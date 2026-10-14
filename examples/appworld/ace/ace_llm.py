"""The ACE Reflector / Curator / merge client to the optimizer gateway (plan §5.3).

generate(messages, role, step) -> {"content", "usage": {"input", "output", "cache_read"}, "finish_reason"}

Replaces ACE's LiteLLMGenerator, which cannot reach the gateway: litellm.completion with
model "anthropic/" + OPT_MODEL, api_base=$ANTHROPIC_BASE_URL, api_key=$ANTHROPIC_AUTH_TOKEN and the
gateway header from $ANTHROPIC_CUSTOM_HEADERS; max_tokens 4096, no response_format, no tools, no
cache; 50 retries 10 s apart (ACE's config). No `temperature`: the gateway rejects it for this model
(HTTP 400 "`temperature` is deprecated for this model", finding G1), so the model default is used.
Deterministic 4xx errors other than 429 are not retried. Every call (full prompt and response text,
tokens, latency, error) is appended to AW_STATE/ace/llm_calls.jsonl. Credentials are never logged.
If the variables are not in the environment they are read from ~/.claude/settings.json `env`.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import awpaths as P  # noqa: E402

OPT_MODEL = os.environ.get("OPT_MODEL", P.OPT_MODEL)
MAX_TOKENS = 4096
RETRIES = 50
RETRY_WAIT_S = 10
CALLS_LOG = Path(os.environ.get("ACE_CALLS_LOG", P.AW_STATE / "ace" / "llm_calls.jsonl"))


def _gateway() -> tuple[str, str, dict[str, str]]:
    env = dict(os.environ)
    if not env.get("ANTHROPIC_BASE_URL"):
        s = json.loads((Path.home() / ".claude" / "settings.json").read_text())
        env.update(s.get("env", {}))
    raw = env.get("ANTHROPIC_CUSTOM_HEADERS", "")
    headers = {}
    for line in raw.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
        elif line.strip():
            headers["x-context-guru-token"] = line.strip()
    return env["ANTHROPIC_BASE_URL"], env["ANTHROPIC_AUTH_TOKEN"], headers


def _log(entry: dict) -> None:
    CALLS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(CALLS_LOG, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def generate(messages: list[dict], role: str, step: str | int | None = None) -> dict:
    import litellm

    base, key, headers = _gateway()
    prompt_text = "\n".join(m["content"] for m in messages)
    t0 = time.time()
    last_err = None
    for attempt in range(RETRIES):
        try:
            r = litellm.completion(model="anthropic/" + OPT_MODEL, messages=messages, api_base=base,
                                   api_key=key, extra_headers=headers, max_tokens=MAX_TOKENS)
            choice = r.choices[0]
            content = choice.message.content or ""
            u = r.usage
            cache_read = int(getattr(u, "cache_read_input_tokens", 0) or 0)
            usage = {"input": int(u.prompt_tokens or 0) - cache_read, "output": int(u.completion_tokens or 0),
                     "cache_read": cache_read}
            out = {"content": content, "usage": usage, "finish_reason": choice.finish_reason,
                   "attempts": attempt + 1}
            _log({"utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "role": role,
                  "step": step, "model": OPT_MODEL, "prompt_sha256": P.sha256_bytes(prompt_text.encode()),
                  "messages": messages, "response": content, "usage": usage,
                  "finish_reason": choice.finish_reason, "latency_s": round(time.time() - t0, 2),
                  "attempts": attempt + 1, "error": None})
            return out
        except Exception as e:  # noqa: BLE001  (retry everything, as ACE's max_retries does)
            last_err = f"{type(e).__name__}: {str(e)[:300]}"
            for secret in [key, *headers.values()]:
                if secret:
                    last_err = last_err.replace(secret, "<redacted>")
            status = getattr(e, "status_code", None)
            if isinstance(status, int) and 400 <= status < 500 and status != 429:
                break
            time.sleep(RETRY_WAIT_S)
    _log({"utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "role": role, "step": step,
          "model": OPT_MODEL, "prompt_sha256": P.sha256_bytes(prompt_text.encode()), "messages": messages,
          "response": None, "usage": {"input": 0, "output": 0, "cache_read": 0}, "finish_reason": None,
          "latency_s": round(time.time() - t0, 2), "attempts": RETRIES, "error": last_err})
    raise RuntimeError(f"optimizer call failed after {RETRIES} attempts: {last_err}")


class MergeGenerator:
    """The `llm_generator` object BulletpointAnalyzer expects (.generate(messages, **kw) -> {content})."""

    def __init__(self, step, meter: list | None = None):
        self.step = step
        self.meter = meter if meter is not None else []

    def generate(self, messages, extra_log_fields=None, **_):
        out = generate(messages, role="merge", step=self.step)
        self.meter.append(out["usage"] | {"finish_reason": out["finish_reason"]})
        return {"content": out["content"]}
