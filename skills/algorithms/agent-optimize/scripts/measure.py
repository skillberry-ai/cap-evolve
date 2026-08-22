"""measure — the run's FINAL, honest seed-vs-best table across every real split.

A val number is the thing the gate optimized against, so quoting it as the result is
quoting the training signal. This script produces the one table that is allowed to be
called "the improvement": ``seed`` vs ``best`` on **val** (from the rollouts the gate
actually used), on **train** when the spec defines a train split worth reporting, and
on the **sealed test** split — scored exactly once, through the same ``harness.finalize``
the finalize phase calls, and refused on a second attempt.

For every split it prints mean, stderr, n (tasks scored / tasks in split), the paired
per-task delta vector's mean + SE + n, and the gate decision recomputed on that vector.

What it refuses to pretend:

  * **No-holdout specs.** If ``test`` overlaps ``train``/``val`` (as some benchmarks ship by
    default, where all three are the same ids), the test column is a FIT
    metric, not generalisation, and the payload says so in ``holdout`` — with the
    overlap counted, not hand-waved.
  * **Empty splits.** A split with no ids gets ``"status": "empty"`` and no numbers,
    rather than a 0.0 that reads like a measured failure.
  * **best == seed.** Nothing cleared the gate; the deltas are 0 by construction and
    ``no_accepted_change`` says so, instead of presenting a 0.000 improvement as a
    measurement of anything.

Train is measured only when it adds information: ``--train auto`` (the default) skips
it when the train ids equal the val ids (the numbers would be a copy) and skips it when
there are no train ids. ``--train on`` forces it; ``--train off`` never pays for it.
Train and val evals here are ordinary un-sealed evaluations; only test is sealed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import RunDir, harness
from cap_evolve.check import load_adapter
from cap_evolve.gate import decide
from cap_evolve.loop import SplitResult
from cap_evolve.specfile import spec_for_run


def _num(sr: SplitResult | None) -> dict:
    if sr is None:
        return {"status": "not measured"}
    return {"reward": round(sr.reward, 6), "stderr": round(sr.stderr, 6),
            "n_scored": sr.n_scored, "n_tasks": sr.n_tasks,
            "coverage": round(sr.coverage, 4), "pass_k": sr.pass_k}


def _compare(seed: SplitResult | None, best: SplitResult | None, *, split: str,
             k_se: float, mode: str) -> dict:
    """Paired delta + the gate decision on one split. Gate is only meaningful on val."""
    row = {"split": split, "seed": _num(seed), "best": _num(best)}
    if seed is None or best is None:
        return row
    deltas = harness._paired_deltas(seed, best)
    row["mean_delta_unpaired"] = round(best.reward - seed.reward, 6)
    if not deltas:
        row["paired"] = {"status": "no aligned per-task data (tasks unscored on one "
                                  "side are dropped — missing data, not a 0.0)"}
        return row
    n = len(deltas)
    mean_d = sum(deltas) / n
    se = 0.0
    if n >= 2:
        var = sum((d - mean_d) ** 2 for d in deltas) / (n - 1)
        se = (var / n) ** 0.5
    row["paired"] = {"n": n, "mean_delta": round(mean_d, 6), "se": round(se, 6),
                     "improved": sum(1 for d in deltas if d > 1e-9),
                     "regressed": sum(1 for d in deltas if d < -1e-9)}
    if split == "val":
        d = decide(seed.reward, best.reward, split="val", mode=mode, k_se=k_se,
                   candidate_stderr=best.stderr, current_stderr=seed.stderr,
                   paired_deltas=deltas, coverage=best.coverage)
        row["gate"] = d.to_dict()
    else:
        row["gate"] = {"note": f"no gate on {split}: acceptance is val-only "
                               "(gate.decide refuses any other split)"}
    return row


def _per_task_movement(seed: SplitResult, best: SplitResult) -> dict:
    from cap_evolve.loop import has_valid_trials
    s = {pt["task_id"]: pt.get("reward", 0.0) for pt in (seed.per_task or [])
         if has_valid_trials(pt)}
    b = {pt["task_id"]: pt.get("reward", 0.0) for pt in (best.per_task or [])
         if has_valid_trials(pt)}
    shared = sorted(set(s) & set(b))
    return {
        "fixed": [t for t in shared if b[t] > s[t] + 1e-9],
        "broke": [t for t in shared if b[t] < s[t] - 1e-9],
        "unchanged": [t for t in shared if abs(b[t] - s[t]) <= 1e-9],
        "unpaired": sorted((set(s) | set(b)) - set(shared)),
    }


def _screen_ledger(run_dir: RunDir) -> dict:
    """Sum every recorded subset screen. MEASURED integers, no estimates.

    ``net_rollouts`` is what the ladder actually bought: ``+ (full_val − fired)`` for each
    kill, ``− fired`` for each promote. A negative total is an honest report that screening
    cost more than it saved on this run — which is what happens when nothing gets killed.
    """
    d = run_dir.root / "screens"
    rows = []
    for f in sorted(d.glob("*.json")):
        try:
            rows.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            continue
    kills = [r for r in rows if r.get("decision") == "kill"]
    return {
        "screens": len(rows),
        "kills": len(kills),
        "promotes": len(rows) - len(kills),
        "rollouts_fired_by_screens": sum(int(r["savings"]["fired"]) for r in rows),
        "rollouts_avoided_by_kills": sum(int(r["savings"]["avoided"]) for r in rows),
        "net_rollouts": sum(int(r["savings"]["net_rollouts"]) for r in rows),
        "screen_usd": round(sum(float(r["savings"].get("screen_cost_usd") or 0.0)
                                for r in rows), 6),
        "note": ("net_rollouts > 0 means the ladder paid for itself; <= 0 means every "
                 "candidate was promoted, so screening was pure overhead this run"),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="measure")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--n-trials", type=int, default=0,
                   help="trials per eval; default = the spec's num_trials")
    p.add_argument("--k-se", type=float, default=None,
                   help="gate bar; default = the spec's gate_k_se")
    p.add_argument("--gate-mode", default=None,
                   help="gate mode; default = the spec's gate_mode (else paired)")
    p.add_argument("--train", default="auto", choices=["auto", "on", "off"])
    p.add_argument("--skip-test", action="store_true",
                   help="report train/val only; do NOT touch the seal (audit use)")
    p.add_argument("--workers", type=int, default=None)
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    project = Path(args.project)
    spec = spec_for_run(run_dir, project)
    n_trials = args.n_trials or int(spec.get("num_trials") or 1)
    k_se = args.k_se if args.k_se is not None else float(spec.get("gate_k_se") or 1.0)
    mode = args.gate_mode or str(spec.get("gate_mode") or "paired")

    splits = run_dir.read_splits()
    best_id = run_dir.best_id or "seed"
    tr, va, te = set(splits.train), set(splits.val), set(splits.test)
    holdout = {
        "n_train": len(tr), "n_val": len(va), "n_test": len(te),
        "test_overlaps_train": len(te & tr), "test_overlaps_val": len(te & va),
        "val_overlaps_train": len(va & tr),
    }
    held_out = bool(te) and not (te & tr) and not (te & va)
    holdout["test_is_held_out"] = held_out
    holdout["verdict"] = (
        "TEST IS HELD OUT: the test column measures generalisation."
        if held_out else
        ("NO TEST SPLIT: there is no held-out number in this run at all."
         if not te else
         "NOT HELD OUT: test overlaps train/val, so the test column is a FIT metric, "
         "not generalisation. Do not report it as a held-out result.")
    )

    rows: list = []

    # ---- val: free, straight off the rollouts the gate used ------------------
    if not va:
        rows.append({"split": "val", "status": "empty — no val ids in the frozen split"})
        seed_val = best_val = None
    else:
        seed_val = harness.split_result_from_rollouts(run_dir, "seed", "val")
        best_val = harness.split_result_from_rollouts(run_dir, best_id, "val")
        rows.append(_compare(seed_val, best_val, split="val", k_se=k_se, mode=mode))

    # ---- train: only when it adds information -------------------------------
    do_train = args.train == "on" or (args.train == "auto" and tr and tr != va)
    if not tr:
        rows.append({"split": "train", "status": "empty — no train ids in the frozen split"})
    elif not do_train:
        rows.append({"split": "train",
                     "status": ("skipped: train ids are identical to val, so the numbers "
                                "would be a copy of the val row (pass --train on to "
                                "measure anyway)" if tr == va else
                                "skipped by --train off")})
    else:
        adapter = load_adapter(project)

        def _train(cid: str, tag: str):
            """Train result for candidate ``cid``, REUSING its rollouts when complete.

            A candidate dir is an immutable snapshot, so rollouts already persisted under
            its own tag are measurements of exactly this capability — re-running them buys
            nothing and costs a full train split. (The agent-mode loop pays one
            ``evaluate --split train`` for the seed to get a diagnosis signal, so this
            reuse is the common case, not a corner case.)
            """
            have = harness.split_result_from_rollouts(run_dir, cid, "train")
            if have.per_task and have.n_scored >= len(tr):
                have.reused_rollouts = True  # type: ignore[attr-defined]
                return have, True
            return harness.evaluate_candidate(adapter, run_dir.candidate_dir(cid),
                                              run_dir=run_dir, split="train",
                                              n_trials=n_trials, tag=tag,
                                              workers=args.workers), False

        s, s_reused = _train("seed", "MEASURE_seed")
        if best_id == "seed":
            b, b_reused = s, s_reused
        else:
            b, b_reused = _train(best_id, "MEASURE_best")
        row = _compare(s, b, split="train", k_se=k_se, mode=mode)
        row["rollouts_reused"] = {"seed": s_reused, "best": b_reused}
        rows.append(row)

    # ---- test: the sealed split, exactly once -------------------------------
    final_path = run_dir.root / "final.json"
    if not te:
        rows.append({"split": "test", "status": "empty — no test ids; this run has no "
                                                "held-out number"})
    elif args.skip_test:
        rows.append({"split": "test", "status": "skipped by --skip-test (seal untouched)"})
    elif splits.test_used and final_path.is_file():
        fin = json.loads(final_path.read_text(encoding="utf-8"))
        rows.append({"split": "test", "status": "already sealed — reporting final.json",
                     "seed": _num(SplitResult.from_dict(fin["test_baseline"])),
                     "best": _num(SplitResult.from_dict(fin["test"])),
                     "test_delta": fin.get("test_delta"),
                     "paired": (_compare(SplitResult.from_dict(fin["test_baseline"]),
                                         SplitResult.from_dict(fin["test"]),
                                         split="test", k_se=k_se, mode=mode)
                                .get("paired"))})
    else:
        adapter = load_adapter(project)
        fin = harness.finalize(adapter, run_dir=run_dir,
                               best_dir=run_dir.candidate_dir(best_id),
                               n_trials=n_trials,
                               baseline_dir=run_dir.candidate_dir("seed"))
        row = _compare(SplitResult.from_dict(fin["test_baseline"]),
                       SplitResult.from_dict(fin["test"]),
                       split="test", k_se=k_se, mode=mode)
        row["test_delta"] = fin.get("test_delta")
        row["status"] = "sealed now (once)"
        rows.append(row)

    payload = {
        "run_dir": str(run_dir.root),
        "seed_id": "seed",
        "best_id": best_id,
        "no_accepted_change": best_id == "seed",
        "n_trials": n_trials,
        "gate": {"mode": mode, "k_se": k_se},
        "holdout": holdout,
        "splits": rows,
        "val_per_task_movement": (_per_task_movement(seed_val, best_val)
                                  if seed_val and best_val else None),
        "spent": run_dir.spent.to_dict(),
        "screen_ledger": _screen_ledger(run_dir),
    }
    if best_id == "seed":
        payload["warning"] = ("best_id == 'seed': nothing cleared the val gate, so every "
                              "delta below is 0 by construction. Report this as a null "
                              "result with a diagnosed cause, not as a 0.000 improvement.")
    (run_dir.root / "measure.json").write_text(json.dumps(payload, indent=2),
                                               encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
