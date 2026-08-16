#!/usr/bin/env python3
"""Measurement-power analysis for the v4 run, re-derivable from `baseline.json` alone.

v3 concluded that `num_trials: 1` made the paired significance gate unable to detect any
edit, because a byte-identical copy of the seed measured Δ̄ = −0.0833. v4 raised trials to
5. This script takes the v4 baseline's MEASURED per-task pass rates (its `trial_rewards`
vectors) and reports, for each trial count:

  * the SD of the paired Δ̄ that a **null** edit would produce — i.e. how much apparent
    movement the harness invents when nothing changed; and
  * the probability that the **strict no-regression veto** fires on that same null edit.

The second number is the one v3 never computed, and it moves the OPPOSITE way from the
first: averaging trials shrinks the significance noise but turns every per-task reward
into a fraction, so "any task strictly dropped" becomes almost certain. Both halves of
the acceptance rule have to be readable at once for a run to be able to accept anything.

    python noise_power.py baseline.json
"""
from __future__ import annotations

import json
import math
import random
import statistics
import sys
from pathlib import Path


def rates(baseline: dict) -> list[float]:
    val = baseline["val"]
    return [p["reward"] for p in val["per_task"]]


def predicted_null_sd(ps: list[float], n: int) -> float:
    """SD of mean_t(cand_t - cur_t) when both sides are independent n-trial means."""
    return math.sqrt(sum(2 * p * (1 - p) / n for p in ps) / len(ps) ** 2)


def veto_fire_rate(ps: list[float], n: int, reps: int = 20000, seed: int = 0):
    """P(some task strictly drops) for a null edit, plus the simulated Δ̄ distribution."""
    rng = random.Random(seed)
    fires = 0
    deltas = []
    for _ in range(reps):
        cur = [sum(rng.random() < p for _ in range(n)) / n for p in ps]
        cand = [sum(rng.random() < p for _ in range(n)) / n for p in ps]
        deltas.append(sum(c - u for c, u in zip(cand, cur)) / len(ps))
        if any(c < u - 1e-9 for c, u in zip(cand, cur)):
            fires += 1
    return fires / reps, statistics.mean(deltas), statistics.stdev(deltas)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    baseline = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    ps = rates(baseline)
    val = baseline["val"]
    print(f"seed val mean {val['reward']:.4f} +/- {val['stderr']:.4f}  (n_tasks={val['n_tasks']})")
    print(f"per-task 5-trial means: {ps}")
    print(f"stochastic tasks (0<p<1): {sum(1 for p in ps if 0 < p < 1)} of {len(ps)}")
    print()
    print(f"{'n_trials':>8}  {'null SD(delta-bar)':>18}  {'P(veto fires | null)':>21}")
    for n in (1, 5, 10, 20, 40):
        sd = predicted_null_sd(ps, n)
        fire, _, _ = veto_fire_rate(ps, n)
        print(f"{n:>8}  {sd:>18.4f}  {fire:>21.3f}")
    print()
    print("A run can only accept when BOTH columns are small: the left one bounds how big a")
    print("real gain has to be to look significant, the right one is the chance the veto")
    print("rejects it anyway for noise. Raising trials fixes the left column and worsens the")
    print("right, so trials alone cannot make this gate able to accept.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
