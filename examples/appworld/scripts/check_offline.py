"""Acceptance checks that need no model call (plan §11): A3, A4 (prompt part), A5, A6.

  venv-aw/bin/python -I check_offline.py a3|a4|a5|a6
Each world-touching check runs in its own subprocess (one live world per process). Dev / train ids are
used per rule S1; nothing is counted. Prints a JSON summary (flags and counts only).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
sys.path.insert(0, str(EX / "adapters"))
import awpaths as P  # noqa: E402

os.environ["APPWORLD_ROOT"] = str(P.ROOT_OPT)
os.environ.setdefault("OPENAI_API_KEY", "unused")


def sub(name: str, *args) -> dict:
    r = subprocess.run([str(P.VENV_PY), "-I", __file__, name, *args], capture_output=True, text=True,
                       env={**os.environ, "APPWORLD_ROOT": str(P.ROOT_OPT)}, cwd=str(P.AW_STATE))
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        return {"error": r.stderr[-800:]}


def _world(task_id: str, exp: str, harden: bool):
    from appworld import AppWorld
    from appworld.common import safety_guard
    import aw_agent
    if harden:
        safety_guard.ALLOWED_MODULE_NAMES.difference_update(aw_agent.F1_REMOVED_MODULES)
    out = Path(P.ROOT_OPT) / "experiments" / "outputs"
    if not out.exists():
        (P.SCRATCH / "root_opt").mkdir(parents=True, exist_ok=True)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.symlink_to(P.SCRATCH / "root_opt", target_is_directory=True)
    return AppWorld(task_id=task_id, experiment_name=exp, random_seed=100, raise_on_extra_parameters=True)


def _cleanup(exp: str):
    import shutil
    shutil.rmtree((P.SCRATCH / "root_opt" / exp).resolve(), ignore_errors=True)


def repl_probe(harden: str) -> dict:
    from appworld.task import load_task_ids
    t = load_task_ids("dev")[0]
    gt = P.ROOT_OPT / "data" / "tasks" / t / "ground_truth" / "answer.json"
    probes = {
        "import_os": "import os\nprint(os.listdir('/'))",
        "open_answer": f"print(open('{gt}').read())",
        "pathlib_read": f"import pathlib\nprint(pathlib.Path('{gt}').read_text())",
        "io_open": f"import io\nprint(io.open('{gt}').read())",
    }
    res = {}
    with _world(t, "accept/a3", harden == "1") as w:
        for k, code in probes.items():
            out = w.execute(code)
            leaked = gt.exists() and gt.read_text().strip()[:20] in out and len(gt.read_text().strip()) > 3
            blocked = ("not allowed" in out.lower() or "error" in out.lower() or "prohibited" in out.lower()
                       or "unsafe" in out.lower()) and not leaked
            res[k] = {"blocked": blocked}
    _cleanup("accept/a3")
    return res


def a3() -> dict:
    hard = sub("_repl", "1")
    soft = sub("_repl", "0")
    r = subprocess.run(["python3", "-I", str(EX / "scripts" / "make_roots.py"), "--check"], capture_output=True, text=True)
    roots = json.loads(r.stdout.strip().splitlines()[-1])
    res = {"hardened": hard, "unhardened_for_reference": soft, "roots": roots,
           "root_full_readable": os.access(P.ROOT_FULL, os.R_OK)}
    res["ok"] = all(v.get("blocked") for v in hard.values() if isinstance(v, dict)) and len(hard) == 4 \
        and roots["ok"] and not res["root_full_readable"]
    return res


def first_request(cap: str, stock: str) -> dict:
    """Render the agent's first request without any model call (dummy client env)."""
    os.environ["MODEL_SERVER_URL"] = "http://unused.invalid"
    os.environ["RITS_API_KET"] = "unused"
    from appworld.task import load_task_ids
    import aw_agent
    t = load_task_ids("dev")[0]
    if stock == "1":
        from appworld_agents.code.simplified.react_code_agent import SimplifiedReActCodeAgent
        agent = SimplifiedReActCodeAgent(prompt_file_path=str(P.APPWORLD_SRC / "experiments/prompts/react_code_agent/instructions.txt"),
                                         model_config=aw_agent.model_config(), max_output_length=60000,
                                         ignore_multiple_calls=True, logger_config={"color": False, "verbose": False})
    else:
        agent = aw_agent.make_agent_class()(capability_dir=cap, model_config=aw_agent.model_config(),
                                            max_output_length=60000, ignore_multiple_calls=True,
                                            logger_config={"color": False, "verbose": False})
    with _world(t, f"accept/a4{stock}", False) as w:
        agent.initialize(w)
        msgs = [{"role": m["role"], "content": m["content"]} for m in agent.trimmed_messages]
    _cleanup(f"accept/a4{stock}")
    return {"sha256": P.sha256_bytes(json.dumps(msgs).encode()), "n": len(msgs),
            "last_has_memory": aw_agent.MEMORY_HEADING in msgs[-1]["content"],
            "memory_before_name": (msgs[-1]["content"].find(aw_agent.MEMORY_HEADING) <
                                   msgs[-1]["content"].rfind("My name is: ")) if aw_agent.MEMORY_HEADING in msgs[-1]["content"] else None}


