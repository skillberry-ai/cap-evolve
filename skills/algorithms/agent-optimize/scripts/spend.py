"""spend — ONE call that answers "may I spend, and am I done?".

``references/algorithm.md`` says the agent re-reads spend against the project's
free-text ``stop_condition`` every few rounds. Re-reads is the operative word: a running
total carried in an agent's context is how a $6.00 cap becomes $6.01. Everything here is
read from the RUN DIR (``state.json`` spend, ``events.jsonl`` timestamps, the persisted
rollouts) — never from anything remembered.

It prints, in one JSON object:

  * ``best_id`` + the current best's **full-val** mean/stderr/coverage;
  * every recorded ``spent`` field, the ``budget``, and ``RunDir.budget_exhausted()``
    as ``stop``/``stop_reason`` (the exact rule the deterministic loops stop on);
  * ``wallclock_seconds`` — measured from the first event in ``events.jsonl``;
  * ``constraints`` — the free-text ``stop_condition`` parsed into concrete predicates
    (:mod:`cap_evolve.constraints`), each with its measured actual and satisfied/violated
    state, the original prose verbatim, an ``ambiguous`` list for anything the parser
    would have had to guess at, and one ``recommendation``:
    ``stop`` | ``continue`` | ``narrow_scope``;
  * ``afford`` — with ``--n-siblings N``, whether N full-val evaluations fit in what is
    left, using the run's own **measured** $/rollout. Check this BEFORE fanning out N
    proposers, not after: N candidates can blow a budget that had room for one.

``recommendation`` combines both halves: a violated ``budget_exhausted()`` is a ``stop``
even when the prose says nothing about money.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Imported for its side effect ONLY: seeds sys.path so `cap_evolve` resolves when
# this script is run standalone (`python <this-file>`). Must precede the
# cap_evolve imports below; not "unused" — deleting it breaks standalone runs.
import _bootstrap  # noqa: F401  # side-effect import, see above

from cap_evolve import RunDir, harness
from cap_evolve.constraints import check_constraints, parse_constraints
from cap_evolve.loop import has_valid_trials
from cap_evolve.specfile import spec_for_run


def _wallclock(run_dir: RunDir) -> float:
    """Seconds since the run's FIRST recorded event (measured, not remembered)."""
    import time
    try:
        with run_dir.events_path.open(encoding="utf-8") as f:
            first = json.loads(f.readline())
        return max(0.0, time.time() - float(first.get("t") or 0.0))
    except Exception:  # noqa: BLE001
        try:
            return max(0.0, time.time() - run_dir.state_path.stat().st_mtime)
        except Exception:  # noqa: BLE001
            return 0.0


def _regressed_vs_seed(run_dir: RunDir, best_id: str | None) -> list:
    """Val tasks the SEED measured-and-passed that the current best now scores lower.

    This is what a "don't regress task X" clause is checked against. Tasks either side
    failed to measure are skipped: missing data is not a regression.
    """
    if not best_id or best_id == "seed":
        return []
    seed = harness.split_result_from_rollouts(run_dir, "seed", "val")
    best = harness.split_result_from_rollouts(run_dir, best_id, "val")
    s = {pt["task_id"]: pt.get("reward", 0.0) for pt in (seed.per_task or [])
         if has_valid_trials(pt)}
    b = {pt["task_id"]: pt.get("reward", 0.0) for pt in (best.per_task or [])
         if has_valid_trials(pt)}
    return sorted(str(t) for t, r in s.items() if t in b and b[t] < r - 1e-9)


