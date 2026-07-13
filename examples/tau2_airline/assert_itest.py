#!/usr/bin/env python3
"""Regression gate for the taubench (tau2 airline) task-9 integration test.

Given a finished cap-evolve run dir, assert:
  1. the pipeline COMPLETED   — baseline.json + final.json + report.md exist;
  2. ONE iteration ran        — state.json spent.iterations >= 1;
  3. NON-REGRESSION           — final test reward >= baseline val reward.

With 1 iteration x 1 trial the paired gate will often REJECT the single edit
(final == baseline) — that is a legitimate PASS. The point is that the real taubench
pipeline runs end to end with a claude agent and yields an honest, non-worse number,
not that a single iteration must improve. Prints a JSON verdict; exits non-zero on fail.

Usage:  python assert_itest.py <run_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _reward(path: Path, split: str) -> float | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    node = data.get(split) or data
    r = node.get("reward")
    return float(r) if r is not None else None


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: assert_itest.py <run_dir>", file=sys.stderr)
        return 2
    run = Path(sys.argv[1])
    checks: dict[str, object] = {}

    baseline_json, final_json, report_md = run / "baseline.json", run / "final.json", run / "report.md"
    checks["completed"] = baseline_json.exists() and final_json.exists() and report_md.exists()

    iterations = None
    state = run / "state.json"
    if state.exists():
        iterations = int((json.loads(state.read_text(encoding="utf-8")).get("spent") or {}).get("iterations") or 0)
    checks["iterations"] = iterations
    checks["iteration_ran"] = bool(iterations and iterations >= 1)

    base_val = _reward(baseline_json, "val")
    final_test = _reward(final_json, "test")
    checks["baseline_val_reward"] = base_val
    checks["final_test_reward"] = final_test
    checks["no_regression"] = (base_val is not None and final_test is not None
                               and final_test + 1e-9 >= base_val)

    ok = bool(checks["completed"] and checks["iteration_ran"] and checks["no_regression"])
    print(json.dumps({"ok": ok, "suite": "tau2-task9", "run_dir": str(run),
                      "checks": checks}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
