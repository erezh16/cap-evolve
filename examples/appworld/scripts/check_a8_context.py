"""A8: context budget and M_cap (plan §6.2, §11). Not counted.

1. 10 dev episodes with no playbook (seed): the characters-per-token ratio of the agent history (the
   text the 60,000-character trimming measures), lowest one used -> H_max = 60,000 / ratio.
2. P_max: the largest stock first request over the 147 train ∪ dev tasks, rendered with the task block
   and the memory heading but no playbook (prompt only, no model call), in vLLM tokens: tiktoken
   o200k_harmony on the message contents + the chat-template overhead measured on the 10 episodes.
3. M_cap = min(30,000, 34,000 − P_max − H_max), rounded down to a multiple of 500; recorded in manifest.
4. 3 dev episodes with an M_cap-token playbook in the slot stay under 34K prompt tokens (vLLM), and
   tiktoken's count of their first request is within 2% of vLLM's prompt_tokens.
  venv-aw/bin/python -I check_a8_context.py [measure|verify]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
sys.path.insert(0, str(EX / "adapters"))
import awpaths as P  # noqa: E402

os.environ["APPWORLD_ROOT"] = str(P.ROOT_OPT)
import adapter  # noqa: E402
import lints  # noqa: E402

A8 = P.AW_STATE / "acceptance" / "a8"


def history_text(messages: list[dict], n_instr: int) -> str:
    """messages_to_text(post_messages) minus the prefix up to 'Task: ' (react_code_agent.trimmed_messages)."""
    post = messages[n_instr - 1:]
    s = ""
    for m in post:
        s += ("ASSISTANT:\n" if m["role"] == "assistant" else "USER:\n" if m["role"] == "user" else "SYSTEM:\n") + m["content"]
    return s[s.index("Task: ") + 6:]


def render_first(task_id: str) -> list[dict]:
    from appworld.task import Task
    from jinja2 import Template
    import aw_agent
    t = Task.load(task_id=task_id, load_ground_truth=False)
    tpl = (EX / "seed_capability/policy/instructions.txt").read_text().lstrip()
    app = json.dumps([{"name": k, "description": v} for k, v in t.app_descriptions.items()], indent=1)
    out = Template(tpl).render(instruction=t.instruction, main_user=t.supervisor, app_descriptions=app) + "\n\n"
    from appworld_agents.code.simplified.react_code_agent import SimplifiedReActCodeAgent
    msgs = SimplifiedReActCodeAgent.text_to_messages(None, out)
    i = msgs[-1]["content"].rfind("My name is: ")
    msgs[-1]["content"] = msgs[-1]["content"][:i] + aw_agent.MEMORY_HEADING + "\n\n\n" + msgs[-1]["content"][i:]
    return msgs


def tok_msgs(msgs: list[dict]) -> int:
    return sum(lints.count_tokens(m["content"]) for m in msgs)


def synthetic_playbook(m_cap: int) -> str:
    base = ["Always call apis.api_docs.show_api_doc before using an API, to check its parameters",
            "Loop over page_index until an API returns an empty page, so that no item is missed",
            "Return answers as minimal values: a number, a name or a title, never a sentence",
            "Print intermediate results in small code chunks before any irreversible change"]
    lines, k = ["## OTHERS"], 1
    while True:
        cand = "\n".join(lines + [f"[misc-{k:05d}] {base[k % 4]} (note {k})."])
        if lints.count_tokens(cand) > m_cap:
            break
        lines.append(f"[misc-{k:05d}] {base[k % 4]} (note {k}).")
        k += 1
    return "\n".join(lines)


def run_cells(name: str, ids: list[str], cap: Path) -> list[dict]:
    items = []
    for t in ids:
        d = A8 / name / t
        d.mkdir(parents=True, exist_ok=True)
        items.append((adapter.episode_spec(t, f"accept/a8{name}/{t}", cap, 100, messages_out=str(d / "messages.json"),
                                           first_request_out=str(d / "first.json")), d / "record.json"))
    recs = adapter.run_episodes(items, workers=10, max_infra_retries=1)
    out = []
    for (spec, path), rec in zip(items, recs):
        d = path.parent
        out.append({"rec": rec, "messages": P.read_json(d / "messages.json"), "first": P.read_json(d / "first.json")})
    return out


def measure() -> dict:
    dev = adapter.tasks("dev")[:10]
    cells = run_cells("seed", dev, EX / "seed_capability")
    ratios, overhead, n_instr = [], [], 23
    ep = []
    for c in cells:
        r = c["rec"]
        ep.append({k: r.get(k) for k in ("termination", "success", "steps", "prompt_tokens_max", "infra_error")})
        if not c["messages"] or r.get("infra_error"):
            continue
        h = history_text(c["messages"], n_instr)
        if len(h) > 2000:
            ratios.append(len(h) / lints.count_tokens(h))
        if c["first"] and r.get("prompt_tokens_per_step"):
            overhead.append(r["prompt_tokens_per_step"][0] - tok_msgs(c["first"]))
    min_ratio = min(ratios)
    h_max = int(60000 / min_ratio + 0.999)
    ids = adapter.tasks("train") + adapter.tasks("dev")
    p_tok = max(tok_msgs(render_first(t)) for t in ids)
    ov = max(overhead)
    p_max = p_tok + ov
    m_cap_raw = min(30000, 34000 - p_max - h_max)
    m_cap = (m_cap_raw // 500) * 500
    res = {"episodes": ep, "history_ratios": [round(x, 3) for x in ratios], "min_ratio": round(min_ratio, 3),
           "H_max": h_max, "P_max_tiktoken": p_tok, "template_overhead_max": ov, "template_overhead": overhead,
           "P_max": p_max, "M_cap_raw": m_cap_raw, "M_cap": m_cap, "prompts_measured": len(ids)}
    P.update_manifest(m_cap={"value": m_cap, "formula": "min(30000, 34000 - P_max - H_max), floor to 500",
                             "P_max": p_max, "H_max": h_max, "min_chars_per_token": round(min_ratio, 3),
                             "encoding": "o200k_harmony"})
    res["ok"] = len(ratios) >= 5 and m_cap > 0
    return res


def verify() -> dict:
    m_cap = int(P.manifest()["m_cap"]["value"])
    pb = synthetic_playbook(m_cap)
    cap = A8 / "cap_mcap"
    import shutil
    if cap.exists():
        shutil.rmtree(cap)
    shutil.copytree(EX / "seed_capability", cap)
    (cap / "memory" / "playbook.md").write_text(pb)
    cells = run_cells("mcap", adapter.tasks("dev")[10:13], cap)
    out = []
    for c in cells:
        r = c["rec"]
        vt = r.get("prompt_tokens_per_step", [None])[0] if r.get("prompt_tokens_per_step") else None
        tt = tok_msgs(c["first"]) if c["first"] else None
        out.append({"termination": r.get("termination"), "prompt_tokens_max": r.get("prompt_tokens_max"),
                    "steps": r.get("steps"), "vllm_first": vt, "tiktoken_first": tt,
                    "rel_diff": round(abs(vt - tt) / vt, 4) if vt and tt else None})
    res = {"m_cap": m_cap, "playbook_tokens": lints.count_tokens(pb), "episodes": out}
    res["ok"] = all(e["prompt_tokens_max"] and e["prompt_tokens_max"] < 34000 and e["termination"] != "context_exceeded"
                    for e in out) and all(e["rel_diff"] is not None and e["rel_diff"] <= 0.02 for e in out)
    return res


def main() -> int:
    A8.mkdir(parents=True, exist_ok=True)
    res = measure() if sys.argv[1] == "measure" else verify()
    P.write_json(A8 / f"{sys.argv[1]}.json", res)
    print(json.dumps(res))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
