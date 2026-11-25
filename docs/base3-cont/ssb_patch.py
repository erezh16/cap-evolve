"""Project-local deviation for spreadsheetbench (docs/base3.md §2 'What to record'):
stamp episode_start/episode_end/episode_seconds, prompt/completion token sums and the
LLM-call count into every Rollout.metadata. Scoring, prompts and the sandbox are untouched."""
import sys, re
p = sys.argv[1]
s = open(p).read()
orig = s
# 1) accumulate where the adapter adds usage.total_tokens
old = "                tokens += usage.total_tokens if usage else 0\n"
assert s.count(old) == 1, "token line not unique"
s = s.replace(old, old +
"                _B3.calls += 1\n"
"                _B3.prompt += int(getattr(usage, 'prompt_tokens', 0) or 0) if usage else 0\n"
"                _B3.completion += int(getattr(usage, 'completion_tokens', 0) or 0) if usage else 0\n")
# 2) rename run_target -> _run_target_inner and add a wrapper
old = "    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:\n        \"\"\"Multi-round CodeAct loop"
assert s.count(old) == 1
s = s.replace(old,
"    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:\n"
"        \"\"\"base3 wrapper: per-episode wall time + prompt/completion tokens + LLM calls.\"\"\"\n"
"        import datetime as _dt, time as _time\n"
"        _B3.calls = _B3.prompt = _B3.completion = 0\n"
"        t0 = _time.time(); start = _dt.datetime.now(_dt.timezone.utc).isoformat()\n"
"        r = self._run_target_inner(task, ctx, seed=seed)\n"
"        t1 = _time.time()\n"
"        md = dict(r.metadata or {})\n"
"        md.update(episode_start=start, episode_end=_dt.datetime.now(_dt.timezone.utc).isoformat(),\n"
"                  episode_seconds=round(t1 - t0, 3), prompt_tokens=_B3.prompt,\n"
"                  completion_tokens=_B3.completion, llm_calls=_B3.calls)\n"
"        r.metadata = md\n"
"        return r\n\n"
"    def _run_target_inner(self, task: Task, ctx, *, seed: int = 0) -> Rollout:\n        \"\"\"Multi-round CodeAct loop")
# 3) thread-local counters
old = "# --- configuration -----------------------------------------------------------\n"
assert s.count(old) == 1
s = s.replace(old, "import threading as _b3_threading\n_B3 = _b3_threading.local()\n\n" + old)
open(p, "w").write(s)
print("patched", p, len(s) - len(orig), "bytes added")
