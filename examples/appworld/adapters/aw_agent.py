"""CapReActAgent and the one-episode worker (plan §5.1, §6.1, §7; base plan Appendix A F1, F2).

  venv-aw/bin/python -I aw_agent.py SPEC.json OUT.json

One process = one AppWorld world = one episode. SPEC keys:
  task_id, experiment_name, capability_dir, trial_seed, appworld_root,
  messages_out (optional: write the agent's final trimmed message list, the ACE Reflector input),
  max_steps (50), token_cap (100000), log_lm_calls (false; A2 turns it on to check key scrubbing)
OUT is a gold-free record: the evaluator's failure `trace` is never written.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import awpaths as P  # noqa: E402

MEMORY_HEADING = "Guidelines learned from past task attempts:"
FS_PROBE = ["ground_truth", "answer.json", "/data/tasks", "APPWORLD_ROOT", "root_full", "root_opt",
            "test_normal"]
F1_REMOVED_MODULES = {"os", "pathlib", "io", "shutil", "glob"}


def model_config() -> dict:
    """Plan §5.1 (identical for every arm and phase)."""
    return {
        "client_name": "litellm",
        "name": "hosted_vllm/openai/gpt-oss-120b-a100",
        "base_url": "{{MODEL_SERVER_URL}}/gpt-oss-120b-a100/v1",
        "api_key": "unused",
        "extra_headers_env": {"RITS_API_KEY": "RITS_API_KET"},
        "reasoning_effort": "medium",
        "temperature": 0,
        "max_completion_tokens": 6000,
        "drop_reasoning_content": True,
        "use_cache": False,
        "retry_after_n_seconds": 15,
        "max_retries": 20,
        "cost_per_token": {"input_cache_miss": 0.0, "input_cache_hit": 0.0, "input_cache_write": 0.0,
                           "output": 0.0},
    }


def insert_memory(content: str, memory: str) -> str:
    """Insert the memory block right before the final `My name is:` block (plan §6.1)."""
    i = content.rfind("My name is: ")
    if i < 0:
        raise ValueError("prompt has no 'My name is:' block")
    return content[:i] + f"{MEMORY_HEADING}\n{memory.strip()}\n\n" + content[i:]


def make_agent_class():
    from appworld_agents.code.simplified.react_code_agent import SimplifiedReActCodeAgent

    class CapReActAgent(SimplifiedReActCodeAgent):
        """Overrides only initialize(): the prompt comes from the capability, plus the memory slot."""

        def __init__(self, capability_dir: str, **kwargs):
            cap = Path(capability_dir)
            super().__init__(prompt_file_path=str(cap / "policy" / "instructions.txt"), **kwargs)
            pb = cap / "memory" / "playbook.md"
            self.memory = pb.read_text() if pb.exists() else ""

        def initialize(self, world) -> None:
            super().initialize(world)
            if self.memory.strip():
                last = self.messages[self.num_instruction_messages - 1]
                last["content"] = insert_memory(last["content"], self.memory)

    return CapReActAgent


def classify_lm_error(msg: str) -> str:
    low = msg.lower()
    if "context length" in low or "context window" in low or "contextwindowexceeded" in low \
            or "maximum context" in low or "too long" in low:
        return "context_exceeded"
    return "lm_error"


def run(spec: dict) -> dict:
    t0 = time.time()
    root = spec["appworld_root"]
    os.environ["APPWORLD_ROOT"] = root
    os.environ["OPENAI_API_KEY"] = "unused"
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    # AppWorld's native outputs go to the /tmp scratch (plan §4), via a symlink in the root
    out_link = Path(root) / "experiments" / "outputs"
    scratch = P.SCRATCH / Path(root).name
    scratch.mkdir(parents=True, exist_ok=True)
    if not out_link.exists():
        out_link.parent.mkdir(parents=True, exist_ok=True)
        try:
            out_link.symlink_to(scratch, target_is_directory=True)
        except FileExistsError:
            pass
    env = P.read_env_file()
    os.environ["MODEL_SERVER_URL"] = env["RITS_URL"].rstrip("/")
    os.environ["RITS_API_KET"] = env["RITS_API_KET"]

    from appworld import AppWorld
    from appworld.common import safety_guard
    safety_guard.ALLOWED_MODULE_NAMES.difference_update(F1_REMOVED_MODULES)  # F1 (a)

    CapReActAgent = make_agent_class()
    seed = int(spec["trial_seed"])
    agent = CapReActAgent(
        capability_dir=spec["capability_dir"],
        model_config=model_config(),
        appworld_config={"random_seed": seed, "raise_on_extra_parameters": True},
        logger_config={"color": False, "verbose": False},
        usage_tracker_config={"max_cost_overall": 1000, "max_cost_per_task": 10,
                              "max_output_tokens_per_task": 100000},
        ignore_multiple_calls=True,
        max_prompt_length=None,
        max_output_length=60000,
        max_steps=int(spec.get("max_steps", 50)),
        log_lm_calls=bool(spec.get("log_lm_calls", False)),
    )
    del os.environ["RITS_API_KET"]  # F1 (b): the client holds the header; the world never sees the key

    token_cap = int(spec.get("token_cap", 100000))
    task_id = spec["task_id"]
    rec = {"task_id": task_id, "experiment_name": spec["experiment_name"], "trial_seed": seed,
           "playbook_sha256": P.sha256_bytes(agent.memory.encode()) if agent.memory.strip() else None,
           "infra_error": False, "error": None}
    prompt_tokens, completion_tokens, codes = [], 0, []
    max_trims = 0
    termination = "step_cap"
    first_request = None
    with AppWorld(task_id=task_id, experiment_name=spec["experiment_name"], random_seed=seed,
                  raise_on_extra_parameters=True) as world:
        agent.usage_tracker.reset(task_id)
        agent.initialize(world)
        outputs = []
        try:
            for _ in range(agent.max_steps):
                agent.step_number += 1
                tm = agent.trimmed_messages
                if first_request is None:
                    first_request = [{"role": m["role"], "content": m["content"]} for m in tm]
                trims = sum(m["content"].count("[NOT SHOWN FOR BREVITY]") +
                            m["content"].count("[TRIMMED HISTORY]") for m in tm if m.get("content"))
                max_trims = max(max_trims, trims)
                inputs, usage, status = agent.next_execution_inputs_usage_and_status(outputs)
                if status.failed:
                    termination = classify_lm_error(status.message)
                    rec["error"] = status.message[:500]
                    break
                tok = usage.tokens
                prompt_tokens.append(int(tok.input_cache_miss + tok.input_cache_hit + tok.input_cache_write))
                completion_tokens += int(tok.output)
                codes += [i.content for i in inputs]
                outs = world.batch_execute([i.content for i in inputs])
                from appworld_agents.code.simplified.agent import ExecutionIO
                outputs = [ExecutionIO(content=o, metadata=i.metadata) for i, o in zip(inputs, outs, strict=True)]
                agent.usage_tracker.add(task_id, usage)
                if world.task_completed():
                    termination = "completed"
                    break
                if agent.usage_tracker.exceeded(task_id):
                    termination = "cost_cap"
                    break
                if completion_tokens >= token_cap:  # F2: enforced here
                    termination = "token_cap"
                    break
        except Exception as e:  # provider failure after the client's retries, or a client crash
            termination = "infra_error"
            rec["infra_error"] = True
            rec["error"] = f"{type(e).__name__}: {str(e)[:400]}"
        final_messages = [{"role": m["role"], "content": m["content"]} for m in agent.trimmed_messages]
        tracker = world.evaluate()
        out_dir = world.output_directory if hasattr(world, "output_directory") else None
    d = tracker.to_dict()
    failures = [{"requirement": f.get("requirement"), "label": f.get("label")} for f in d["failures"]]
    rec.update({
        "success": bool(d["success"]), "pass_count": len(d["passes"]), "num_tests": d["num_tests"],
        "difficulty": d.get("difficulty"),
        "failed_requirements": failures,
        "no_collateral_damage": not any(f["label"] == "no_op_pass" for f in failures),
        "steps": agent.step_number, "termination": termination,
        "prompt_tokens_max": max(prompt_tokens) if prompt_tokens else 0,
        "prompt_tokens_sum": sum(prompt_tokens), "prompt_tokens_per_step": prompt_tokens,
        "completion_tokens": completion_tokens, "max_trims": max_trims,
        "fs_probe": sorted({p for p in FS_PROBE for c in codes if p in c}),
        "complete_task_called": any("complete_task" in c for c in codes),
        "wall_s": round(time.time() - t0, 1),
        "native_output_dir": out_dir,
    })
    if spec.get("messages_out"):
        P.write_json(spec["messages_out"], final_messages)
    if spec.get("first_request_out"):
        P.write_json(spec["first_request_out"], first_request)
    return rec


def main() -> int:
    spec = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2])
    try:
        rec = run(spec)
    except Exception as e:
        rec = {"task_id": spec.get("task_id"), "experiment_name": spec.get("experiment_name"),
               "infra_error": True, "termination": "infra_error", "success": False,
               "error": f"worker crash {type(e).__name__}: {str(e)[:400]}",
               "traceback_tail": traceback.format_exc()[-1500:]}
    # the record never holds the RITS key (A2 greps for it)
    key = P.read_env_file().get("RITS_API_KET")
    text = json.dumps(rec, indent=1)
    if key and key in text:
        text = text.replace(key, "<redacted>")
    P.atomic_write(out, text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
