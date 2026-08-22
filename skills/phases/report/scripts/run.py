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


def _pm(reward, stderr) -> str:
    """``0.71 ± 0.08`` when the stderr is known, else the bare point estimate.

    A point estimate with no noise floor invites over-reading: "0.71" and "0.71 ± 0.08"
    justify different ship decisions.
    """
    if reward is None:
        return "None"
    return f"{reward} ± {stderr}" if isinstance(stderr, (int, float)) else f"{reward}"


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
    p.add_argument("--dashboard-url", default="",
                   help="URL of a dashboard server the caller ALREADY started; recorded "
                        "as-is instead of launching a second one")
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))

    # --- ANSI terminal mode: reduce → render_ansi → stdout, then return ---
    if args.terminal:
        import dashboard
        reduced = dashboard.reduce_run(run_dir)
        print(dashboard.render_ansi(reduced, color=not args.no_color, top_n=args.top_n))
        return 0

    baseline = json.loads((run_dir.root / "baseline.json").read_text()) if (run_dir.root / "baseline.json").exists() else {}
    final_path = run_dir.root / "final.json"
    final = json.loads(final_path.read_text()) if final_path.exists() else {}
    finalized = bool(final.get("test"))

    base_val_obj = baseline.get("val") or {}
    base_val = base_val_obj.get("reward")
    test = final.get("test") or {}
    test_reward = test.get("reward")
    # Baseline scored on the SAME sealed test split — the honest held-out improvement.
    test_baseline = final.get("test_baseline") or {}
    test_baseline_reward = test_baseline.get("reward")
    test_delta = final.get("test_delta")
    baseline_id = final.get("baseline_id")  # "seed" normally; == best_id if best IS the seed

    # best val, the no-holdout verdict and the consuming-LLM profile are already computed by
    # the engine's reducer (``cap_evolve.dashboard.reduce_run``). Read them; never recompute
    # them here and never ask the agent to re-derive them in prose — that is how the report
    # stopped being comparable between runs.
    # ponytail: reduces a second time when the dashboard is also written (write_dashboard
    # reduces again). Thread the reduced dict through write_dashboard if that ever profiles hot.
    best_val = best_stderr = no_holdout = target_profile = None
    try:
        import dashboard
        reduced = dashboard.reduce_run(run_dir)
        s = reduced["summary"]
        best_val = s.get("best_val")
        best_stderr = next((n.get("stderr") for n in reduced["graph"]["nodes"]
                            if n.get("id") == s.get("best_id")), None)
        no_holdout = bool((s.get("splits") or {}).get("no_holdout"))
        target_profile = s.get("target_profile")
    except Exception:  # noqa: BLE001 — a broken reducer must never break the report
        pass

    # Search picks the candidate that scores best on val, so best_val is biased upward by
    # exactly the selection performed. test has no such bias, so the difference measures how
    # much the run overfit val.
    gap = (round(best_val - test_reward, 6)
           if isinstance(best_val, (int, float)) and isinstance(test_reward, (int, float))
           else None)

    summary = {
        "run_dir": str(run_dir.root),
        "best_id": run_dir.best_id,
        "finalized": finalized,
        "no_holdout": no_holdout,
        "baseline_val": base_val,
        "baseline_val_stderr": base_val_obj.get("stderr"),
        "best_val": best_val,
        "test_reward": test_reward,
        "test_stderr": test.get("stderr"),
        "test_baseline_reward": test_baseline_reward,
        "test_baseline_stderr": test_baseline.get("stderr"),
        "test_delta": test_delta,
        "test_pass_k": test.get("pass_k"),
        "val_test_gap": gap,
        "iterations": run_dir.spent.iterations,
        "target_profile": target_profile,
    }

    # pass^k for k > n_trials is UNDEFINED, so aggregate_scores omits it (see
    # loop.aggregate_scores) — never 0.0, which would read as "0% reliable" instead
    # of "not enough trials". Render exactly the ks that are PRESENT, in numeric
    # order: a hardcoded k range would drop a measured pass^3 and invent a
    # `pass^2=N/A` that was never requested (`ks` is a caller kwarg; gepa passes a
    # non-default one). final.json does not record which ks were asked for, so the
    # present keys are the only honest source.
    pk = test.get("pass_k") or {}
    if not isinstance(pk, dict):  # legacy run dirs stored a bare scalar
        pk = {"1": pk}
    pk_str = ", ".join(f"pass^{k}={float(pk[k]):.3f}" for k in sorted(pk, key=int))

    md = [f"# cap-evolve run report — {run_dir.root.name}", ""]
    if not finalized:
        # The sealed note below is the exact claim a reader relies on. Emitting it for a run
        # that never scored test is the worst failure mode this phase has — say the opposite.
        md += ["> **NOT FINALIZED** — no held-out test number. Run the finalize phase first; "
               "everything below is val-only.", ""]
    elif no_holdout:
        md += ["> **No holdout** (train == val == test). The test number below is a *fit* "
               "metric, not an estimate of generalization.", ""]
    md += [
        f"- Best candidate: `{run_dir.best_id}`",
        f"- Baseline val: {_pm(base_val, base_val_obj.get('stderr'))}",
        f"- Best val: {_pm(best_val, best_stderr)}",
        f"- **Held-out test (optimized skills): {_pm(test_reward, test.get('stderr'))}**"
        + (f"  ({pk_str})" if pk else ""),
    ]
    # When the best candidate IS the seed (no accepted gain), baseline_id == best_id and
    # baseline == optimized — label accordingly rather than implying a separate comparison.
    best_is_seed = baseline_id is not None and baseline_id == run_dir.best_id
    if test_baseline_reward is not None and not best_is_seed:
        baseline_label = f"baseline `{baseline_id}` skills" if baseline_id else "baseline skills"
        md.append(f"- Held-out test ({baseline_label}): "
                  f"{_pm(test_baseline_reward, test_baseline.get('stderr'))}")
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
    if gap is not None:
        md.append(f"- Val→test gap: {gap:+} — selection optimism on val; this gap IS the overfitting")
    md.append(f"- Iterations: {run_dir.spent.iterations}")
    if target_profile and target_profile.get("model"):
        # The consuming LLM the capabilities were optimized FOR — a different LLM role from
        # the optimizer model that proposed the edits.
        md.append(f"- Optimized for: {target_profile['model']}"
                  + (f" (tier {target_profile['tier']})" if target_profile.get("tier") else ""))
    if finalized:
        md += ["", sealed_note]
    (run_dir.root / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    if not args.no_dashboard:
        try:
            import dashboard
            dash = dashboard.write_dashboard(run_dir)
            summary["dashboard"] = str(dash)
        except Exception as e:  # noqa: BLE001 — never let the dashboard break the report
            summary["dashboard_error"] = str(e)

    # Final phase: guarantee the live dashboard server is up and opened, so "the
    # dashboard is created automatically in the last phase" holds even when early
    # auto-start was disabled. Best-effort; never fails the report.
    #
    # NOT idempotent, which is why --dashboard-url exists: maybe_launch() deliberately
    # steps past an occupied port (a stale server there would serve the wrong run), so
    # calling it again after `cap-evolve run` already launched one spawns a SECOND
    # server on a SECOND port and leaks it. When the caller hands us the URL it got,
    # record that and launch nothing.
    if args.dashboard_url:
        summary["dashboard_server"] = args.dashboard_url
    elif args.dashboard_mode in ("auto", "report-only"):
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