def a4() -> dict:
    import shutil
    import tempfile
    import lints
    stock = sub("_first", "", "1")
    seed = sub("_first", str(EX / "seed_capability"), "0")
    with tempfile.TemporaryDirectory() as td:
        cap = Path(td) / "cap"
        shutil.copytree(EX / "seed_capability", cap)
        (cap / "memory" / "playbook.md").write_text((EX / "ace/vendor/playbooks/appworld_initial_playbook.txt").read_text())
        mem = sub("_first", str(cap), "0")
    res = {"seed_identical_to_stock": stock.get("sha256") == seed.get("sha256") and stock.get("n") == seed.get("n"),
           "n_messages": stock.get("n"), "memory_slot": mem}
    m_cap = P.manifest().get("m_cap", {}).get("value")
    if m_cap:
        big = "## OTHERS\n" + "\n".join(f"[misc-{i:05d}] Always paginate list endpoints until an empty page appears."
                                        for i in range(1, 4000))
        while lints.count_tokens(big) > m_cap + 1:
            big = big.rsplit("\n", 1)[0]
        while lints.count_tokens(big) < m_cap + 1:
            big += " x"
        res["over_cap"] = {"tokens": lints.count_tokens(big), "m_cap": m_cap,
                           "refused": not lints.memory_lint(big, m_cap)["ok"]}
    res["ok"] = res["seed_identical_to_stock"] and mem.get("last_has_memory") and mem.get("memory_before_name") \
        and (res.get("over_cap", {}).get("refused", True))
    res["m_cap_part_done"] = bool(m_cap)
    return res


def score_probe() -> dict:
    from appworld.task import load_task_ids
    from appworld.common.utils import import_module_file  # type: ignore[attr-defined]
    import adapter
    t = load_task_ids("train")[0]
    out = {}
    for mode in ("solution", "noop", "solution2"):
        with _world(t, f"accept/a5{mode}", True) as w:
            if mode.startswith("solution"):
                mod = import_module_file(str(P.ROOT_OPT / "data/tasks" / t / "ground_truth/compiled_solution.py"), force=True)
                mod.solution(w.apis, w.requester)
            d = w.evaluate().to_dict()
        _cleanup(f"accept/a5{mode}")
        rec = {"success": bool(d["success"]),
               "failed_requirements": [{"requirement": f.get("requirement"), "label": f.get("label")} for f in d["failures"]]}
        out[mode] = {"reward": adapter.score(rec), "record_has_trace": "trace" in json.dumps(rec)}
    return out


def a5() -> dict:
    r = sub("_score")
    res = {"probe": r, "solution_reward": r.get("solution", {}).get("reward"), "noop_reward": r.get("noop", {}).get("reward")}
    res["ok"] = res["solution_reward"] == 1.0 and res["noop_reward"] == 0.0 and \
        r.get("solution2", {}).get("reward") == 1.0 and not any(v.get("record_has_trace") for v in r.values())
    return res


def a6() -> dict:
    import adapter
    train = adapter.tasks("train")
    raw = [x for x in (P.ROOT_OPT / "data/datasets/train.txt").read_text().split() if x]
    res = {"train_matches_file": train == raw and len(train) == 90}
    try:
        adapter.tasks("test_normal")
        res["test_split_sealed"] = False
    except adapter.Sealed:
        res["test_split_sealed"] = True
    test_id = json.loads(P.LINT_CACHE.read_text())["test_ids"][0]
    try:
        adapter.check_seal(test_id)
        res["test_id_sealed"] = False
    except adapter.Sealed:
        res["test_id_sealed"] = True
    res["ok"] = all(res.values())
    return res


def main() -> int:
    cmd = sys.argv[1]
    if cmd == "_repl":
        print(json.dumps(repl_probe(sys.argv[2])))
        return 0
    if cmd == "_first":
        print(json.dumps(first_request(sys.argv[2], sys.argv[3])))
        return 0
    if cmd == "_score":
        print(json.dumps(score_probe()))
        return 0
    res = globals()[cmd]()
    P.write_json(P.AW_STATE / "acceptance" / f"{cmd}.json", res)
    print(json.dumps(res))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
