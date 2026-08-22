"""baseline — create the run dir, freeze the splits, score the seed on val.

This establishes the starting point every algorithm compares against. It is the
first step that touches data, so it owns split creation (seeded, written once).
Prints the run-dir path and the baseline val score as JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import Budget, RunDir, harness
from cap_evolve.check import load_adapter, run_check


def _refuse_degenerate_split(splits, run_dir) -> bool:
    """Refuse a ratio split with no val or no test; warn on a tiny val (#113).

    A val-gated run with zero val tasks has nothing to decide on, and a sealed-test
    run with zero test tasks produces its headline number over nothing — both fail
    silently today because ``make_splits`` clamps sizes without a floor
    (``splits.py:113-119``). Failing here costs nothing; failing at finalize costs the
    whole run. A pinned ``--split-ids`` may be deliberately degenerate (the no-holdout
    case), so only the ratio path is guarded.
    """
    if not splits.val or not splits.test:
        msg = (f"degenerate ratio split: train={len(splits.train)} val={len(splits.val)} "
               f"test={len(splits.test)} — the val gate and the sealed test number both "
               "need at least one task. Add tasks, change --ratios, or pin --split-ids "
               "deliberately.")
        run_dir.log_event("splits_warning", msg=msg)
        print(json.dumps({"step": "baseline", "error": msg}, indent=2), file=sys.stderr)
        return True
    if len(splits.val) < 5:
        run_dir.log_event(
            "splits_warning",
            msg=(f"val has only {len(splits.val)} task(s) — the gate's Δ > k·SE bar is "
                 "optimistic at this n, and a one-task improvement cannot reliably clear "
                 "it at all (#351). Prefer >= 5 val tasks."))
    return False


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="baseline")
    p.add_argument("--base", default=".capevolve", help="dir under which run_* is created")
    p.add_argument("--project", required=True, help="dir with adapters/adapter.py")
    p.add_argument("--capability", required=True, help="seed capability dir")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--ratios", default="0.5,0.25,0.25")
    p.add_argument("--split-ids", default=None,
                   help="JSON file {train:[],val:[],test:[]} to pin the split explicitly")
    p.add_argument("--reuse-baseline", default=None,
                   help="prior run dir: reuse its splits/baseline/seed/val-rollouts and "
                        "SKIP the baseline eval (algorithm starts at iter 1 on it)")
    p.add_argument("--n-trials", type=int, default=1)
    p.add_argument("--max-iterations", type=int, default=10)
    p.add_argument("--stall", type=int, default=0)
    p.add_argument("--max-metric-calls", type=int, default=0, help="0 = unlimited")
    p.add_argument("--max-usd", type=float, default=0.0,
                   help="0 = unlimited; total spend cap (runner + optimizer + intake)")
    p.add_argument("--max-optimizer-usd", type=float, default=0.0,
                   help="0 = off; separate cap on optimizer spend alone")
    p.add_argument("--run-ts", default=None, help="fixed timestamp for reproducible run dirs")
    p.add_argument("--resume", action="store_true",
                   help="reopen an existing run dir instead of failing; skip the baseline "
                        "eval when it already ran (baseline.json present)")
    p.add_argument("--spec", default=None,
                   help="path to capevolve.yaml spec (for observer config)")
    args = p.parse_args(argv)

    # The hard gate, on THIS path too. `cap-evolve run` checks the adapter before it
    # calls us (cli.py:721-726), but /cap-evolve:baseline is reachable directly and the
    # needs/provides DAG validates declared order, not runtime state — so without this
    # the standalone chain would freeze a split against a knowingly-broken adapter and
    # every number in the run would be measured against it (#358). Gate before the run
    # dir exists so a red check leaves nothing behind.
    rep = run_check(Path(args.project))
    if not rep.ok:
        print(json.dumps({"step": "baseline", "error": "check failed",
                          "report": rep.to_dict()}, indent=2), file=sys.stderr)
        return 1

    Path(args.base).mkdir(parents=True, exist_ok=True)
    budget = Budget(max_iterations=args.max_iterations, stall=args.stall,
                    max_metric_calls=args.max_metric_calls, max_usd=args.max_usd,
                    max_optimizer_usd=args.max_optimizer_usd)
    run_dir = RunDir.create(Path(args.base), ts=args.run_ts, budget=budget, exist_ok=args.resume)

    try:
        try:
            from cap_evolve.specfile import read_yaml
            from capevolve_telemetry import load_observers, load_observers_from_state
            spec_path = Path(args.spec) if args.spec else Path(args.project, "capevolve.yaml")
            spec_text = spec_path.read_text(encoding="utf-8")
            full_spec = read_yaml(spec_text)
            obs_config = full_spec.get("observers")
            caps = full_spec.get("capabilities")
            run_name = str(full_spec.get("run_name", "")).strip()
            if not run_name:
                parts = [run_dir.root.name]
                for key in ("algorithm_skill", "optimizer_skill", "target_model"):
                    v = str(full_spec.get(key, "")).strip()
                    if v:
                        parts.append(v)
                if isinstance(caps, list):
                    parts.append("+".join(str(c) for c in caps))
                elif caps:
                    parts.append(str(caps))
                run_name = " | ".join(parts)
            run_tags = {}
            for key in ("algorithm_skill", "optimizer_skill", "optimizer_model",
                         "target_model", "max_iterations", "gate_mode", "num_trials",
                         "dataset_source"):
                v = full_spec.get(key)
                if v is not None and str(v).strip():
                    run_tags[key] = str(v)
            if caps:
                run_tags["capabilities"] = "+".join(str(c) for c in caps) if isinstance(caps, list) else str(caps)
            observers = (
                load_observers_from_state(run_dir.load_observer_state())
                if args.resume
                else load_observers(
                    obs_config,
                    run_dir_root=str(run_dir.root),
                    run_name=run_name,
                    run_tags=run_tags,
                )
            )
            for obs in observers:
                run_dir.add_observer(obs)
        except Exception:  # noqa: BLE001
            pass

        # Resume fast-path: baseline already ran → the split is frozen, the seed is scored,
        # best_id is set. Re-print the recorded baseline and skip the (expensive) eval so the
        # algorithm resumes straight from the current best. state.json is left untouched.
        if args.resume and (run_dir.root / "baseline.json").exists():
            splits = run_dir.read_splits()
            recorded = json.loads((run_dir.root / "baseline.json").read_text(encoding="utf-8"))
            print(json.dumps({
                "run_dir": str(run_dir.root),
                "splits": {"train": len(splits.train), "val": len(splits.val), "test": len(splits.test)},
                "baseline_val": recorded.get("val", {}),
                "resumed": True,
            }, indent=2))
            return 0

        adapter = load_adapter(Path(args.project))

        # --reuse-baseline: copy a prior run's frozen split + baseline + seed snapshot +
        # seed val rollouts into this fresh run dir and SKIP the (expensive) baseline eval.
        if args.reuse_baseline:
            result = harness.reuse_baseline(Path(args.reuse_baseline), run_dir=run_dir)
            splits = run_dir.read_splits()
            print(json.dumps({
                "run_dir": str(run_dir.root),
                "splits": {"train": len(splits.train), "val": len(splits.val), "test": len(splits.test)},
                "baseline_val": result.to_dict(),
                "reused_baseline_from": str(args.reuse_baseline),
            }, indent=2))
            return 0

        ratios = tuple(float(x) for x in args.ratios.split(","))
        split_ids = None
        if args.split_ids:
            # Resolve the split-ids path robustly: as given (absolute or cwd-relative),
            # else relative to the project dir. `cap-evolve run` invokes baseline with
            # cwd=workdir, so a project-relative `split_ids_file: split_ids.json` in
            # capevolve.yaml would otherwise miss — this lets users author it naturally.
            sp = Path(args.split_ids)
            if not sp.exists():
                cand = Path(args.project) / args.split_ids
                if cand.exists():
                    sp = cand
            split_ids = json.loads(sp.read_text(encoding="utf-8"))
        splits = harness.ensure_splits(adapter, run_dir, seed=args.seed, ratios=ratios,
                                       split_ids=split_ids)
        if split_ids is None and _refuse_degenerate_split(splits, run_dir):
            return 1
        # Resolve the seed capability dir robustly: as given (absolute/cwd-relative),
        # else relative to the project dir. `cap-evolve run` invokes baseline with
        # cwd=workdir, so a project-relative `capability_path: seed_capability` in
        # capevolve.yaml would otherwise miss — let users author it naturally.
        cap_path = Path(args.capability)
        if not cap_path.exists():
            cand = Path(args.project) / args.capability
            if cand.exists():
                cap_path = cand
        result = harness.baseline(adapter, cap_path, run_dir=run_dir, n_trials=args.n_trials)

        # Headroom: the budget decision this phase exists to make. Saturated => every
        # later Δ chases noise; floor => usually a broken adapter, not a hard task.
        # Emitted, not just advised, so `cap-evolve run` / orchestrate can stop on it
        # without a human reading the number. Non-fatal: recording it is the job.
        headroom = round(max(0.0, 1.0 - result.reward), 4)
        verdict = ("saturated" if result.reward + max(result.stderr, 0.0) >= 1.0
                   else "floor" if result.reward <= 0.0 else "ok")
        run_dir.log_event("headroom", headroom=headroom, verdict=verdict, val=result.reward)

        print(json.dumps({
            "run_dir": str(run_dir.root),
            "splits": {"train": len(splits.train), "val": len(splits.val), "test": len(splits.test)},
            "baseline_val": result.to_dict(),
            "headroom": headroom,
            "headroom_verdict": verdict,
        }, indent=2))
        return 0
    finally:
        close_observers = getattr(run_dir, "close_observers", None)
        if callable(close_observers):
            close_observers()


if __name__ == "__main__":
    sys.exit(main())
