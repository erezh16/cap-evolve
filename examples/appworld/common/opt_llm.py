"""The optimizer-model shim shared by every eval-REST candidate (docs/EVAL_APPWORLD_REST.md §5.2, §7.4; G1–G3).

  chat(messages, *, cand, role, system=None, max_tokens=8192) -> str

Calls ``aws/claude-sonnet-5-5`` on the gateway in ``~/.claude/settings.json`` (``ANTHROPIC_BASE_URL``,
``ANTHROPIC_AUTH_TOKEN``, the ``x-context-guru-token`` header from ``ANTHROPIC_CUSTOM_HEADERS``) through
the Anthropic Messages API, stdlib only, so every candidate venv can import it. No ``temperature`` (G1),
no tools, no structured output (G3). 429/5xx/network errors are retried (30 attempts, backoff to 60 s);
other 4xx are not (G1). OpenAI-style messages are accepted: ``system`` messages are joined into the
top-level ``system`` field and consecutive same-role messages are merged.

Every call appends one usage line ``{t, seconds, model, role, prompt_tokens, completion_tokens,
cache_read, cache_write, error, finish_reason}`` to ``AW_STATE/<cand>/optimizer_usage.jsonl`` (the single cost and
latency source for the optimizer side, §5.2) and the full prompt/response to ``AW_STATE/<cand>/llm_calls.jsonl``
(local only, never pushed). Before each call the candidate's cumulative non-cache-read tokens are checked
against the 10M cap (§7.4); over the cap the call raises ``BudgetExceeded``. No call starts while
AW_STATE/PAUSE exists (rule R2). Credentials are never logged.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import awrest as P  # noqa: E402

OPT_MODEL = os.environ.get("OPT_MODEL", P.OPT_MODEL)
RETRIES = 30
_lock = threading.Lock()
_totals: dict[str, int] = {}


class BudgetExceeded(RuntimeError):
    pass


class Refusal(RuntimeError):
    pass


def _gateway() -> tuple[str, str, dict[str, str]]:
    env = dict(os.environ)
    if not env.get("ANTHROPIC_BASE_URL") or not env.get("ANTHROPIC_AUTH_TOKEN"):
        s = json.loads((Path.home() / ".claude" / "settings.json").read_text())
        env.update(s.get("env", {}))
    headers = {}
    for line in env.get("ANTHROPIC_CUSTOM_HEADERS", "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    return env["ANTHROPIC_BASE_URL"].rstrip("/"), env["ANTHROPIC_AUTH_TOKEN"], headers


def usage_path(cand: str) -> Path:
    return P.AW_STATE / cand / "optimizer_usage.jsonl"


def totals(cand: str) -> dict:
    """Cumulative usage of a candidate's optimizer (all roles), from its usage log."""
    rows = P.read_jsonl(usage_path(cand))
    return {"calls": len(rows), "errors": sum(1 for r in rows if r.get("error")),
            "prompt_tokens": sum(int(r.get("prompt_tokens") or 0) for r in rows),
            "completion_tokens": sum(int(r.get("completion_tokens") or 0) for r in rows),
            "cache_read": sum(int(r.get("cache_read") or 0) for r in rows),
            "cache_write": sum(int(r.get("cache_write") or 0) for r in rows),
            "seconds": round(sum(float(r.get("seconds") or 0) for r in rows), 1)}


def proxy_usd(t: dict) -> float:
    """Proxy USD at the Sonnet 5.5 list price (§5.2). prompt_tokens includes cache writes (they are
    non-cache-read input); they are priced at the cache-write rate, the rest at the input rate."""
    cw = t.get("cache_write", 0)
    return round(((t["prompt_tokens"] - cw) * P.PRICE_IN + cw * P.PRICE_CACHE_WRITE
                  + t["completion_tokens"] * P.PRICE_OUT + t.get("cache_read", 0) * P.PRICE_CACHE_READ) / 1e6, 2)


