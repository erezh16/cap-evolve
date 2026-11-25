"""base3 deviation (infra robustness only): make spreadsheetbench's LLM call WAIT through gateway refusals /
network loss instead of failing the episode at once. Retries the SAME request (same messages, seed, kwargs) on
403/401/429/5xx/connection/timeout errors, every 60 s, for up to 12 h; other errors (e.g. 400 bad request) still
fail as before. Prompts, turns, sandbox and scoring are unchanged."""
import sys
p = sys.argv[1]; s = open(p).read()
old = """                try:
                    response = litellm.completion(
                        model=model_config.MODEL,
                        messages=messages,
                        seed=seed,
                        **model_config.llm_kwargs(),
                    )
                except Exception as e:  # noqa: BLE001"""
assert s.count(old) == 1, "completion call not found"
new = """                try:
                    response = _b3_wait_completion(
                        litellm,
                        model=model_config.MODEL,
                        messages=messages,
                        seed=seed,
                        **model_config.llm_kwargs(),
                    )
                except Exception as e:  # noqa: BLE001"""
s = s.replace(old, new)
helper = '''
def _b3_wait_completion(litellm, **kw):
    """base3: retry transient gateway/network failures (403/401/429/5xx/connection/timeout) every 60 s, up to 12 h."""
    import re as _re, time as _t
    deadline = _t.time() + 12 * 3600
    while True:
        try:
            return litellm.completion(**kw)
        except Exception as e:  # noqa: BLE001
            msg = f"{type(e).__name__}: {e}"
            transient = _re.search(r"\\b(401|403|429|50[0-4])\\b|Connection|Timeout|timed out|ServiceUnavailable|APIConnection",
                                   msg, _re.I)
            if not transient or _t.time() > deadline:
                raise
            print(f"spreadsheetbench[b3]: transient LLM error, waiting 60 s: {msg[:160]}", file=sys.stderr, flush=True)
            _t.sleep(60)

'''
anchor = "class Adapter(CapabilityAdapter):"
assert s.count(anchor) == 1
s = s.replace(anchor, helper + anchor)
open(p, "w").write(s); print("patched", p)
