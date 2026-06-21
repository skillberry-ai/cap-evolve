"""Textual learning-rate schedules — integer edit-budget per step (SkillOpt).

SkillOpt models a "textual learning rate" as how many edits the optimizer may make
in one step: a large budget early (explore broadly), shrinking later (consolidate).
This is the discrete analogue of an LR schedule, so we reuse the familiar
``constant | linear | cosine`` shapes but emit INTEGERS (you cannot make 2.7 edits).

``build_schedule(mode, max_lr, min_lr, total_steps)`` returns a list of length
``total_steps`` giving the edit budget at each step. Values are clamped to
``[min_lr, max_lr]`` and rounded to ints. Pure stdlib; deterministic.

This module is shipped now (W1) so the SkillOpt algorithm (W3) consumes it rather
than re-deriving the schedule.
"""

from __future__ import annotations

import math

_MODES = ("constant", "linear", "cosine")


def build_schedule(mode: str = "cosine", max_lr: int = 4, min_lr: int = 1,
                   total_steps: int = 10) -> list[int]:
    """Return a length-``total_steps`` list of integer edit budgets.

    Modes (all decay from ``max_lr`` toward ``min_lr`` over the run):
      - ``constant``: every step is ``max_lr``.
      - ``linear``:   linearly interpolate max_lr → min_lr across the steps.
      - ``cosine``:   half-cosine decay max_lr → min_lr (slow start, slow finish).

    ``min_lr``/``max_lr`` are clamped so ``min_lr <= max_lr`` and both ``>= 0``.
    ``total_steps <= 0`` yields an empty schedule.
    """
    if mode not in _MODES:
        raise ValueError(f"unknown schedule mode: {mode!r} (use {_MODES})")
    if total_steps <= 0:
        return []
    lo = max(0, int(min_lr))
    hi = max(lo, int(max_lr))

    if mode == "constant" or total_steps == 1:
        # A single step (or constant mode) sits at the max budget.
        return [hi] * total_steps

    out: list[int] = []
    last = total_steps - 1
    for i in range(total_steps):
        frac = i / last  # 0.0 .. 1.0
        if mode == "linear":
            val = hi + (lo - hi) * frac
        else:  # cosine: hi at frac=0, lo at frac=1, smooth at both ends
            val = lo + (hi - lo) * 0.5 * (1.0 + math.cos(math.pi * frac))
        # Round to nearest int, then clamp into [lo, hi] for safety.
        out.append(min(hi, max(lo, int(round(val)))))
    return out
