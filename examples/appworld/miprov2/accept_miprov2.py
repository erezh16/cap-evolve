"""A-miprov2 (docs/EVAL_APPWORLD_REST.md §9.2): run by `run_miprov2.py accept` as candidate "miprov2_accept".

All episodes use phase "accept" (never counted, separate cache namespace). Uses only dev ids, and only dev
records already in the accept cache of the seed, plus 2 fresh dev episodes for item 2. Prints counts and
verdicts only: no task id, task text or trajectory text.
"""

from __future__ import annotations

import json
import os
import random
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("AW_MIPRO_CAND", "miprov2_accept")
import run_miprov2 as R  # noqa: E402
import dspy  # noqa: E402

E, P, opt_llm = R.E, R.P, R.opt_llm
OUT: dict = {}


def cached_seed_dev(n: int) -> list[str]:
    h = E.seed_hash()
    return [t for t in E.split_ids("dev") if E._cache_path(h, t, P.SEARCH_SEED_BASE, "accept").exists()][:n]


def item1() -> None:
    c0 = E.materialize(R.CAND, R.program_files(R.STOCK_INSTRUCTION))
    demos = [{"task": f"Find <item {k}> in <app> for <friend's name> and report <the value>.",
              "solution": "pw = apis.supervisor.show_account_passwords()\n# log in, look up, then\n"
                          "apis.supervisor.complete_task(answer=result)"} for k in range(3)]
    ins = "You are an autonomous assistant. Complete the supervisor's task by calling app APIs from Python."
    v = R.lint_text(ins, demos)
    text = R.render(ins, demos)
    OUT["1"] = {"candidate0_equals_seed_hash": E.tree_hash(c0) == E.seed_hash(),
                "candidate0_byte_identical": R.render(R.STOCK_INSTRUCTION) == R.STOCK,
                "dummy_lint_violations": v, "dummy_prompt_tokens": R._tok(text),
                "final_block_kept": text.rstrip().endswith("Task: {{ instruction }}"),
                "demo_before_key_instructions": text.index("Here is another example task") < text.index(R._DEMO_ANCHOR)}
    OUT["1"]["pass"] = (OUT["1"]["candidate0_equals_seed_hash"] and OUT["1"]["candidate0_byte_identical"]
                        and not v and OUT["1"]["final_block_kept"] and OUT["1"]["demo_before_key_instructions"])


def item2(records: dict[str, dict]) -> None:
    ids = [t for t in E.split_ids("dev")][:2]
    recs = E.evaluate(R.CAND, E.materialize(R.CAND, {}), ids, phase="accept", tag="instructions")  # seed: cache or fresh
    by_ins = {r["instruction"]: [r["task_id"]] for r in recs}
    agent = R.AppWorldAgent(by_ins, phase="accept")
    agent.agent.signature = agent.agent.signature.with_instructions(
        R.STOCK_INSTRUCTION + "\n\nWork carefully and verify each API's specification before calling it.")
    preds = [agent(task=r["instruction"]) for r in recs]
    after = E.evaluate(R.CAND, agent.candidate_dir(), ids, phase="accept", tag="check")
    OUT["2"] = {"rewards": [p.reward for p in preds], "records_ok": all(r.get("error") is None for r in after),
                "fresh_then_cached": all(r.get("cache_hit") for r in after),
                "steps": [r.get("n_steps") for r in after], "seconds": [r.get("episode_seconds") for r in after]}
    OUT["2"]["pass"] = OUT["2"]["records_ok"] and OUT["2"]["fresh_then_cached"] and len(preds) == 2