def _afford(run_dir: RunDir, spec: dict, n_siblings: int, n_trials: int) -> dict:
    """Can N full-val evals be paid for? Uses the run's MEASURED $/rollout.

    ``usd_per_rollout`` is ``spent.usd / spent.metric_calls`` — an observed average from
    this run's own rollouts, so the answer gets more accurate as the run proceeds and is
    honestly ``null`` before any rollout has been paid for (in which case only the
    rollout-count ceilings can be checked, and that is said out loud).
    """
    spent, budget = run_dir.spent, run_dir.budget
    val_n = len(run_dir.read_splits().ids("val"))
    per_eval = val_n * max(1, n_trials)
    need = per_eval * max(0, n_siblings)
    # A measured rate of EXACTLY $0 after real rollouts is not "free" — it is
    # UNMETERED. It happens whenever the serving path returns no cost (the IBM litellm
    # proxy does exactly this: litellm logs "model isn't mapped yet" and reports 0.0).
    # Treating it as 0.0 made `need_usd` 0.0, so the max_usd ceiling could never
    # block anything and ANY fan-out came back affordable: true. Unknown, not zero.
    metered = bool(spent.metric_calls) and spent.usd > 0.0
    upr = (spent.usd / spent.metric_calls) if metered else None
    unmetered = bool(spent.metric_calls) and not metered
    need_usd = (upr * need) if upr is not None else None

    blockers: list = []
    if budget.max_metric_calls:
        left = budget.max_metric_calls - spent.metric_calls
        if need > left:
            blockers.append(f"needs {need} rollouts, {left} left under max_metric_calls")
    if budget.max_usd and need_usd is not None:
        left_usd = budget.max_usd - spent.total_usd
        if need_usd > left_usd:
            blockers.append(f"needs ~${need_usd:.2f} of runner spend (measured "
                            f"${upr:.4f}/rollout), ${left_usd:.2f} left under max_usd")
    return {
        "n_siblings": n_siblings,
        "val_n": val_n,
        "n_trials": n_trials,
        "rollouts_per_full_val_eval": per_eval,
        "rollouts_needed": need,
        "usd_per_rollout_measured": upr,
        "usd_needed_estimate": need_usd,
        "affordable": not blockers,
        "blockers": blockers,
        "runner_spend_metered": (None if not spent.metric_calls else metered),
        "caveat": ("usd_per_rollout is this run's measured average and excludes the "
                   "proposer's own cost — record that with commit.py --optimizer-usd"
                   if upr is not None else
                   (f"{spent.metric_calls} rollouts are recorded but runner usd is still "
                    "0.0, so this serving path does NOT meter cost. The $ ceiling cannot "
                    "be enforced from measurements — bound the run with max_metric_calls "
                    "/ max_iterations instead, and report rollout counts, not dollars."
                    if unmetered else
                    "no rollout has been paid for yet, so only rollout-count ceilings "
                    "could be checked — the $ answer is unknown, not 'yes'")),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="spend")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--project", default=None,
                   help="project dir, to read stop_condition + num_trials")
    p.add_argument("--n-siblings", type=int, default=0,
                   help="check affordability of N full-val evals BEFORE fanning out")
    p.add_argument("--n-trials", type=int, default=0,
                   help="trials per full-val eval; default = the spec's num_trials")
    p.add_argument("--warn-frac", type=float, default=0.8,
                   help="ceiling consumption at which to recommend narrow_scope")
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    project = Path(args.project) if args.project else None
    spec = spec_for_run(run_dir, project)
    stop, reason = run_dir.budget_exhausted()
    best_id = run_dir.best_id
    best = harness.split_result_from_rollouts(run_dir, best_id, "val") if best_id else None
    spent = run_dir.spent
    wall = _wallclock(run_dir)

    parsed = parse_constraints(str(spec.get("stop_condition") or ""))
    checked = check_constraints(
        parsed,
        best_val=(best.reward if best else None),
        usd=spent.total_usd, wallclock_seconds=wall,
        iterations=spent.iterations, stall=spent.stall,
        metric_calls=spent.metric_calls,
        regressed_tasks=_regressed_vs_seed(run_dir, best_id),
        warn_frac=args.warn_frac,
    )

    # The run dir's own hard stop always wins: a prose condition cannot buy more budget.
    rec = "stop" if stop else checked["recommendation"]
    reasons = ([reason] if stop else []) + list(checked["reasons"])

    n_trials = args.n_trials or int(spec.get("num_trials") or 1)
    out = {
        "best_id": best_id,
        "best_val": ({"reward": best.reward, "stderr": best.stderr,
                      "coverage": best.coverage, "n_scored": best.n_scored,
                      "n_tasks": best.n_tasks} if best else None),
        "spent": spent.to_dict(),
        "budget": run_dir.budget.to_dict(),
        "wallclock_seconds": round(wall, 1),
        "stop": stop,
        "stop_reason": reason,
        "stop_condition": parsed["text"],
        "constraints": checked,
        "recommendation": rec,
        "recommendation_reasons": reasons,
        "test_sealed": not run_dir.read_splits().test_used,
    }
    if args.n_siblings:
        out["afford"] = _afford(run_dir, spec, args.n_siblings, n_trials)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
