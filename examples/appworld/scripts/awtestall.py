"""TEST_ALL constants (docs/TEST_ALL.md §3, §7 B1, §12): 13 arms (the seed + 12 frozen champions), one test window.

Loaded by awrest.py when AW_PROFILE=testall (set by examples/appworld/test_all/env.sh), so every module that does
``import awrest as P`` (status_doc, window, analyze, post, autopost, ...) sees these values in every process of the
run. Paths come from the environment (AW_HOME, AW_STATE, AW_SCRATCH_ROOT, AW_LEDGER_NAME, AW_BRANCH, AW_REPO), all
set by env.sh. Nothing is trained: there is no optimizer, no search budget and no candidate run root. The window
joins no earlier records (plan §7 B1): REUSED_WINDOW_ARMS and FINAL_ARMS_RUN are not defined here.
"""

from pathlib import Path

ARMS = ("seed", "altk", "ace", "gepa", "skillopt", "wikiskill", "evoskill", "metaharness", "harnesslens", "miprov2",
        "trace2skill", "gepa_full", "cape_k02")
CANDIDATES = ARMS[1:]
# One new tracking issue per arm, the seed included (plan §12.1). The numbers are recorded in manifest.json
# (`issues`) by test_all/open_issues.py when the issues are opened, and read from there; never typed by hand.
ISSUES: dict = {}
METHOD_NAMES = {"seed": "seed agent", "altk": "ALTK-Evolve", "ace": "ACE", "gepa": "GEPA", "skillopt": "SkillOpt",
                "wikiskill": "WikiSkill", "evoskill": "EvoSkill", "metaharness": "Meta-Harness",
                "harnesslens": "HarnessLens", "miprov2": "MIPROv2", "trace2skill": "Trace2Skill",
                "gepa_full": "GEPA-Full", "cape_k02": "Cap-Evolve-impr2 K=0.2"}
LEDGER_PREFIX = "TA"
LEDGER_ID = "TA"
EVAL_NAME = "TEST_ALL"
FINAL_TRIALS = 5
FINAL_SEED_BASE = 7000                     # trial seeds 7000 + k, k in 0..4 (plan §0, D4)
FINAL_ORDER_SEED = 2026102501              # plan §8, §15
FINAL_CELLS = 168 * len(ARMS) * FINAL_TRIALS   # 10,920
BUDGET_ROLLOUTS = 0                        # no search in this plan (D1)
BUDGET_OPT_TOKENS = 0                      # no optimizer in this plan
SEED_BASELINE_PHASE = None

# Hourly status timers (plan §12.2): arm i owns offset i × 276 s into each UTC hour.
HOURLY_PERIOD_S = 276
HOURLY_OFFSET_S = {a: i * HOURLY_PERIOD_S for i, a in enumerate(ARMS)}

# The 13 artifacts (plan §3): local path first, Box second (D5); each verified by its own hash rule (S, F or B).
BOX_ROOT = "eval-data:appworld/"
SURFACES_OF = {"seed": "none", "altk": "M (retrieval)", "ace": "M", "gepa": "P + T", "skillopt": "P + T + M",
               "wikiskill": "P + T + M", "evoskill": "P + T + M", "metaharness": "P + T", "harnesslens": "none",
               "miprov2": "P", "trace2skill": "M", "gepa_full": "P + T", "cape_k02": "P + T"}
# Surfaces the frozen artifact actually changed vs the seed (file sha256 vs seed's; B3, 2026-10-24). Shown next to
# SURFACES_OF ("surfaces searched"); T4 and the §11.3 surface analysis use this one (user decision, TA-0000 D10).
SURFACES_CHANGED = {"seed": "none", "altk": "M (retrieval)", "ace": "M", "gepa": "P", "skillopt": "M",
                    "wikiskill": "M", "evoskill": "M", "metaharness": "P + T", "harnesslens": "none", "miprov2": "P",
                    "trace2skill": "M", "gepa_full": "P + T", "cape_k02": "P + T"}
SOURCE_EVAL = {"seed": "the unmodified AppWorld ReAct agent",
               "altk": "ALTK-Evolve v1.3.0, retrieval dose (smoke test, 2026-10-13)",
               "ace": "ACE, offline, no ground truth (2026-10-14)",
               "gepa": "GEPA v0.1.4, prompt + tools (eval 5, 2026-10-18)",
               "skillopt": "SkillOpt ae2f766 (eval 5)",
               "wikiskill": "WikiSkill (re-implementation; eval 5)",
               "evoskill": "EvoSkill v1.3.0 (eval 5)",
               "metaharness": "Meta-Harness 8123cca (eval 5)",
               "harnesslens": "HarnessLens 369a5c8 (REST, 2026-10-20); inert, equals the seed",
               "miprov2": "MIPROv2, DSPy 3.4.1 (REST)",
               "trace2skill": "Trace2Skill 3d0b52a (REST)",
               "gepa_full": "GEPA v0.1.4, full mode: prompt + per-app tool descriptions (REST)",
               "cape_k02": "cap-evolve Improvement 2, commit 3db96a0, hill-climb with gate K = 0.2 (CE3, 2026-10-24)"}
