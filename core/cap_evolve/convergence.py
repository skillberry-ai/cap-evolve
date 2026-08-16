"""Plateau detection that escalates instead of halting.

cap-evolve's only plateau signal today is ``Budget.stall`` — a flat counter of
consecutive rejects that ``RunDir.budget_exhausted`` turns into a full stop. It
can say "give up" but not "you are digging in a dead subtree, change approach",
so the cheapest remaining budget gets spent on more of what already failed. This
module produces a graded signal — ``ok`` → ``warn`` → ``paradigm_shift`` → ``stop``
— whose ``advice`` text is written to be injected verbatim into the optimizer
prompt, keeping budget productive for several more iterations before the run dies.

Why this port is stricter than the original
-------------------------------------------
The idea comes from Arbor, which compares **raw single numbers**: an iteration is
"non-improving" whenever ``delta <= threshold``. On a noisy metric that mistakes
noise for a plateau — a run genuinely climbing 0.05/iteration with ±0.03 of trial
noise will, in any window where noise happens to eat the gain, be told to abandon
a working direction. cap-evolve carries a standard error on every ``SplitResult``,
so here "non-improving" is **variance-aware**: a gain counts only when it clears a
noise bar built from the observations' own stderr (via ``stats.combined_stderr``),
in addition to the relative ``improvement_threshold``. Real progress hidden under
noise is therefore *not* reported as a plateau — the same discipline
``gate.decide`` already applies to acceptance, extended to trend detection.

The pooled noise bar deliberately feeds ``combined_stderr`` a *flat* mean vector,
which isolates its within-task (trial) term. The between-task term measures the
spread of the rewards themselves, and on a genuinely rising sequence that spread
*is* the signal — counting it as noise would suppress exactly the trend we want
to detect.

:func:`assess` is a **pure function recomputed from the observation list on every
call** — no accumulated mutable state. That is what makes it crash-safe and
resume-safe (rebuild the list from ``events.jsonl`` / ``history.jsonl`` and you
get the identical signal) and trivially testable. Below ``min_observations`` it
returns ``ok`` with an explanatory ``advice``, so no caller ever acts on 2 points.

Pure stdlib.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Sequence

from . import stats

Level = Literal["ok", "warn", "paradigm_shift", "stop"]


@dataclass(frozen=True)
class ConvergenceConfig:
    min_observations: int = 4
    window: int = 5
    improvement_threshold: float = 0.001  # relative (see _scale)
    warn_after: int = 3
    shift_after: int = 5
    stop_after: int = 8
    k_se: float = 1.0                     # noise bar = k_se * SE, as in gate.decide


DEFAULT_CONFIG = ConvergenceConfig()


@dataclass
class Observation:
    """One iteration's outcome. Build from a ``SplitResult`` + the gate decision."""

    id: str
    reward: float
    accepted: bool = False
    stderr: float = 0.0


@dataclass
class ConvergenceSignal:
    level: Level
    consecutive_non_improving: int
    velocity: float
    advice: str
    n_observations: int = 0

    def to_dict(self) -> dict:
        return {"level": self.level,
                "consecutive_non_improving": self.consecutive_non_improving,
                "velocity": self.velocity, "advice": self.advice,
                "n_observations": self.n_observations}


def _signed(delta: float, direction: str) -> float:
    """Gain in the "better" polarity. The single place direction is interpreted,
    so ``maximize``/``minimize`` can't drift apart between call sites."""
    if direction == "minimize":
        return -delta
    if direction != "maximize":
        raise ValueError(f"unknown direction: {direction!r}")
    return delta


def _scale(*values: float) -> float:
    """Denominator for the *relative* improvement threshold. Floored at 1.0 so a
    baseline of 0.0 doesn't collapse the bar to zero (rewards are usually 0..1,
    where this makes the threshold plain 0.001)."""
    return max(1.0, *(abs(v) for v in values))


def _bar(cand_se: float, best_se: float, window_ses: Sequence[float],
         scale: float, cfg: ConvergenceConfig) -> float:
    """Noise + threshold bar a gain must clear to count as an improvement."""
    pair_se = math.sqrt(cand_se ** 2 + best_se ** 2)
    # Flat mean vector ⇒ combined_stderr returns only its within-task term: the
    # metric's own noise floor, not the spread of a real trend.
    pooled = stats.combined_stderr([0.0] * len(window_ses), list(window_ses)) if window_ses else 0.0
    return max(cfg.k_se * max(pair_se, pooled), cfg.improvement_threshold * scale)


def assess(observations: Sequence[Observation], *, baseline: float,
           config: ConvergenceConfig = DEFAULT_CONFIG,
           direction: str = "maximize") -> ConvergenceSignal:
    """Grade the run's trend. Pure: same input ⇒ identical output.

    ``observations`` are the iteration outcomes in chronological order;
    ``baseline`` is the score every candidate must beat (the seed's val reward).
    """
    obs = list(observations)
    n = len(obs)
    cfg = config
    _signed(0.0, direction)  # validate direction eagerly, even on the short path

    if n < cfg.min_observations:
        return ConvergenceSignal(
            "ok", 0, 0.0, n_observations=n,
            advice=(f"Only {n} of {cfg.min_observations} observations needed for a trend "
                    "verdict — keep optimizing normally; no plateau conclusion is "
                    "statistically available yet."))

    # Replay the run: a gain counts only when it clears the variance-aware bar.
    best, best_se = baseline, 0.0
    streak = 0
    for i, o in enumerate(obs):
        window_ses = [x.stderr for x in obs[max(0, i - cfg.window + 1):i + 1]]
        bar = _bar(o.stderr, best_se, window_ses, _scale(baseline, best), cfg)
        if _signed(o.reward - best, direction) > bar:
            best, best_se, streak = o.reward, o.stderr, 0
        else:
            streak += 1

    win = obs[-cfg.window:]
    ref = obs[-cfg.window - 1].reward if n > cfg.window else baseline
    velocity = _signed(win[-1].reward - ref, direction) / len(win)
    accepted = sum(1 for o in win if o.accepted)

    if streak >= cfg.stop_after:
        level: Level = "stop"
        advice = (f"STOP: {streak} consecutive iterations with no improvement that clears the "
                  "noise bar. The remaining budget is better spent elsewhere — this search "
                  "direction is exhausted. Report the current best and finalize.")
    elif streak >= cfg.shift_after:
        level = "paradigm_shift"
        advice = (f"PARADIGM SHIFT REQUIRED: {streak} consecutive iterations produced no "
                  "improvement beyond noise. Incremental tweaks to the current approach are "
                  "not working. Abandon this line of edits and try a structurally different "
                  "one: change WHICH component you edit, restructure it rather than reword "
                  "it, or revisit an assumption in the current design. Do not submit another "
                  "variation of the last few edits.")
    elif streak >= cfg.warn_after:
        level = "warn"
        advice = (f"PLATEAU WARNING: {streak} consecutive iterations with no improvement "
                  f"beyond measurement noise ({accepted}/{len(win)} recent iterations "
                  "accepted). Before the next edit, re-read the failure clusters and target "
                  "a failure mode you have not addressed yet rather than refining the last "
                  "edit further.")
    else:
        level = "ok"
        advice = (f"Progress is real: velocity {velocity:+.4f}/iteration over the last "
                  f"{len(win)} iterations ({accepted} accepted). Continue the current "
                  "approach.")

    return ConvergenceSignal(level, streak, velocity, advice, n_observations=n)
