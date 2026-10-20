"""Vendored verbatim from HarnessLens 369a5c8:harnesslens/core/train_protocol.py (see VENDORED.md)."""
from __future__ import annotations

import os


def _train_rollout_repeats() -> int:
    raw = str(os.environ.get("HAI_TRAIN_ROLLOUT_REPEATS", "2")).strip()
    try:
        repeats = int(raw)
    except ValueError as exc:
        raise ValueError("HAI_TRAIN_ROLLOUT_REPEATS must be an integer") from exc
    if repeats not in {1, 2}:
        raise ValueError("HAI_TRAIN_ROLLOUT_REPEATS must be 1 or 2")
    return repeats


TRAIN_ROLLOUT_REPEATS = _train_rollout_repeats()
