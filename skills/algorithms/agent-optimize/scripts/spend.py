"""spend — the stop-condition readout: spend vs budget vs the free-text goal.

``references/algorithm.md`` says the agent re-reads spend (metric_calls / usd /
seconds) against the project's free-text ``stop_condition`` every few rounds. That
used to require hand-rolling three separate ``python -c`` one-liners. This prints all
of it in one JSON object: recorded spend, the budget, ``RunDir.budget_exhausted()``
(the bool+reason the deterministic loops stop on), the current best's full-val mean,
and the ``stop_condition`` text itself so it is in front of you when you decide.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import RunDir, harness
from cap_evolve.specfile import read_yaml


def _stop_condition(project: Path | None) -> str:
    if not project:
        return ""
    spec = project / "capevolve.yaml"
    if not spec.is_file():
        return ""
    try:
        return str((read_yaml(spec.read_text(encoding="utf-8")) or {}).get("stop_condition") or "")
    except Exception:  # noqa: BLE001 — a malformed spec must not block the readout
        return ""


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="spend")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--project", default=None, help="project dir, to read stop_condition")
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    stop, reason = run_dir.budget_exhausted()
    best_id = run_dir.best_id
    best = harness.split_result_from_rollouts(run_dir, best_id, "val") if best_id else None
    print(json.dumps({
        "best_id": best_id,
        "best_val": ({"reward": best.reward, "stderr": best.stderr,
                      "coverage": best.coverage} if best else None),
        "spent": run_dir.spent.to_dict(),
        "budget": run_dir.budget.to_dict(),
        "stop": stop,
        "stop_reason": reason,
        "stop_condition": _stop_condition(Path(args.project) if args.project else None),
        "test_sealed": not run_dir.read_splits().test_used,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
