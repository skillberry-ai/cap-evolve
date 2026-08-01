#!/usr/bin/env python3
"""Assert a cap-evolve run dir completed and did not regress on the sealed test.

  assert_run.py <run_dir> [--min-iterations N] [--allow-regression] [--max-infra-frac F]

- completed: baseline.json + final.json present
- iteration_ran: state.json spent.iterations >= N (default 1)
- measured: not infra-dominated — at most F of the baseline's tasks failed with an
  INFRASTRUCTURE error (default 0.5)
- no_regression: final test reward >= baseline val reward
Exit 0 on pass, 1 on failure (prints why).

--allow-regression drops the no_regression check and asserts COMPLETION only. Use it
where the reward is a real, noisy model measurement (the benchmarks suite): there,
re-scoring the winner on the sealed test can land a hair under baseline through trial
noise alone, and failing CI for that would be a false alarm. The completion checks are
the ones that catch a genuinely broken run — a crashed step leaves no final.json.

The `measured` check exists because completion is NOT sufficient. A run whose every rollout
died on an infrastructure fault still writes baseline.json and final.json, still records
iterations, and still reports `success` — while measuring nothing. That is what
run 30682720920 did: `azure/gpt-5.5` rejected `temperature=0.0`, so all 60 tasks errored,
eval spend was $0.00, and the job went green with a clean-looking 0.000. An all-zero run
caused by a broken gateway, a missing binary or a bad model id must be LOUD, because the
alternative is publishing it as a real capability measurement.
"""
from __future__ import annotations
import json, sys
from pathlib import Path


def _infra_task(pt: dict) -> bool:
    """True if this task's reward≈0 is an infrastructure error, not a capability result.

    Same rule as ci/benchmarks/lib/metrics.py's `_infra_task`, which already renders these
    as `⚠️ infra-error` in the report — this wires that existing signal to the exit code.
    """
    raw = pt.get("raw") or {}
    if not raw.get("errored"):
        return False
    if float(pt.get("reward", 0) or 0) > 1e-9:
        return False
    et, nt = raw.get("errored_trials"), (raw.get("n_trials") or pt.get("n"))
    if et is not None and nt:
        return int(et) * 2 > int(nt)
    return True


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__); return 2
    rd = Path(argv[1])
    min_it = 1
    if "--min-iterations" in argv:
        min_it = int(argv[argv.index("--min-iterations") + 1])
    allow_regression = "--allow-regression" in argv
    max_infra_frac = 0.5
    if "--max-infra-frac" in argv:
        max_infra_frac = float(argv[argv.index("--max-infra-frac") + 1])

    for f in ("baseline.json", "final.json", "state.json"):
        if not (rd / f).exists():
            print(f"FAIL: missing {f} — the run did not complete (a step crashed or was killed)")
            return 1

    baseline = json.loads((rd / "baseline.json").read_text())["val"]
    base = baseline["reward"]
    fin = json.loads((rd / "final.json").read_text())["test"]["reward"]
    it = json.loads((rd / "state.json").read_text()).get("spent", {}).get("iterations", 0)

    if it < min_it:
        print(f"FAIL: only {it} optimizer iteration(s), need >= {min_it}"); return 1

    per_task = baseline.get("per_task") or []
    infra = [pt for pt in per_task if _infra_task(pt)]
    if per_task and len(infra) > max_infra_frac * len(per_task):
        ids = ", ".join(str(pt.get("task_id")) for pt in infra[:5])
        print(f"FAIL: {len(infra)}/{len(per_task)} baseline tasks failed with an "
              f"INFRASTRUCTURE error (> {max_infra_frac:.0%}) — this run measured nothing, "
              f"its 0.000 is not a capability result. First: {ids}. "
              f"Check the gateway/model id/binaries, not the capability.")
        return 1
    if fin + 1e-9 < base and not allow_regression:
        print(f"FAIL: regression — test {fin} < baseline {base}"); return 1
    note = ""
    if fin + 1e-9 < base:
        note = f" (test < baseline by {base - fin:.4f}; regression check waived)"
    print(f"OK: baseline={base} test={fin} iterations={it}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
