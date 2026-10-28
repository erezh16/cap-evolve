"""TEST_ABL constants (docs/TEST_ABL.md §3, §7 B1, §12): the ablation champions, test window only.

Loaded by awrest.py when AW_PROFILE=testabl (set by examples/appworld/test_abl/env.sh). It reuses every TEST_ALL code
path (TESTALL is true for both profiles) with these values. Window 1 scores ARMS; the gate arms join WINDOW2_ARMS only
when they are ready (plan §3.2), and are scored in a second window (AW_STATE/final2). Nothing is trained.
"""

import os
from pathlib import Path

ARMS = ("seed", "abl_ref", "abl_cc_best", "abl_prompt", "abl_tools", "abl_notrace", "abl_tracescore")
GATE_ARMS = ("abl_nogate", "abl_naivegate")
# Plan §3.2: empty until both gate champions are frozen, reset, scanned and the gate run's P7 is done.
WINDOW2_ARMS: tuple = ()
ALL_ARMS = ARMS + WINDOW2_ARMS
CANDIDATES = ARMS[1:]
REF_ARM = "abl_ref"
# AW_WINDOW=2 selects the second window (its arms, order seed and state dir); unset = window 1.
WINDOW = os.environ.get("AW_WINDOW", "1")
if WINDOW == "2":
    ARMS, CANDIDATES = ("seed",) + WINDOW2_ARMS, WINDOW2_ARMS   # the seed is only a key for issue lookups here
ISSUES: dict = {}                          # from manifest.json `issues` (open_issues.py), never typed by hand
METHOD_NAMES = {"seed": "seed agent", "abl_ref": "Cap-evolve full (reference)",
                "abl_cc_best": "Claude code, best evaluated candidate", "abl_prompt": "Cap evolve prompt only",
                "abl_tools": "Cap evolve tools only", "abl_notrace": "Cap evolve no traces",
                "abl_tracescore": "Cap evolve traces and score only", "abl_nogate": "Cap evolve no gate",
                "abl_naivegate": "Cap evolve naive gate"}
SEARCH_ISSUES = {"abl_ref": 930, "abl_cc_best": 931, "abl_prompt": 932, "abl_tools": 933, "abl_notrace": 934,
                 "abl_tracescore": 935, "abl_nogate": 938, "abl_naivegate": 939}
LEDGER_PREFIX = "TA"                       # TEST_ALL's code paths (ARM_KEY, memory sample, ...)
LEDGER_ID = "TB"
EVAL_NAME = "TEST_ABL"
PLAN_NAME = "TEST_ABL.md"
FINAL_TRIALS = 5
FINAL_SEED_BASE = 7000                     # trial seeds 7000 + k (plan §0, D4)
FINAL_ORDER_SEED = 2026102802 if WINDOW == "2" else 2026102801
FINAL_DIR_NAME = "final2" if WINDOW == "2" else "final"
WINDOW_ARMS = WINDOW2_ARMS if WINDOW == "2" else ARMS
FINAL_CELLS = 168 * len(WINDOW_ARMS) * FINAL_TRIALS   # 5,880 (window 1), 1,680 (window 2)
BUDGET_ROLLOUTS = 0
BUDGET_OPT_TOKENS = 0
SEED_BASELINE_PHASE = None

# Hourly timers (plan §12.2): arm i owns offset i × 400 s; the gate arms' timers start when their issues exist.
TIMER_ORDER = ("seed", "abl_ref", "abl_cc_best", "abl_prompt", "abl_tools", "abl_notrace", "abl_tracescore") + GATE_ARMS
HOURLY_PERIOD_S = 400
HOURLY_OFFSET_S = {a: i * HOURLY_PERIOD_S for i, a in enumerate(TIMER_ORDER)}

