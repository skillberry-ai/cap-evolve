"""report — summarize a run: baseline → best val → sealed test, and the winner.

Reads the run dir's baseline.json / final.json / events and prints a human and
machine readable summary. Writes report.md next to them, plus (by default) a
self-contained dashboard.html. ``--terminal`` / ``--ansi`` prints a colored
in-terminal report instead (CLAUDECODE-margin-aware) for in-chat progress.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import RunDir


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="report")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--no-dashboard", action="store_true", help="skip generating dashboard.html")
    p.add_argument("--terminal", "--ansi", dest="terminal", action="store_true",
                   help="print a colored ANSI terminal report (KPI strip + cumulative-best "
                        "chart + top-N table) instead of the JSON summary")
    p.add_argument("--no-color", action="store_true", help="disable ANSI colors in --terminal mode")
    p.add_argument("--top-n", type=int, default=8, help="rows in the --terminal candidate table")
    p.add_argument("--dashboard-mode", choices=("auto", "report-only", "off"), default="off",
                   help="ensure the live dashboard server is up (auto/report-only) at the final phase")
    p.add_argument("--dashboard-port", type=int, default=7878)
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))

    # --- ANSI terminal mode: reduce → render_ansi → stdout, then return ---
    if args.terminal:
        import dashboard
        reduced = dashboard.reduce_run(run_dir)
        print(dashboard.render_ansi(reduced, color=not args.no_color, top_n=args.top_n))
        return 0

    baseline = json.loads((run_dir.root / "baseline.json").read_text()) if (run_dir.root / "baseline.json").exists() else {}
    final = json.loads((run_dir.root / "final.json").read_text()) if (run_dir.root / "final.json").exists() else {}

    base_val = (baseline.get("val") or {}).get("reward")
    test = final.get("test") or {}
    test_reward = test.get("reward")
    # Baseline scored on the SAME sealed test split — the honest held-out improvement.
    test_baseline = final.get("test_baseline") or {}
    test_baseline_reward = test_baseline.get("reward")
    test_delta = final.get("test_delta")
    baseline_id = final.get("baseline_id")  # "seed" normally; == best_id if best IS the seed

    summary = {
        "run_dir": str(run_dir.root),
        "best_id": run_dir.best_id,
        "baseline_val": base_val,
        "test_reward": test_reward,
        "test_baseline_reward": test_baseline_reward,
        "test_delta": test_delta,
        "test_pass_k": test.get("pass_k"),
        "iterations": run_dir.spent.iterations,
    }

    test_line = f"- **Held-out test (optimized skills): {test_reward}**" + (
        f"  (pass^k={test.get('pass_k')})" if test.get("pass_k") else "")
    md = [
        f"# cap-evolve run report — {run_dir.root.name}",
        "",
        f"- Best candidate: `{run_dir.best_id}`",
        f"- Baseline val: {base_val}",
        test_line,
    ]
    # When the best candidate IS the seed (no accepted gain), baseline_id == best_id and
    # baseline == optimized — label accordingly rather than implying a separate comparison.
    best_is_seed = baseline_id is not None and baseline_id == run_dir.best_id
    if test_baseline_reward is not None and not best_is_seed:
        baseline_label = f"baseline `{baseline_id}` skills" if baseline_id else "baseline skills"
        md.append(f"- Held-out test ({baseline_label}): {test_baseline_reward}")
        md.append(
            f"- **Test improvement (optimized − baseline): {test_delta:+}**"
            if isinstance(test_delta, (int, float)) else f"- Test improvement: {test_delta}"
        )
        sealed_note = (
            "Test was scored exactly once on the sealed split, for BOTH the baseline "
            f"(`{baseline_id}`) and the optimized skills — the improvement above is on "
            "held-out tasks the optimizer never saw."
        )
    else:
        sealed_note = (
            "Test was scored exactly once on the sealed split. The best candidate is the "
            "seed (no accepted improvement), so baseline and optimized are identical here."
            if best_is_seed else
            "Test was scored exactly once on the sealed split."
        )
    md += [
        f"- Iterations: {run_dir.spent.iterations}",
        "",
        sealed_note,
    ]
    (run_dir.root / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    if not args.no_dashboard:
        try:
            import dashboard
            dash = dashboard.write_dashboard(run_dir)
            summary["dashboard"] = str(dash)
        except Exception as e:  # noqa: BLE001 — never let the dashboard break the report
            summary["dashboard_error"] = str(e)

    # Final phase: guarantee the live dashboard server is up (idempotent) and
    # opened, so "the dashboard is created automatically in the last phase" holds
    # even when early auto-start was disabled. Best-effort; never fails the report.
    if args.dashboard_mode in ("auto", "report-only"):
        try:
            from cap_evolve import dashboard_launch
            base = run_dir.root.resolve().parent  # absolute: subprocess cwd may differ
            status = dashboard_launch.maybe_launch(
                base, mode=args.dashboard_mode, port=args.dashboard_port, open_browser=True
            )
            summary["dashboard_server"] = status.get("dashboard")
        except Exception as e:  # noqa: BLE001
            summary["dashboard_server_error"] = str(e)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
