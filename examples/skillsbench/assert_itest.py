#!/usr/bin/env python3
"""Regression gate for the SkillsBench EMPTY-SEED integration test.

Given a finished cap-evolve run dir, assert:
  1. the pipeline COMPLETED   — baseline.json + final.json + report.md exist;
  2. the empty-seed path FIRED — the `seed` candidate has NO SKILL.md, and the
     optimizer AUTHORED one: some non-seed candidate snapshot contains a SKILL.md
     (checked regardless of gate acceptance — every candidate is snapshotted);
  3. NON-REGRESSION           — final test reward >= baseline val reward.

Strict "must improve" is intentionally NOT asserted: 1 task x 1 trial x binary reward
is too noisy. The stable regression signal is "completes + creates a skill + doesn't
regress". Prints a compact JSON verdict and exits non-zero on failure.

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


def _has_skill_md(d: Path) -> bool:
    return d.is_dir() and any(d.rglob("SKILL.md"))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: assert_itest.py <run_dir>", file=sys.stderr)
        return 2
    run = Path(sys.argv[1])
    checks: dict[str, object] = {}

    baseline_json, final_json, report_md = run / "baseline.json", run / "final.json", run / "report.md"
    checks["completed"] = baseline_json.exists() and final_json.exists() and report_md.exists()

    cands = run / "candidates"
    seed = cands / "seed"
    seed_empty = seed.exists() and not _has_skill_md(seed)
    authored = [c.name for c in cands.glob("*") if c.name != "seed" and _has_skill_md(c)] if cands.exists() else []
    checks["seed_was_empty"] = seed_empty
    checks["optimizer_authored_skill"] = bool(authored)
    checks["authored_candidates"] = authored

    base_val = _reward(baseline_json, "val")
    final_test = _reward(final_json, "test")
    checks["baseline_val_reward"] = base_val
    checks["final_test_reward"] = final_test
    checks["no_regression"] = (base_val is not None and final_test is not None
                               and final_test + 1e-9 >= base_val)

    ok = bool(checks["completed"] and checks["seed_was_empty"]
              and checks["optimizer_authored_skill"] and checks["no_regression"])
    print(json.dumps({"ok": ok, "suite": "skillsbench-empty-seed", "run_dir": str(run),
                      "checks": checks}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
