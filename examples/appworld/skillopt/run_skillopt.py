"""The `skillopt` arm: SkillOpt (main @ ae2f766) evolving one skill document in the M slot (§7.2).

  venv-skillopt/bin/python -I run_skillopt.py search    # resumable (SkillOpt's runtime_state.json + episode records)
  venv-skillopt/bin/python -I run_skillopt.py accept    # A-skillopt: 1 step on 4 dev tasks, throwaway, not counted
  venv-skillopt/bin/python -I run_skillopt.py freeze    # out_root/best_skill.md -> memory/playbook.md, lint, artifact

``ReflACTTrainer(cfg, AppWorldAdapter).train()`` with SkillOpt's own defaults (its configs/_base_ via its
own scripts/train.py load_config), the plan's settings in appworld.yaml, and these changes only:
* the optimizer backend ``openai_compatible`` has its ``chat_optimizer`` replaced by the shared gateway
  shim (every stage: analyst, merge, ranking, slow update, meta skill), max_tokens 16384, no temperature;
* ``num_epochs`` 3 instead of 4 so the counted rollouts stay within B = 900 (§7.2 budget rule; worst case
  57 + 3·(90 + 3·57) + 2·40 = 920, so the evaluator's hard cap of 900 can cut the very last gate);
* rollouts run the shared AppWorld evaluator; ``hard`` = success, ``soft`` = share of requirement checks
  passed, ``fail_reason`` = gold-free failed-check summary; train rollouts write a compacted
  conversation.json (per-step thought/code/output, outputs ≤ 2,000 chars, ≤ 60,000 chars in all) with a
  final ``{"role": "system"}`` F1 report; dev (gate) rollouts write nothing the optimizer reads;
* no ``reference_text`` is ever set (SkillOpt's "Hidden Reference" never appears); eval_test false, test = [];
* a skill over M_cap / 30,000 chars is lint-rejected by the evaluator (scored 0, not run).
Only a resumed step's own episodes are replayed from their records (tag = SkillOpt's step dir); every other
rollout runs as SkillOpt asks (its selection cache already skips identical gates).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE.parent / "common"))
import aw5 as P  # noqa: E402

P.setup_env()
import evaluator as E  # noqa: E402
import opt_llm  # noqa: E402

CAND = os.environ.get("AW_CAND", "skillopt")
STATE = P.AW_STATE / CAND
OUT_ROOT = STATE / "out_root"
SKILLOPT = P.CLONES / "skillopt"
NUM_EPOCHS = int(os.environ.get("AW_SKILLOPT_EPOCHS", 3))
CONV_OUT_CHARS = 2000
CONV_MAX_CHARS = 60000
sys.path.insert(0, str(SKILLOPT))
sys.path.insert(0, str(SKILLOPT / "scripts"))


def patch_optimizer(cand: str) -> None:
    """Every SkillOpt optimizer stage -> the shared gateway shim (looked up on the module at call time)."""
    import skillopt.model.openai_compatible_backend as ocb

    def chat_optimizer(system, user, max_completion_tokens=16384, retries=5, stage="optimizer",
                       reasoning_effort=None, timeout=None):
        try:
            text = opt_llm.chat([{"role": "user", "content": user}], system=system, cand=cand, role=stage,
                                max_tokens=min(int(max_completion_tokens or 16384), 16384))
        except opt_llm.Refusal:
            P.progress_log(cand, "P3", f"refusal in stage {stage} (G2); returned empty text")
            text = ""
        u = P.read_jsonl(opt_llm.usage_path(cand))[-1]
        ocb.tracker.record(stage, int(u["prompt_tokens"]), int(u["completion_tokens"]))
        return text, {"prompt_tokens": int(u["prompt_tokens"]), "completion_tokens": int(u["completion_tokens"])}

    ocb.chat_optimizer = chat_optimizer


def _conversation(rec: dict, with_report: bool) -> list[dict]:
    msgs = [{"role": "user", "content": f"Task: {rec['instruction']}"}]
    steps = rec.get("steps") or []
    outs = [(s.get("output") or "")[:CONV_OUT_CHARS] for s in steps]
    for s, o in zip(steps, outs):
        thought = (s.get("thought") or "").strip()
        msgs.append({"role": "assistant", "content": (thought + "\n\n" if thought else "")
                     + f"```python\n{(s.get('code') or '').strip()}\n```"})
        msgs.append({"role": "user", "content": f"Output:\n{o}"})
    # cap the whole conversation: shrink the longest outputs first
    total = sum(len(m["content"]) for m in msgs)
    while total > CONV_MAX_CHARS:
        i = max((k for k in range(2, len(msgs), 2)), key=lambda k: len(msgs[k]["content"]), default=None)
        if i is None or len(msgs[i]["content"]) < 200:
            break
        cut = min(len(msgs[i]["content"]) // 2, total - CONV_MAX_CHARS + 50)
        msgs[i]["content"] = msgs[i]["content"][: len(msgs[i]["content"]) - cut] + "\n…[truncated]"
        total = sum(len(m["content"]) for m in msgs)
    if with_report:
        msgs.append({"role": "system", "content": "Evaluation report: " + rec["feedback"]})
    return msgs


def make_adapter(cand: str, train_items: list[dict], val_items: list[dict], hard_cap: int, out_root: Path):
    from skillopt.datasets.base import SplitDataLoader
    from skillopt.envs.base import EnvAdapter
    cfg_out_root = [str(out_root)]

    class _Loader(SplitDataLoader):
        def setup(self, cfg):  # in-memory splits: train = official train, val = dev, test = []
            self._splits = {"train": list(train_items), "val": list(val_items), "test": []}

    class AppWorldAdapter(EnvAdapter):
        def __init__(self):
            self.analyst_workers = 16
            self.failure_only = False
            self.minibatch_size = 8
            self.edit_budget = 4
            self.dataloader = _Loader(split_mode="split_dir", split_dir="(in memory)")

        def setup(self, cfg):
            super().setup(cfg)
            self.dataloader.setup(cfg)

        def get_dataloader(self):
            return self.dataloader

        def build_env_from_batch(self, batch, **kw):
            return list(batch.payload or [])

        def build_train_env(self, batch_size, seed, **kw):
            return self.build_env_from_batch(self.dataloader.build_train_batch(batch_size=batch_size, seed=seed))

        def build_eval_env(self, env_num, split, seed, **kw):
            if split not in ("valid_seen", "val"):
                raise PermissionError(f"SkillOpt asked for split {split!r}: only train and dev exist here")
            return self.build_env_from_batch(self.dataloader.build_eval_batch(env_num=env_num, split=split, seed=seed))

        def rollout(self, env_manager, skill_content, out_dir, **kw):
            items = list(env_manager)
            if not items:
                return []
            split = items[0]["split"]
            cdir = E.materialize(cand, {"memory/playbook.md": skill_content or ""})
            # tag = the call site + step (SkillOpt's own dir layout), so only a resumed step is replayed
            tag = os.path.relpath(out_dir, cfg_out_root[0]) if cfg_out_root else "x"
            recs = E.evaluate(cand, cdir, [it["id"] for it in items], phase="P3", split=split, reuse=True,
                              hard_cap=hard_cap, tag=tag)
            out = []
            for it, r in zip(items, recs):
                n, passed = int(r.get("num_tests") or 0), int(r.get("pass_count") or 0)
                res = {"id": it["id"], "hard": 1 if r["reward"] >= 1.0 else 0,
                       "soft": (passed / n) if n else float(r["reward"]),
                       "instruction": it["instruction"], "task_description": it["instruction"],
                       "task_type": "appworld", "n_turns": int(r.get("n_steps") or 0)}
                if split == "train":
                    reqs = r.get("failed_requirements") or []
                    res["fail_reason"] = ("" if res["hard"] else
                                          ("lint_reject: skill rejected by the length lint" if r.get("lint_reject") else
                                           f"failed_checks: {len(reqs)} of {n} requirement checks failed"))
                    d = Path(out_dir) / "predictions" / it["id"]
                    d.mkdir(parents=True, exist_ok=True)
                    (d / "conversation.json").write_text(json.dumps(
                        _conversation(r, with_report=bool(kw.get("use_eval_feedback", True))), ensure_ascii=False))
                out.append(res)
            return out

        def get_task_types(self):
            return ["appworld"]

    return AppWorldAdapter()


def _items(split: str, ids: list[str]) -> list[dict]:
    root = P.ROOT_OPT / "data" / "tasks"
    return [{"id": t, "split": split, "instruction": json.loads((root / t / "specs.json").read_text())["instruction"]}
            for t in ids]


def build_cfg(out_root: Path, train_n: int, epochs: int, batch_size: int = 40) -> dict:
    import argparse
    import train as skillopt_train
    yml = (HERE / "appworld.yaml").read_text().replace("@SKILLOPT@", str(SKILLOPT))
    cfgp = STATE / "appworld.resolved.yaml"
    cfgp.parent.mkdir(parents=True, exist_ok=True)
    cfgp.write_text(yml)
    argv0, sys.argv = sys.argv, ["train.py", "--config", str(cfgp)]
    try:
        ns = skillopt_train.parse_args()
    finally:
        sys.argv = argv0
    cfg = skillopt_train.load_config(ns)
    cfg.update({"out_root": str(out_root), "skill_init": str(STATE / "no_initial_skill.md"), "train_size": train_n,
                "num_epochs": epochs, "batch_size": batch_size, "eval_test": False, "test_env_num": 0,
                "optimizer_model": P.OPT_MODEL, "optimizer_backend": "openai_compatible",
                "target_backend": "openai_compatible"})
    return cfg


def train(cfg: dict, adapter) -> dict:
    from skillopt.engine.trainer import ReflACTTrainer
    patch_optimizer(CAND)
    return ReflACTTrainer(cfg, adapter).train()


def checkpoint(what: str, kind: str = "result", next_unit: str | None = None) -> None:
    import status_doc
    hist = P.read_json(OUT_ROOT / "history.json", []) or []
    rows = [{k: h.get(k) for k in ("step", "epoch", "action", "selection_hard", "selection_soft", "accepted", "skill_len")
             if k in h} for h in hist]
    t = opt_llm.totals(CAND)
    best = (OUT_ROOT / "best_skill.md")
    prog = {"candidate": CAND, "epochs": NUM_EPOCHS, "rows": rows, "counted_rollouts": E.counted(CAND),
            "cap": P.BUDGET_ROLLOUTS, "best_skill_chars": len(best.read_text()) if best.exists() else 0,
            "optimizer": {**t, "proxy_usd": opt_llm.proxy_usd(t)}}
    P.write_json(P.PUSHED / CAND / "progress.json", prog)
    status_doc.append(kind, "P3", f"{CAND} search",
                      f"SkillOpt {what}: {len(rows)} steps on record; best skill {prog['best_skill_chars']:,} chars.\n"
                      f"Counted rollouts {prog['counted_rollouts']}/{P.BUDGET_ROLLOUTS}; optimizer {t['calls']} calls, "
                      f"{t['prompt_tokens'] / 1e6:.2f}M in / {t['completion_tokens'] / 1e6:.2f}M out tok, "
                      f"${opt_llm.proxy_usd(t)} proxy.",
                      done_through=f"{CAND}/search/{what}", next_unit=next_unit or f"{CAND}/search",
                      extra={"candidate": CAND, "counts": {CAND: {"counted_rollouts": prog["counted_rollouts"]}},
                             "spend": {CAND: {"in": t["prompt_tokens"], "out": t["completion_tokens"],
                                              "proxy_usd": opt_llm.proxy_usd(t)}}},
                      artifacts=[f"STATE/{CAND}/progress.json"], subject=f"{CAND} {what}")


def search() -> int:
    import threading
    pidf = P.AW_STATE / "RUNNING.pid"
    pidf.write_text(f"{os.getpid()} {CAND} search\n")
    stop = threading.Event()

    def beat():  # one checkpoint per new history row (SkillOpt step), checked every 60 s
        seen = len(P.read_json(OUT_ROOT / "history.json", []) or [])
        while not stop.wait(60):
            n = len(P.read_json(OUT_ROOT / "history.json", []) or [])
            if n > seen:
                seen = n
                try:
                    checkpoint(f"step {n}")
                except Exception as e:  # noqa: BLE001
                    P.progress_log(CAND, "P3", f"checkpoint error {e}"[:300])

    th = threading.Thread(target=beat, daemon=True)
    th.start()
    try:
        tr, dv = _items("train", E.split_ids("train")), _items("dev", E.split_ids("dev"))
        cfg = build_cfg(OUT_ROOT, len(tr), NUM_EPOCHS)
        P.write_json(STATE / "cfg.json", {k: v for k, v in cfg.items() if "key" not in k.lower()})
        try:
            train(cfg, make_adapter(CAND, tr, dv, P.BUDGET_ROLLOUTS, OUT_ROOT))
            end = "done"
        except (E.BudgetExceeded, opt_llm.BudgetExceeded) as e:
            end = f"stopped at the cap ({e})"
            P.progress_log(CAND, "P3", end)
        stop.set()
        P.write_json(STATE / "search_end.json", {"end": end, "utc": P.utcnow()})
        checkpoint("search finished: " + end.split(" (")[0], kind="phase_done", next_unit=f"{CAND}/freeze")
        return 0
    finally:
        stop.set()
        pidf.unlink(missing_ok=True)


def accept() -> int:
    """1 step on 4 dev tasks (3 as train, 1 as val), throwaway (AW_CAND=acc_skillopt), not counted."""
    dev = E.split_ids("dev")
    out_root = STATE / "accept_out"
    shutil.rmtree(out_root, ignore_errors=True)
    tr, dv = _items("train", dev[:3]), _items("dev", dev[3:4])
    cfg = build_cfg(out_root, len(tr), 1, batch_size=3)
    cfg.update({"use_slow_update": False, "use_meta_skill": False})
    patch_optimizer(CAND)
    ad = make_adapter(CAND, tr, dv, 100, out_root)
    train(cfg, ad)
    calls = P.read_jsonl(opt_llm.usage_path(CAND))
    hist = P.read_json(out_root / "history.json", []) or []
    convs = list(out_root.rglob("conversation.json"))
    report = any(json.loads(c.read_text())[-1]["role"] == "system" for c in convs)
    big = "- rule\n" * 9000  # ~54,000 chars: over the memory lint
    over = E.evaluate(CAND, E.materialize(CAND, {"memory/playbook.md": big}), dev[:1], phase="A", split="dev")[0]
    llm_text = (STATE / "llm_calls.jsonl").read_text() if (STATE / "llm_calls.jsonl").exists() else ""
    res = {"optimizer_calls": len(calls), "errors": sum(1 for c in calls if c.get("error")),
           "stages": sorted({c["role"] for c in calls}), "steps": len(hist),
           "conversations": len(convs), "eval_report_in_conversation": report,
           "over_cap_rejected": bool(over.get("lint_reject")), "hidden_reference_absent": "Hidden Reference" not in llm_text,
           "best_skill_exists": (out_root / "best_skill.md").exists()}
    res["ok"] = (res["optimizer_calls"] >= 1 and res["errors"] == 0 and res["conversations"] >= 1 and report
                 and res["over_cap_rejected"] and res["hidden_reference_absent"] and res["best_skill_exists"])
    P.write_json(P.AW_STATE / "acceptance" / "a_skillopt.json", res)
    print(json.dumps(res))
    return 0 if res["ok"] else 1


def freeze() -> int:
    best = OUT_ROOT / "best_skill.md"
    text = best.read_text() if best.exists() else ""
    rs = P.read_json(OUT_ROOT / "runtime_state.json", {}) or {}
    hist = P.read_json(OUT_ROOT / "history.json", []) or []
    inert = not text.strip() or not any(h.get("accepted") for h in hist)
    cdir = E.materialize(CAND, {"memory/playbook.md": text})
    v = E.lint(cdir)
    if v:
        raise SystemExit(f"best skill fails the lint: {v}")
    art = P.PUSHED / CAND / "artifact"
    shutil.rmtree(art, ignore_errors=True)
    for rel, t in E.read_surfaces(cdir).items():
        (art / rel).parent.mkdir(parents=True, exist_ok=True)
        (art / rel).write_text(t)
    (art / "memory").mkdir(exist_ok=True)
    P.write_json(art / "FREEZE.json", {"candidate": CAND, "label": "inert" if inert else "",
                                       "best_score": rs.get("best_score"), "steps": len(hist),
                                       "memory_chars": len(text), "memory_tokens": E.memory_tokens(text),
                                       "tree_sha256": P.sha256_tree(cdir)})
    print(json.dumps(P.read_json(art / "FREEZE.json")))
    return 0


if __name__ == "__main__":
    raise SystemExit({"search": search, "accept": accept, "freeze": freeze}[sys.argv[1]]())