_ABL = Path("/workspace/worktrees/eval-abl/docs/ABLATION_STATUS_STATE")
_BOX = {"abl_ref": "2026-10-25-appworld-capevolve-abl-full-75b3bcd-gptoss120b-sonnet55-qualified/champion/",
        "abl_cc_best": "2026-10-26-appworld-capevolve-abl-plainclaudecode-75b3bcd-gptoss120b-sonnet55-qualified/abl_cc_best/frozen_artifact/",
        "abl_prompt": "2026-10-25-appworld-capevolve-abl-promptonly-75b3bcd-gptoss120b-sonnet55-qualified/champion/",
        "abl_tools": "2026-10-25-appworld-capevolve-abl-toolsonly-75b3bcd-gptoss120b-sonnet55-qualified/champion/",
        "abl_notrace": "2026-10-26-appworld-capevolve-abl-notrace-75b3bcd-gptoss120b-sonnet55-qualified/champion/",
        "abl_tracescore": "2026-10-26-appworld-capevolve-abl-tracescore-75b3bcd-gptoss120b-sonnet55-qualified/champion/"}
_HASH = {"seed": "85a0da9cec2206a7bc683c11d60b5cb0acac7328d43c6e9197324d1e45971f3c",
         "abl_ref": "54a4f3799ae887761849d5b96e7da0f0e0e4939000ac18c528c60b5d652790c2",
         "abl_cc_best": "a2b6434e76a0109310d94d88fb193a0ece2435e98d0a12d443b6cc4a6f31ca71",
         "abl_prompt": "f979201fc17b5e55725b5032b411a486af837b470997a1bbfb40a818ba850eaa",
         "abl_tools": "d78dcf6138cd9f41c9ec819aaa43c0c78f6b68bdc983d04058ba64b8731c0434",
         "abl_notrace": "973ebcb4af6b3bddc83a597c6eedb12e65c03a7da34a4b81fba01c63da9723c8",
         "abl_tracescore": "c2da5909d55fac51bdc26ef678b53d302c2184869a144182db3a6431ff28327c"}
BOX_ROOT = "eval-data:appworld/"
ARTIFACTS = {"seed": {"local": Path("/workspace/worktrees/eval-abl/examples/appworld/seed_capability"), "box": None,
                      "hash": _HASH["seed"], "rule": "S"}}
ARTIFACTS |= {a: {"local": _ABL / a / "artifact", "box": _BOX[a], "hash": _HASH[a], "rule": "S"} for a in _BOX}
SURFACES_OF = {"seed": "none", "abl_ref": "P + T", "abl_cc_best": "P + T", "abl_prompt": "P", "abl_tools": "T",
               "abl_notrace": "P + T", "abl_tracescore": "P + T", "abl_nogate": "P + T", "abl_naivegate": "P + T"}
# Measured 2026-10-28 (file sha256 vs the seed's): abl_tools changed only tools/api_notes.json.
SURFACES_CHANGED = {"seed": "none", "abl_ref": "P + T", "abl_cc_best": "P + T", "abl_prompt": "P",
                    "abl_tools": "T (notes only)", "abl_notrace": "P + T", "abl_tracescore": "P + T"}
SOURCE_EVAL = {"seed": "the unmodified AppWorld ReAct agent",
               "abl_ref": "full cap-evolve main 75b3bcd, hill-climb, gate K = 0.2 (ablation study, #930)",
               "abl_cc_best": "plain Claude Code, one session, no cap-evolve; its best evaluated candidate (ablation study, #931)",
               "abl_prompt": "cap-evolve main 75b3bcd, edit surface = system prompt only (ablation study, #932)",
               "abl_tools": "cap-evolve main 75b3bcd, edit surface = tools only (ablation study, #933)",
               "abl_notrace": "cap-evolve main 75b3bcd, proposer without conversation traces (ablation study, #934)",
               "abl_tracescore": "cap-evolve main 75b3bcd, proposer with traces + reward only (ablation study, #935)",
               "abl_nogate": "cap-evolve main 75b3bcd, no acceptance gate (gate ablation, #938)",
               "abl_naivegate": "cap-evolve main 75b3bcd, naive gate (gate ablation, #939)"}
# Arms that have (or now get) an issue: window 1's 7, plus the gate arms once they are in WINDOW2_ARMS (plan §12.1).
ISSUE_ARMS = ("seed", "abl_ref", "abl_cc_best", "abl_prompt", "abl_tools", "abl_notrace", "abl_tracescore") + WINDOW2_ARMS
