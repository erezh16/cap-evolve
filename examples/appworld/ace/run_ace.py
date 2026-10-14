"""The ACE offline no-GT adaptation loop with per-step checkpoints (plan §8.2–§8.4, §10).

  venv-aw/bin/python -I run_ace.py [--split train] [--limit N] [--ace-dir DIR] [--no-ledger]

For training task i = 1 … N (order = load_task_ids(split), no shuffle), four sub-steps, each
persisted before the next starts, and each reused on resume (never re-run, never re-requested):
  1. episode   common-harness episode with memory/playbook.md = pb_{i-1}       -> episode.json, messages.json
  2. reflector ACE no-GT reflector prompt (ported from adaptation_react.py)      -> reflector.json
  3. curator   ACE curator prompt; JSON schema checks, ADD-only, section whitelist -> curator.json
  4. apply     per-bullet lint (§8.3), apply_curator_operations, D5 size rule    -> apply.json, pb_<iii>.txt
Then one checkpoint: pushed ace/playbook.txt + ace/progress.json + ledger entry, one commit.

As in ACE's `solve_task_wo_gt`, the Reflector and Curator run only when the episode ended with
`task_completed()` or the per-task cost limit (here also the F2 token cap, its analogue); an
episode that reaches the step cap, or ends on an LM error, gets no curation (playbook carried).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parent
sys.path.insert(0, str(EX / "scripts"))
sys.path.insert(0, str(EX / "adapters"))
sys.path.insert(0, str(EX))
sys.path.insert(0, str(HERE))
import awpaths as P  # noqa: E402
import adapter  # noqa: E402
import lints  # noqa: E402
import ace_llm  # noqa: E402
from ace.vendor.playbook import apply_curator_operations, extract_json_from_text, get_next_global_id  # noqa: E402

VENDOR = HERE / "vendor"
# Our copies of ACE's prompts: identical to vendor/prompts except that the phrase "chain of thought /
# reasoning / thinking process, " is removed from the `reasoning` field description (4 places). With it
# the gateway ends every Reflector and Curator response with finish_reason "refusal" (finding G2,
# plan §15 / A7). Field names are unchanged. Diff: prompts/gateway-filter.diff.
PROMPTS = HERE / "prompts"
REFLECTOR_PROMPT = (PROMPTS / "appworld_react_reflector_no_gt_prompt.txt").read_text()
CURATOR_PROMPT = (PROMPTS / "appworld_react_curator_prompt.txt").read_text()
INITIAL_PLAYBOOK = (VENDOR / "playbooks" / "appworld_initial_playbook.txt").read_text()
ALLOWED_SECTIONS = {
    "strategies_and_hard_rules",
    "apis_to_use_for_specific_information",
    "useful_code_snippets_and_templates",
    "common_mistakes_and_correct_strategies",
    "problem_solving_heuristics_and_workflows",
    "verification_checklist",
    "troubleshooting_and_pitfalls",
    "others",
}
CURATE_ON = {"completed", "cost_cap", "token_cap"}
SOFT_CAP, HARD_CAP, ROLLOUT_CAP = 8_500_000, 10_000_000, 900
USD_IN, USD_OUT = 2.0, 10.0  # proxy list prices per Mtok
SCAN_STRINGS = ["test_normal", "root_full", "answer.json", "ground_truth"]

STOP = False


def _sigterm(*_):
    global STOP
    STOP = True


# ------------------------------------------------------------------ ported from adaptation_react.py

def conversation_history(messages: list[dict]) -> str:
    out = "\n\n=== FULL CONVERSATION HISTORY ===\n"
    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        out += f"[{i}] {role.upper()}: {content}\n\n"
    return out


def render_reflector(playbook: str, messages: list[dict], world_gt_code=None, test_report=None) -> str:
    filled = (
        REFLECTOR_PROMPT
        .replace("{{ground_truth_code}}", world_gt_code or "")
        .replace("{{test_report}}", test_report or "")
        .replace("{{generated_code}}", "See full conversation history below")
        .replace("{{generated_rationale}}", "See full conversation history below")
        .replace("{{spec_or_api_docs}}", "See full conversation history below")
        .replace("{{execution_error}}", "See full conversation history below")
        .replace("{{playbook}}", playbook or "N/A")
        .replace("{{previous_reflection}}", "N/A")
    )
    return filled + conversation_history(messages)


def render_curator(playbook: str, reflection: str | None, instruction: str, messages: list[dict],
                   world_gt_code=None) -> str:
    content = CURATOR_PROMPT.format(
        initial_generated_code="See full conversation history below",
        final_generated_code="See full conversation history below",
        guidebook=reflection,
        current_playbook=playbook,
        question_context=instruction,
        gt=world_gt_code,
    )
    return content + conversation_history(messages)


def validate_curator(curator_response: str) -> tuple[list[dict] | None, list[dict], str | None]:
    """ACE's strict validation. Returns (accepted ADD ops or None if the update is skipped,
    ops skipped for an off-whitelist section, error)."""
    operations_info = extract_json_from_text(curator_response, "operations")
    skipped = []
    try:
        if not operations_info:
            raise ValueError("Failed to extract valid JSON from curator response")
        if "reasoning" not in operations_info:
            raise ValueError("JSON missing required 'reasoning' field")
        if "operations" not in operations_info:
            raise ValueError("JSON missing required 'operations' field")
        if not isinstance(operations_info["reasoning"], str):
            raise ValueError("'reasoning' field must be a string")
        if not isinstance(operations_info["operations"], list):
            raise ValueError("'operations' field must be a list")
        filtered_ops: list[dict] = []
        for i, op in enumerate(operations_info["operations"]):
            if not isinstance(op, dict):
                raise ValueError(f"Operation {i} must be a dictionary")
            if "type" not in op:
                raise ValueError(f"Operation {i} missing required 'type' field")
            if op["type"] != "ADD":
                raise ValueError(f"Operation {i} has invalid type '{op['type']}'. Only 'ADD' operations are supported in this file")
            required_fields = {"type", "section", "content"}
            missing_fields = required_fields - set(op.keys())
            if missing_fields:
                raise ValueError(f"ADD operation {i} missing fields: {list(missing_fields)}")
            section_name = str(op.get("section", "")).strip().lower().replace(" ", "_").replace("&", "and").rstrip(":")
            if section_name not in ALLOWED_SECTIONS:
                skipped.append({"index": i, "section": op.get("section")})
                continue
            filtered_ops.append(op)
        return filtered_ops, skipped, None
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        return None, skipped, f"{type(e).__name__}: {e}"
    except Exception as e:  # noqa: BLE001  (ACE: "Curator operation failed", update skipped)
        return None, skipped, f"{type(e).__name__}: {e}"


# ------------------------------------------------------------------ §8.3 lint, §8.4 size rule

_analyzer = None


class CachedMerge(ace_llm.MergeGenerator):
    """Merge calls cached by prompt sha256 in the step dir, so a resumed apply never repays a merge."""

    def __init__(self, step, meter, cache_path: Path | None):
        super().__init__(step, meter)
        self.cache_path = cache_path
        self.cache = (P.read_json(cache_path, {}) or {}) if cache_path else {}

    def generate(self, messages, extra_log_fields=None, **_):
        key = P.sha256_bytes(json.dumps(messages, sort_keys=True).encode())
        if key in self.cache:
            return {"content": self.cache[key]}
        out = super().generate(messages)
        self.cache[key] = out["content"]
        if self.cache_path:
            P.write_json(self.cache_path, self.cache)
        return out


def _get_analyzer(meter: list, step, cache_path=None):
    global _analyzer
    from ace.vendor.bulletpoint_analyzer import BulletpointAnalyzer
    if _analyzer is None:
        os.environ.setdefault("HF_HOME", str(P.HF_HOME))
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        _analyzer = BulletpointAnalyzer(None, embedding_model_name="sentence-transformers/all-mpnet-base-v2")
    _analyzer.llm_generator = CachedMerge(step, meter, cache_path)
    return _analyzer


def apply_with_rules(pb_prev: str, next_id: int, ops: list[dict], m_cap: int, step,
                     merge_cache: Path | None = None) -> tuple[str, int, dict]:
    info = {"ops_in": len(ops), "lint_drop": [], "applied": 0, "cap_drop": 0, "dedup": None,
            "merge_usage": []}
    kept = []
    for i, op in enumerate(ops):
        v = lints.bullet_violations(str(op.get("content", "")))
        if v:
            info["lint_drop"].append({"op": i, "rules": v, "source": "curator"})
        else:
            kept.append(op)
    cand, cand_next = apply_curator_operations(pb_prev, kept, next_id)
    tok = lints.count_tokens(cand)
    if tok <= m_cap:
        info["applied"] = len(kept)
        return cand, cand_next, info
    # D5 (a): one dedup pass at the cap, merges by OPT_MODEL
    before = lints.bullets(cand)
    an = _get_analyzer(info["merge_usage"], step, merge_cache)
    deduped = an.analyze(cand, threshold=0.90, merge=True)
    old_lines = set(cand.splitlines())
    out_lines = []
    merged = 0
    for line in deduped.splitlines():
        if line not in old_lines:
            merged += 1
            v = lints.bullet_violations(line)
            if v:
                info["lint_drop"].append({"rules": v, "source": "merge"})
                continue
        out_lines.append(line)
    deduped = "\n".join(out_lines)
    dtok = lints.count_tokens(deduped)
    info["dedup"] = {"bullets_before": len(before), "bullets_after": len(lints.bullets(deduped)),
                     "merged_bullets": merged, "tokens_before": tok, "tokens_after": dtok,
                     "merge_calls": len(info["merge_usage"])}
    if dtok <= m_cap:
        info["applied"] = len(kept)
        return deduped, cand_next, info
    info["cap_drop"] = len(kept)
    return pb_prev, next_id, info


# ------------------------------------------------------------------ isolation scan (§9, per step)

def scan_counts(texts: list[str]) -> dict:
    cache = json.loads(P.LINT_CACHE.read_text())
    test_ids = set(cache["test_ids"])
    out = {"test_id": 0, **{s: 0 for s in SCAN_STRINGS}, "canary": 0}
    for t in texts:
        if not t:
            continue
        out["test_id"] += sum(1 for m in re.findall(r"\b[0-9a-f]{7}_[0-9]+\b", t) if m in test_ids)
        for s in SCAN_STRINGS:
            out[s] += t.count(s)
        out["canary"] += t.count("appworld:d17ac3f")
    return out


# ------------------------------------------------------------------ the loop

class Runner:
    def __init__(self, args):
        self.args = args
        self.ace_dir = Path(args.ace_dir)
        self.steps_dir = self.ace_dir / "steps"
        self.pb_dir = self.ace_dir / "playbooks"
        self.pushed = Path(args.pushed_dir)
        self.ledger = not args.no_ledger
        self.m_cap = int(args.m_cap or P.manifest()["m_cap"]["value"])
        self.progress = P.read_json(self.pushed / "progress.json") or {
            "last_applied_step": 0, "next_global_id": None, "rows": [], "spend": {}, "rollouts": 0,
            "soft_cap_reached": False, "hard_stop": False, "m_cap": self.m_cap}
        self.trial = args.trial_name

    # ---------------------------------------------------- helpers
    def log(self, detail: str) -> None:
        P.progress_log(self.trial, "P4" if self.ledger else "test", detail)
        print(detail, flush=True)

    def spend_total(self) -> int:
        s = self.progress["spend"]
        return sum(v.get("input", 0) + v.get("output", 0) for v in s.values())

    def recompute_spend(self) -> None:
        """Spend = sum over checkpointed rows of the usage stored in the step files (crash-safe)."""
        tot = {}
        for r in self.progress["rows"]:
            for role, u in (r.get("usage") or {}).items():
                s = tot.setdefault(role, {"calls": 0, "input": 0, "output": 0, "truncated": 0})
                for k in s:
                    s[k] += u.get(k, 0)
        self.progress["spend"] = tot

    @staticmethod
    def _u(usage: dict, finish_reason) -> dict:
        return {"calls": 1, "input": usage.get("input", 0), "output": usage.get("output", 0),
                "truncated": int(finish_reason in ("length", "max_tokens"))}

    def usd(self) -> float:
        s = self.progress["spend"]
        i = sum(v["input"] for v in s.values())
        o = sum(v["output"] for v in s.values())
        return round(i / 1e6 * USD_IN + o / 1e6 * USD_OUT, 2)

    def instruction(self, task_id: str) -> str:
        return json.loads((P.ROOT_OPT / "data" / "tasks" / task_id / "specs.json").read_text())["instruction"]

    def pb_path(self, i: int) -> Path:
        return self.pb_dir / f"pb_{i:03d}.txt"

    # ---------------------------------------------------- one step
    def step(self, i: int, task_id: str) -> dict:
        sd = self.steps_dir / f"{i:03d}"
        sd.mkdir(parents=True, exist_ok=True)
        if (sd / "apply.json").exists() and self.pb_path(i).exists():  # resume: step fully applied
            a = json.loads((sd / "apply.json").read_text())
            a.pop("lint_drop_detail", None)
            return a | {"_next_global_id": a.pop("next_global_id")}
        pb_prev = self.pb_path(i - 1).read_text()
        next_id = self.progress["next_global_id"] or get_next_global_id(pb_prev)
        # 1. episode
        ep_path = sd / "episode.json"
        if not ep_path.exists():
            ml = lints.memory_lint(pb_prev, self.m_cap)
            if not ml["ok"]:
                raise RuntimeError(f"playbook pb_{i-1:03d} fails the memory lint before a rollout: {ml}")
            cap = sd / "cap"
            if cap.exists():
                shutil.rmtree(cap)
            shutil.copytree(EX / "seed_capability", cap)
            (cap / "memory" / ".gitkeep").unlink(missing_ok=True)
            (cap / "memory" / "playbook.md").write_text(pb_prev)
            spec = adapter.episode_spec(task_id, f"{self.args.exp_prefix}/ace/{task_id}/t0", cap, 100,
                                        messages_out=str(sd / "messages.json"))
            self.log(f"step {i:03d}/{self.n} episode start")
            rec = adapter.run_episode(spec, ep_path, max_infra_retries=1)
            self.log(f"step {i:03d}/{self.n} episode {rec.get('termination')} success={rec.get('success')} "
                     f"steps={rec.get('steps')} prompt_max={rec.get('prompt_tokens_max')}")
        rec = json.loads(ep_path.read_text())
        row = {"step": i, "success": rec.get("success"), "steps": rec.get("steps"),
               "termination": rec.get("termination"), "infra_retries": rec.get("infra_retries", 0),
               "prompt_tokens_max": rec.get("prompt_tokens_max"), "completion_tokens": rec.get("completion_tokens"),
               "context_exceeded": rec.get("termination") == "context_exceeded", "fs_probe": rec.get("fs_probe", [])}
        texts = []
        if rec.get("infra_error"):
            row["skipped"] = "skipped_infra"
            new_pb, new_next, info = pb_prev, next_id, {"ops_in": 0, "applied": 0, "lint_drop": [], "cap_drop": 0, "dedup": None}
            curated = False
        elif rec.get("termination") not in CURATE_ON:
            row["skipped"] = f"no_curation_{rec.get('termination')}"
            new_pb, new_next, info = pb_prev, next_id, {"ops_in": 0, "applied": 0, "lint_drop": [], "cap_drop": 0, "dedup": None}
            curated = False
        else:
            curated = True
            messages = json.loads((sd / "messages.json").read_text())
            # 2. reflector
            rf = sd / "reflector.json"
            if not rf.exists():
                prompt = render_reflector(pb_prev, messages)
                out = ace_llm.generate([{"role": "user", "content": prompt}], role="reflector", step=i)
                P.write_json(rf, {"prompt_sha256": P.sha256_bytes(prompt.encode()), "response": out["content"],
                                  "usage": out["usage"], "finish_reason": out["finish_reason"]})
            refl = json.loads(rf.read_text())
            texts += [render_reflector(pb_prev, messages), refl["response"]]
            # 3. curator
            cf = sd / "curator.json"
            if not cf.exists():
                prompt = render_curator(pb_prev, refl["response"], self.instruction(task_id), messages)
                out = ace_llm.generate([{"role": "user", "content": prompt}], role="curator", step=i)
                ops, skipped, err = validate_curator(out["content"])
                P.write_json(cf, {"prompt_sha256": P.sha256_bytes(prompt.encode()), "response": out["content"],
                                  "usage": out["usage"], "finish_reason": out["finish_reason"],
                                  "operations": ops, "skipped_off_whitelist": skipped, "parse_error": err})
            cur = json.loads(cf.read_text())
            texts += [render_curator(pb_prev, refl["response"], self.instruction(task_id), messages), cur["response"]]
            # 4. apply
            ops = cur["operations"]
            if ops is None:
                new_pb, new_next, info = pb_prev, next_id, {"ops_in": 0, "applied": 0, "lint_drop": [], "cap_drop": 0,
                                                            "dedup": None, "parse_error": cur["parse_error"]}
            else:
                new_pb, new_next, info = apply_with_rules(pb_prev, next_id, ops, self.m_cap, i,
                                                          merge_cache=sd / "merge_cache.json")
            usage = {"reflector": self._u(refl["usage"], refl["finish_reason"]),
                     "curator": self._u(cur["usage"], cur["finish_reason"])}
            mu = info.get("merge_usage") or []
            if mu:
                usage["merge"] = {"calls": len(mu), "input": sum(u["input"] for u in mu),
                                  "output": sum(u["output"] for u in mu),
                                  "truncated": sum(u.get("finish_reason") in ("length", "max_tokens") for u in mu)}
            row["usage"] = usage
            row.update({"ops_proposed": (len(ops) if ops is not None else 0) + len(cur["skipped_off_whitelist"]),
                        "off_whitelist": len(cur["skipped_off_whitelist"]), "parse_error": cur["parse_error"] is not None,
                        "reflector_usage": refl["usage"], "curator_usage": cur["usage"]})
        texts.append(new_pb)
        ml = lints.memory_lint(new_pb, self.m_cap)
        if not ml["ok"]:
            raise RuntimeError(f"pb_{i:03d} fails the memory lint after apply: {ml}")
        P.atomic_write(self.pb_path(i), new_pb)
        scan = scan_counts(texts)
        row.update({"curated": curated, "ops_applied": info["applied"], "lint_drop": len(info["lint_drop"]),
                    "lint_drop_rules": sorted({r for d in info["lint_drop"] for r in d["rules"]}),
                    "cap_drop": info["cap_drop"], "dedup": info["dedup"],
                    "pb_tokens": ml["tokens"], "pb_chars": ml["chars"], "pb_bullets": ml["bullets"],
                    "pb_sha256": P.sha256_bytes(new_pb.encode()), "scan": scan})
        P.write_json(sd / "apply.json", {**row, "next_global_id": new_next,
                                         "lint_drop_detail": info["lint_drop"]})
        return row | {"_next_global_id": new_next}

    # ---------------------------------------------------- checkpoint
    def checkpoint(self, row: dict) -> None:
        i = row["step"]
        nxt = row.pop("_next_global_id")
        self.progress["rows"] = [r for r in self.progress["rows"] if r["step"] != i] + [row]
        self.progress["last_applied_step"] = i
        self.progress["next_global_id"] = nxt
        self.recompute_spend()
        self.progress["rollouts"] = sum(1 for r in self.progress["rows"] if not r.get("skipped") == "skipped_infra")
        self.pushed.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.pb_path(i), self.pushed / "playbook.txt")
        P.write_json(self.pushed / "progress.json", self.progress)
        if not self.ledger:
            return
        import status_doc
        tot = self.spend_total()
        s = self.progress["spend"]
        tin = sum(v["input"] for v in s.values()) / 1e6
        tout = sum(v["output"] for v in s.values()) / 1e6
        bits = []
        if row.get("skipped"):
            bits.append(row["skipped"].replace("_", " "))
        else:
            bits.append(f"+{row['ops_applied']} bullets")
        bits.append(f"{row['lint_drop']} lint_drop, {row['cap_drop']} cap_drop")
        if row.get("dedup"):
            d = row["dedup"]
            bits.append(f"dedup {d['bullets_before']}→{d['bullets_after']} bullets")
        if row.get("parse_error"):
            bits.append("curator JSON invalid, update skipped")
        ep = f"episode {'pass' if row['success'] else 'fail'}, {row['steps']} steps, {row['termination']}"
        scan_hits = {k: v for k, v in row["scan"].items() if v}
        prose = (f"ACE step {i:03d} done ({ep}; {'; '.join(bits)}); 1 counted rollout.\n"
                 f"Totals: rollouts counted {self.progress['rollouts']} (ace {self.progress['rollouts']}, seed 0); "
                 f"playbook {row['pb_bullets']} bullets, {row['pb_chars']:,} chars, {row['pb_tokens']:,} tokens "
                 f"(M_cap {self.m_cap:,}); optimizer {tin:.2f}M in / {tout:.2f}M out tok, ${self.usd():.2f} proxy.\n"
                 f"Isolation scan this step: {scan_hits or 'no hits'}.\n"
                 f"Runner: alive (pid {os.getpid()}).\n"
                 f"Next: {'P5 freeze' if i >= self.n else f'P4 ace/step/{i+1:03d} episode'}.")
        status_doc.append("result", "P4", "ACE adaptation", prose,
                          done_through=f"ace/step/{i:03d}/apply",
                          next_unit="P5/freeze" if i >= self.n else f"ace/step/{i+1:03d}/episode",
                          extra={"counts": {"rollouts_counted": self.progress["rollouts"], "ace_steps": i},
                                 "spend": {"opt_in_tok": int(tin * 1e6), "opt_out_tok": int(tout * 1e6),
                                           "usd_proxy": self.usd()}},
                          artifacts=["STATE/ace/playbook.txt", "STATE/ace/progress.json",
                                     f"local/ace/playbooks/pb_{i:03d}.txt"],
                          subject=f"ace/step/{i:03d}")
        if tot >= SOFT_CAP and not self.progress["soft_cap_reached"]:
            self.progress["soft_cap_reached"] = True
            P.write_json(self.pushed / "progress.json", self.progress)
            status_doc.append("cap_spend", "P4", "ACE adaptation",
                              f"Optimizer soft guard reached: {tot:,} non-cache-read tokens ≥ 8.5M after step {i:03d}. "
                              f"The run continues (hard stop at 10M).", extra={"cap": "soft", "tokens": tot},
                              artifacts=["STATE/ace/progress.json"], subject="cap_spend soft")
        if self.args.post_every and i % self.args.post_every == 0 and i < self.n:
            try:
                import post_update
                post_update.post_ace_progress(i, self.n)
            except Exception as e:  # noqa: BLE001  posting never stops the run
                self.log(f"interim #804 post failed: {type(e).__name__}: {str(e)[:200]}")

    # ---------------------------------------------------- run
    def run(self) -> int:
        signal.signal(signal.SIGTERM, _sigterm)
        ids = adapter.tasks(self.args.split)
        if self.args.limit:
            ids = ids[: self.args.limit]
        self.n = len(ids)
        self.pb_dir.mkdir(parents=True, exist_ok=True)
        if not self.pb_path(0).exists():
            P.atomic_write(self.pb_path(0), INITIAL_PLAYBOOK)
        start = self.progress["last_applied_step"] + 1
        for i in range(start, self.n + 1):
            if STOP:
                self.log(f"SIGTERM: stopping before step {i:03d}")
                return 0
            if self.spend_total() >= HARD_CAP:
                self.progress["hard_stop"] = True
                P.write_json(self.pushed / "progress.json", self.progress)
                if self.ledger:
                    import status_doc
                    status_doc.append("cap_spend", "P4", "ACE adaptation",
                                      f"Optimizer hard guard: {self.spend_total():,} tokens ≥ 10M; adaptation stops after "
                                      f"step {i-1:03d} (budget termination, disclosed). Artifact = pb_{i-1:03d}.",
                                      extra={"cap": "hard"}, next_unit="P5/freeze", subject="cap_spend hard")
                return 0
            if self.progress["rollouts"] >= ROLLOUT_CAP:
                self.log("rollout cap reached")
                return 0
            row = self.step(i, ids[i - 1])
            self.checkpoint(row)
            self.log(f"step {i:03d}/{self.n} +{row['ops_applied']} bullets ({row['lint_drop']} lint_drop, "
                     f"{row['cap_drop']} cap_drop) pb={row['pb_chars']:,} chars {row['pb_tokens']:,} tok")
        return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="train")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ace-dir", default=str(P.AW_STATE / "ace"))
    ap.add_argument("--pushed-dir", default=str(P.PUSHED / "ace"))
    ap.add_argument("--no-ledger", action="store_true")
    ap.add_argument("--m-cap", type=int, default=0)
    ap.add_argument("--exp-prefix", default="p4")
    ap.add_argument("--trial-name", default="ace")
    ap.add_argument("--post-every", type=int, default=0)
    args = ap.parse_args()
    os.environ.setdefault("ACE_CALLS_LOG", str(Path(args.ace_dir) / "llm_calls.jsonl"))
    ace_llm.CALLS_LOG = Path(os.environ["ACE_CALLS_LOG"])
    pid_file = P.AW_STATE / "RUNNING.pid"
    own_pid = not args.no_ledger and not os.environ.get("AW_UNDER_PIPELINE")
    if own_pid:
        pid_file.write_text(f"{os.getpid()} run_ace\n")
    try:
        return Runner(args).run()
    finally:
        if own_pid and pid_file.exists() and pid_file.read_text().split()[0] == str(os.getpid()):
            pid_file.unlink()


if __name__ == "__main__":
    sys.exit(main())
