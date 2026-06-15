"""report — summarize a run: baseline → best val → sealed test, and the winner.

Reads the run dir's baseline.json / final.json / events and prints a human and
machine readable summary. Writes report.md next to them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from agent_capo import RunDir


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="report")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--no-dashboard", action="store_true", help="skip generating dashboard.html")
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    baseline = json.loads((run_dir.root / "baseline.json").read_text()) if (run_dir.root / "baseline.json").exists() else {}
    final = json.loads((run_dir.root / "final.json").read_text()) if (run_dir.root / "final.json").exists() else {}

    base_val = (baseline.get("val") or {}).get("reward")
    test = final.get("test") or {}
    test_reward = test.get("reward")

    summary = {
        "run_dir": str(run_dir.root),
        "best_id": run_dir.best_id,
        "baseline_val": base_val,
        "test_reward": test_reward,
        "test_pass_k": test.get("pass_k"),
        "iterations": run_dir.spent.iterations,
    }

    md = [
        f"# agent-capo run report — {run_dir.root.name}",
        "",
        f"- Best candidate: `{run_dir.best_id}`",
        f"- Baseline val: {base_val}",
        f"- **Held-out test: {test_reward}**" + (f"  (pass^k={test.get('pass_k')})" if test.get("pass_k") else ""),
        f"- Iterations: {run_dir.spent.iterations}",
        "",
        "Test was scored exactly once on the sealed split.",
    ]
    (run_dir.root / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    if not args.no_dashboard:
        try:
            import dashboard
            dash = dashboard.write_dashboard(run_dir)
            summary["dashboard"] = str(dash)
        except Exception as e:  # noqa: BLE001 — never let the dashboard break the report
            summary["dashboard_error"] = str(e)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