_REST_STATE = Path("/workspace/worktrees/eval-rest/docs/EVAL_APPWORLD_REST_STATE")
ARTIFACTS = {
    "seed": {"local": Path("/workspace/worktrees/eval-ce3/examples/appworld/seed_capability"), "box": None,
             "hash": "85a0da9cec2206a7bc683c11d60b5cb0acac7328d43c6e9197324d1e45971f3c", "rule": "S"},
    "altk": {"local": None,
             "box": "2026-10-15-appworld-capevolve-hillclimb-gptoss120b-sonnet55-fix-clean/final_window/artifacts/altk/",
             "hash": "b2b3703744f292128d428e791d3f6d70b5eca3a2572d194b96b6075603f1e131", "rule": "B"},
    "ace": {"local": None, "box": "2026-10-14-appworld-ace-offline-nogt-gptoss120b-sonnet55-qualified/final_window/artifacts/ace/",
            "hash": "e92fbff4b652aaaa8cce0e46bd9556b4706141834f1486245d7b9edc919b117f", "rule": "F"},
    "gepa": {"local": None, "box": "2026-10-18-appworld-gepa-v014-pt-gptoss120b-sonnet55-qualified/champion/artifact/",
             "hash": "26403e2c5e50ed9243c750457cb9f317f28970271c00b799f1d9018a1cdeffc6", "rule": "F"},
    "skillopt": {"local": None,
                 "box": "2026-10-18-appworld-skillopt-ae2f766-m-gptoss120b-sonnet55-qualified/champion/artifact/",
                 "hash": "8314b3340e1c0d8569f3785608186d9eb2cf65782f9be2bc17de0ca94319ca04", "rule": "F"},
    "wikiskill": {"local": None,
                  "box": "2026-10-18-appworld-wikiskill-reimpl-m-gptoss120b-sonnet55-qualified/champion/artifact/",
                  "hash": "3895752eb7b9759b4455aabf9ddde54b27442ad405245ec3272906cfa145b167", "rule": "F"},
    "evoskill": {"local": None,
                 "box": "2026-10-18-appworld-evoskill-v130-m-gptoss120b-sonnet55-scored/champion/artifact/",
                 "hash": "23f5f8f76cf504aee5eba4edbe4c209c160395f428bb39f11b36799ede22a804", "rule": "F"},
    "metaharness": {"local": None,
                    "box": "2026-10-19-appworld-metaharness-8123cca-pt-gptoss120b-sonnet55-qualified/champion/artifact/",
                    "hash": "ea0f2f68e37742b8b45fc2a257ad309fac85ebaf3ed00cf0cf60ee2a7cd0fe16", "rule": "F"},
    "harnesslens": {"local": _REST_STATE / "harnesslens" / "artifact",
                    "box": "2026-10-21-appworld-harnesslens-369a5c8-ptm-gptoss120b-sonnet55-inert-qualified/champion/",
                    "hash": "85a0da9cec2206a7bc683c11d60b5cb0acac7328d43c6e9197324d1e45971f3c", "rule": "S"},
    "miprov2": {"local": _REST_STATE / "miprov2" / "artifact",
                "box": "2026-10-20-appworld-miprov2-dspy341-p-gptoss120b-sonnet55-qualified/champion/",
                "hash": "a4ff3a502879f5206e5b32161f244c939635eb7d5bd70be59a8f9af01db6314a", "rule": "S"},
    "trace2skill": {"local": _REST_STATE / "trace2skill" / "artifact",
                    "box": "2026-10-21-appworld-trace2skill-3d0b52a-m-gptoss120b-sonnet55-qualified/champion/",
                    "hash": "a6b03deb2a044ed4c74920d02d6589b2113530ffd9053a947854152a8e4e5b6f", "rule": "S"},
    "gepa_full": {"local": _REST_STATE / "gepa_full" / "artifact",
                  "box": "2026-10-20-appworld-gepafull-v014-pt-gptoss120b-sonnet55-qualified/champion/",
                  "hash": "eb3d11d38bad1193cd20fc480f3d5de3ac04fc5e0bcf7002493bd7ae3187110e", "rule": "S"},
    "cape_k02": {"local": Path("/workspace/aw_ce3/state/ce3_k02/champion"), "box": None,
                 "hash": "e0ec3d94752bd3a2f067dfa2522695767d4077888a5f62fa360991c3e04019fb", "rule": "S"},
}
