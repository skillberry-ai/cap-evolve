#!/usr/bin/env python3
"""Assert a cap-evolve run dir completed and did not regress on the sealed test.

  assert_run.py <run_dir> [--min-iterations N] [--expect-flip]

- completed: baseline.json + final.json present
- iteration_ran: state.json spent.iterations >= N (default 1)
- no_regression: final test reward >= baseline val reward
- --expect-flip: additionally require final test reward > baseline (0 -> >0)
Exit 0 on pass, 1 on failure (prints why).
"""
from __future__ import annotations
import json, sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__); return 2
    rd = Path(argv[1])
    min_it = 1
    expect_flip = "--expect-flip" in argv
    if "--min-iterations" in argv:
        min_it = int(argv[argv.index("--min-iterations") + 1])

    for f in ("baseline.json", "final.json", "state.json"):
        if not (rd / f).exists():
            print(f"FAIL: missing {f}"); return 1

    base = json.loads((rd / "baseline.json").read_text())["val"]["reward"]
    fin = json.loads((rd / "final.json").read_text())["test"]["reward"]
    it = json.loads((rd / "state.json").read_text()).get("spent", {}).get("iterations", 0)

    if it < min_it:
        print(f"FAIL: only {it} optimizer iteration(s), need >= {min_it}"); return 1
    if fin + 1e-9 < base:
        print(f"FAIL: regression — test {fin} < baseline {base}"); return 1
    if expect_flip and not (fin > base):
        print(f"FAIL: expected a flip but test {fin} <= baseline {base}"); return 1
    print(f"OK: baseline={base} test={fin} iterations={it}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
