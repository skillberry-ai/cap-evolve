#!/usr/bin/env python3
"""Assert a cap-evolve run dir completed and did not regress on the sealed test.

  assert_run.py <run_dir> [--min-iterations N] [--allow-regression]

- completed: baseline.json + final.json present
- iteration_ran: state.json spent.iterations >= N (default 1)
- no_regression: final test reward >= baseline val reward
Exit 0 on pass, 1 on failure (prints why).

--allow-regression drops the no_regression check and asserts COMPLETION only. Use it
where the reward is a real, noisy model measurement (the benchmarks suite): there,
re-scoring the winner on the sealed test can land a hair under baseline through trial
noise alone, and failing CI for that would be a false alarm. The completion checks are
the ones that catch a genuinely broken run — a crashed step leaves no final.json.
"""
from __future__ import annotations
import json, sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__); return 2
    rd = Path(argv[1])
    min_it = 1
    if "--min-iterations" in argv:
        min_it = int(argv[argv.index("--min-iterations") + 1])
    allow_regression = "--allow-regression" in argv

    for f in ("baseline.json", "final.json", "state.json"):
        if not (rd / f).exists():
            print(f"FAIL: missing {f} — the run did not complete (a step crashed or was killed)")
            return 1

    base = json.loads((rd / "baseline.json").read_text())["val"]["reward"]
    fin = json.loads((rd / "final.json").read_text())["test"]["reward"]
    it = json.loads((rd / "state.json").read_text()).get("spent", {}).get("iterations", 0)

    if it < min_it:
        print(f"FAIL: only {it} optimizer iteration(s), need >= {min_it}"); return 1
    if fin + 1e-9 < base and not allow_regression:
        print(f"FAIL: regression — test {fin} < baseline {base}"); return 1
    note = ""
    if fin + 1e-9 < base:
        note = f" (test < baseline by {base - fin:.4f}; regression check waived)"
    print(f"OK: baseline={base} test={fin} iterations={it}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