def item3() -> None:
    seen = []
    real = urllib.request.urlopen

    def hook(req, *a, **k):
        body = json.loads(req.data)
        hdr = {k_.lower() for k_ in req.headers}
        seen.append({"keys": sorted(body), "has_temperature": "temperature" in body, "has_top_p": "top_p" in body,
                     "has_response_format": "response_format" in body, "has_tools": "tools" in body,
                     "guru_header_sent": "x-context-guru-token" in hdr, "model": body.get("model")})
        return real(req, *a, **k)

    urllib.request.urlopen = hook
    try:
        R.configure()
        lm = R.GatewayLM().copy(rollout_id=7, temperature=1.0)            # exactly what GroundedProposer does
        from dspy.propose.grounded_proposer import generate_instruction_class
        with dspy.context(lm=lm):
            out = generate_instruction_class()(dataset_description="Tasks for a personal assistant over apps.",
                                               program_code="AppWorldAgent", program_description="An app agent.",
                                               module="Predict(task) -> solution", module_description="Writes code.",
                                               task_demos="No task demos provided.", previous_instructions="",
                                               basic_instruction=R.STOCK_INSTRUCTION, tip="Keep it concise.")
        with dspy.context(lm=R.GatewayLM()):
            dspy.Predict("question -> answer", n=1, temperature=1.0)(question="Reply with the word ok.")
    finally:
        urllib.request.urlopen = real
    OUT["3"] = {"requests": seen, "proposal_chars": len(out.proposed_instruction or "")}
    OUT["3"]["pass"] = bool(seen) and all(not s["has_temperature"] and not s["has_top_p"] and not s["has_response_format"]
                                          and s["guru_header_sent"] and s["model"] == P.OPT_MODEL for s in seen) \
        and OUT["3"]["proposal_chars"] > 0


def item4() -> None:
    ids = cached_seed_dev(10)
    recs = E.evaluate(R.CAND, E.materialize(R.CAND, {}), ids, phase="accept", tag="item4")
    assert all(r.get("cache_hit") for r in recs), "item 4 must use cached records only"
    ids_of: dict[int, str] = {}
    exs, by_ins = R.examples_for(recs, ids_of)
    R.configure()
    # demos: 3 condensed demos from successful (accept-namespace) seed dev records
    pool = R.build_demo_pool([r for r in recs if r["reward"] == 1.0][:4], R.ST / "demo_pool_accept.json")
    stats = (P.read_json(R.ST / "demo_pool_accept.json") or {}).get("_stats", {})
    demos = list(pool.values())[:3]
    demo_lint = [R.lint_text(R.STOCK_INSTRUCTION, [d]) for d in demos]
    demo_tokens = [R._tok(R.render_demo(d)) for d in demos]
    # dataset summary: the prompt holds instructions only (no ids, contacts); its output must lint clean
    import status_doc as S
    from dspy.propose.dataset_summary_generator import order_input_keys_in_string, create_dataset_summary
    prompt_text = order_input_keys_in_string(exs[0:10].__repr__())
    pv = [x for x in S.violations(prompt_text) if x in ("task_id", "supervisor_contact", "env_string")]
    summary = create_dataset_summary(trainset=exs, view_data_batch_size=10, prompt_model=dspy.settings.lm)
    sv = R.lint_text(summary)
    # proposals: GroundedProposer exactly as AWMIPROv2 builds it, N = 4 (candidate 0 + 3 proposals)
    demo_sets = {0: [[], [dspy.Example(augmented=True, **d) for d in demos], [dspy.Example(augmented=True, **demos[0])],
                     [dspy.Example(augmented=True, **d) for d in demos[1:]]]}
    opt = R.AWMIPROv2(metric=R.metric, prompt_model=R.GatewayLM(), task_model=R.NeverLM(), max_bootstrapped_demos=3,
                      max_labeled_demos=0, auto=None, num_candidates=4, seed=9, demo_pool=pool, ids_of=ids_of,
                      proposals_path=R.ST / "proposals_accept.json")
    opt.rng = random.Random(9)
    (R.ST / "proposals_accept.json").unlink(missing_ok=True)
    prog = R.AppWorldAgent(by_ins, phase="accept")
    cands = opt._propose_instructions(prog, exs, demo_sets, 10, True, True, True, True, num_instruct_candidates=4)
    props = cands[0][1:]
    prop_lint = [R.lint_text(t) for t in props]
    OUT["4"] = {"records_cached": len(recs), "demos": len(demos), "demo_pool_stats": stats,
                "demo_lint_violations": [len(v) for v in demo_lint], "demo_tokens": demo_tokens,
                "dataset_prompt_id_or_contact_hits": pv, "summary_lint_violations": len(sv),
                "summary_chars": len(summary), "proposals": len(props),
                "proposal_lint_violations": [len(v) for v in prop_lint],
                "proposal_chars": [len(t) for t in props], "proposal_stats": opt.proposal_stats,
                "candidate0_is_stock": cands[0][0] == R.STOCK_INSTRUCTION}
    OUT["4"]["pass"] = (len(demos) == 3 and not any(demo_lint) and all(n <= R.DEMO_MAX_TOKENS for n in demo_tokens)
                        and not pv and not sv and len(props) == 3 and not any(prop_lint)
                        and OUT["4"]["candidate0_is_stock"])


