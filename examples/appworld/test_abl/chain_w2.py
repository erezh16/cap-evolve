#!/usr/bin/env python3
"""TEST_ABL: window 2 part of chain.py, run in a fresh interpreter with AW_WINDOW=2 (the gate arms from the manifest)."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
import awrest as P  # noqa: E402
import chain  # noqa: E402

if __name__ == "__main__":
    if not P.WINDOW2_ARMS:
        raise SystemExit("window2_arms not in the manifest yet")
    raise SystemExit(chain.window("2", 168 * len(P.WINDOW2_ARMS) * 5))