def _spent(cand: str) -> int:
    with _lock:
        if cand not in _totals:
            t = totals(cand)
            _totals[cand] = t["prompt_tokens"] + t["completion_tokens"]
        return _totals[cand]


def _add(cand: str, n: int) -> None:
    with _lock:
        _totals[cand] = _totals.get(cand, 0) + n


def to_anthropic(messages: list[dict], system: str | None = None) -> tuple[str, list[dict]]:
    sys_parts = [system] if system else []
    out: list[dict] = []
    for m in messages:
        role, content = m.get("role"), m.get("content") or ""
        if isinstance(content, list):  # OpenAI content parts: keep the text
            content = "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
        if role == "system":
            sys_parts.append(content)
            continue
        role = "assistant" if role == "assistant" else "user"
        if out and out[-1]["role"] == role:
            out[-1]["content"] += "\n\n" + content
        else:
            out.append({"role": role, "content": content})
    if not out or out[0]["role"] != "user":
        out.insert(0, {"role": "user", "content": "(begin)"})
    return "\n\n".join(sys_parts), out


def chat(messages: list[dict] | str, *, cand: str, role: str, system: str | None = None,
         max_tokens: int = 8192, budget: int = P.BUDGET_OPT_TOKENS) -> str:
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    P.wait_unpaused(cand)                         # rule R2: no new optimizer call while PAUSED
    if budget is not None and _spent(cand) >= budget:          # None = no cap (ABLATIONS D12)
        raise BudgetExceeded(f"{cand}: optimizer tokens {_spent(cand):,} >= cap {budget:,}")
    base, key, headers = _gateway()
    sys_text, msgs = to_anthropic(messages, system)
    body = {"model": OPT_MODEL, "max_tokens": int(max_tokens), "messages": msgs}
    if sys_text:
        body["system"] = sys_text
    data = json.dumps(body).encode()
    t0 = time.time()
    err, text, usage, stop = None, None, {}, None
    for attempt in range(RETRIES):
        req = urllib.request.Request(base + "/v1/messages", data=data, headers={
            "content-type": "application/json", "anthropic-version": "2023-06-01",
            "authorization": "Bearer " + key, **headers})
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                d = json.loads(r.read())
            text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
            usage, stop, err = d.get("usage") or {}, d.get("stop_reason"), None
            break
        except urllib.error.HTTPError as e:
            msg = e.read()[:400].decode("utf-8", "ignore")
            err = f"HTTP {e.code}: {msg}"
            if 400 <= e.code < 500 and e.code != 429:
                break
        except Exception as e:  # noqa: BLE001 — network / timeout: retry
            err = f"{type(e).__name__}: {str(e)[:200]}"
        for secret in [key, *headers.values()]:
            err = err.replace(secret, "<redacted>") if err and secret else err
        time.sleep(min(60, 5 * (attempt + 1)))
    pt = int(usage.get("input_tokens") or 0) + int(usage.get("cache_creation_input_tokens") or 0)
    ct = int(usage.get("output_tokens") or 0)
    _add(cand, pt + ct)
    row = {"t": P.utcnow(), "seconds": round(time.time() - t0, 2), "model": OPT_MODEL, "role": role,
           "prompt_tokens": pt, "completion_tokens": ct, "cache_read": int(usage.get("cache_read_input_tokens") or 0),
           "cache_write": int(usage.get("cache_creation_input_tokens") or 0), "error": err, "finish_reason": stop}
    P.append_jsonl(usage_path(cand), row)
    P.append_jsonl(P.AW_STATE / cand / "llm_calls.jsonl",
                   {**row, "system": sys_text, "messages": msgs, "response": text})
    if text is None:
        raise RuntimeError(f"optimizer call failed: {err}")
    if stop == "refusal":
        raise Refusal("the gateway returned finish_reason refusal (G2)")
    return text


if __name__ == "__main__":  # A1: one call through the shim
    print(chat("Reply with the single word ok.", cand=sys.argv[1] if len(sys.argv) > 1 else "a1", role="a1",
               max_tokens=20))