def item5() -> None:
    """Stub-metric dry run, N=3, T=3, minibatch 5 (no episodes, no LM): requested episodes = arithmetic."""
    calls = []
    real_eval = E.evaluate

    def stub(cand, cdir, ids, *, phase, tag="", **k):
        calls.append(len(ids))
        rnd = random.Random(hash((str(cdir), tuple(ids))) & 0xffff)
        return [{"task_id": t, "reward": float(rnd.random() < 0.4)} for t in ids]

    class StubLM(R.GatewayLM):
        def forward(self, prompt=None, messages=None, **kw):
            import re
            f = re.findall(r"\[\[ ## (\w+) ## \]\]\n\{", messages[0]["content"])
            outs = [x for x in f if x in ("observations", "summary", "program_description", "module_description",
                                          "proposed_instruction")]
            return {"choices": [{"message": {"role": "assistant", "content": "".join(
                f"[[ ## {x} ## ]]\nstub {x}\n\n" for x in outs) + "[[ ## completed ## ]]"}}], "usage": {}, "model": "m"}

    E.evaluate, lint_real = stub, R.lint_text
    R.lint_text = lambda ins, demos=(): []
    try:
        R.configure(StubLM())
        ids_of: dict[int, str] = {}
        train = [{"task_id": f"tr{i}", "instruction": f"stub train {i}", "reward": float(i % 2)} for i in range(20)]
        dev = [{"task_id": f"dv{i}", "instruction": f"stub dev {i}", "reward": 0.0} for i in range(12)]
        trs, _ = R.examples_for(train, ids_of)
        vs, by_ins = R.examples_for(dev, ids_of)
        R.BatchEvaluate.ids_of, R.BatchEvaluate.phase = ids_of, "accept"
        R.BatchEvaluate.log = R.ST / "evals_stub.jsonl"
        R.MV2.Evaluate = R.BatchEvaluate
        pp = R.ST / "proposals_stub.json"
        pp.unlink(missing_ok=True)
        opt = R.AWMIPROv2(metric=R.metric, prompt_model=StubLM(), task_model=R.NeverLM(), max_bootstrapped_demos=3,
                          max_labeled_demos=0, auto=None, num_candidates=3, num_threads=4, seed=9,
                          demo_pool={r["task_id"]: {"task": "<t>", "solution": "x = 1"} for r in train if r["reward"]},
                          ids_of=ids_of, proposals_path=pp)
        best = opt.compile(R.AppWorldAgent(by_ins, phase="accept"), trainset=trs, valset=vs, num_trials=3,
                           minibatch=True, minibatch_size=5, minibatch_full_eval_steps=5)
        dspy_total = max(v.get("total_eval_calls_so_far", 0) for v in best.trial_logs.values())
    finally:
        E.evaluate, R.lint_text = real_eval, lint_real
    exp = R.expected_eval_calls(3, 5, 5, 12)
    OUT["5"] = {"requested_episodes": sum(calls), "eval_calls": calls, "dspy_total_eval_calls": dspy_total,
                "arithmetic": exp}
    OUT["5"]["pass"] = sum(calls) == exp["dspy_total_eval_calls"] == dspy_total
    OUT["real_search_schedule"] = R.expected_eval_calls(16, 5, 35, 57)


def main() -> int:
    R.ST.mkdir(parents=True, exist_ok=True)
    only = os.environ.get("AW_ACCEPT_ITEMS", "1,2,3,4,5").split(",")
    for k, f in (("1", item1), ("5", item5), ("3", item3), ("4", item4), ("2", item2)):
        if k not in only:
            continue
        try:
            f(None) if k == "2" else f()
        except Exception as e:  # noqa: BLE001
            OUT[k] = {"pass": False, "error": f"{type(e).__name__}: {str(e)[:500]}"}
        print(f"A-miprov2 item {k}: {'PASS' if OUT[k].get('pass') else 'FAIL'}", flush=True)
    t = opt_llm.totals(R.CAND)
    OUT["optimizer_usage"] = {**t, "proxy_usd": opt_llm.proxy_usd(t)}
    OUT["accept_episodes_fresh"] = len(P.read_jsonl(P.AW_STATE / R.CAND / "accept_rollouts.jsonl"))
    P.write_json(R.ST / "accept_result.json", OUT)
    print(json.dumps(OUT, indent=1, default=str))
    return 0 if all(OUT.get(k, {}).get("pass") for k in only) else 1


if __name__ == "__main__":
    raise SystemExit(main())
