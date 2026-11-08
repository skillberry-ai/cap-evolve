#!/usr/bin/env python3
"""Record one v6_t4 eval suite's time, cost and tokens, plus its reward on F and on the test split.

Reads the per-task results the v5 evaluator writes (results/v5_<suite>/<task>/run/baseline.json,
via examples/parsec/v5/collect.py's own reader) and writes results/v6_t4_e1/eval/<suite>.json:

  cost   total eval $ / tokens / serial seconds over all tasks, plus wall-clock span (first job
         start to last result) from the result files' times
  reward per split (F, test): mean, task count, plus the paired delta against the Seed's v6_g2_e1
         10-trial measurement on the same tasks

Usage:  python3 examples/parsec/v6_t4/collect_evals.py --suite v6t4_m1
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

T4_DIR = Path(__file__).resolve().parent
REPO_ROOT = T4_DIR.parents[2]
sys.path.insert(0, str(T4_DIR.parent / "v5"))
import collect as v5collect  # noqa: E402

G2_RUN = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-ps-worktrees/"
              "parsec-intake_v6/.capevolve/v6_g2_e1/run_g2_e1")


def seed_scores() -> dict[str, dict[str, float]]:
    """{split: {task: Seed mean}} from v6_g2_e1: F = its Seed feedback sweep, test = FINAL_seed."""
    out: dict[str, dict[str, list[float]]] = {"feedback": {}, "test": {}}
    for split, tag in (("feedback", "seed"), ("test", "FINAL_seed")):
        for f in (G2_RUN / "rollouts" / split).glob(f"*__{tag}__t*.json"):
            rec = json.loads(f.read_text())
            if (rec.get("rollout") or {}).get("error"):
                continue
            out[split].setdefault(f.name.split("__")[0], []).append(float(rec["score"]["reward"]))
    return {s: {t: statistics.fmean(v) for t, v in d.items()} for s, d in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", required=True)
    ap.add_argument("--pool", nargs="+", metavar="SUITE",
                    help="pool these suites' trials per task (e.g. a 3-trial suite and its 2-trial top-up "
                         "at fresh seeds) into one 5-trial estimate; written as eval/<--suite>.json")
    args = ap.parse_args()
    if args.pool:
        return pooled(args.suite, args.pool)

    root = REPO_ROOT / "results" / f"v5_{args.suite}"
    splits = json.loads((G2_RUN / "splits.json").read_text())
    split_of = {t: "feedback" for t in splits["feedback"]} | {t: "test" for t in splits["test"]}
    seed = seed_scores()

    rows, times = [], []
    for task_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        b = task_dir / "run" / "baseline.json"
        if not b.is_file():
            continue
        r = v5collect.read_task_result(b, task_dir.name)
        if r is None:
            continue
        r["split"] = split_of.get(task_dir.name)
        rows.append(r)
        times.append(b.stat().st_mtime)
        if r.get("seconds"):
            times.append(b.stat().st_mtime - float(r["seconds"]))

    def tot(k):
        v = [r[k] for r in rows if r.get(k) is not None]
        return sum(v) if v else None

    reward = {}
    for split in ("feedback", "test"):
        ok = [r for r in rows if r["split"] == split and r["status"] == "ok" and r.get("reward") is not None]
        paired = [(float(r["reward"]), seed[split][r["task_id"]]) for r in ok if r["task_id"] in seed[split]]
        d = [a - b for a, b in paired]
        reward[split] = {"n_tasks": len(ok), "mean": statistics.fmean([a for a, _ in paired]) if paired else None,
                         "seed_mean_same_tasks": statistics.fmean([b for _, b in paired]) if paired else None,
                         "paired_delta": statistics.fmean(d) if d else None,
                         "delta_se": (statistics.stdev(d) / len(d) ** 0.5) if len(d) > 1 else None}
    out = {"suite": args.suite, "n_results": len(rows),
           "errored_tasks": sum(r["status"] == "errored" for r in rows),
           "cost": {"eval_usd": tot("cost_usd"), "eval_tokens": tot("tokens"),
                    "serial_seconds": tot("seconds"),
                    "wall_seconds": (max(times) - min(times)) if times else None,
                    "unmetered_tasks": sum(bool(r.get("unmetered")) for r in rows)},
           "reward": reward,
           "note": "3 trials per task. Seed = v6_g2_e1's 10-trial Seed measurement on the same tasks (paired). "
                   "delta_se is the standard error of the per-task paired delta."}
    dst = REPO_ROOT / "results" / "v6_t4_e1" / "eval" / f"{args.suite}.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"suite": args.suite, **out["cost"], "F": reward["feedback"], "test": reward["test"]}, indent=1))
    return 0


def pooled(name: str, suites: list[str]) -> int:
    """One estimate per task from every valid trial across ``suites`` (same bundle, disjoint seeds)."""
    splits = json.loads((G2_RUN / "splits.json").read_text())
    split_of = {t: "feedback" for t in splits["feedback"]} | {t: "test" for t in splits["test"]}
    seed = seed_scores()
    trials: dict[str, list[float]] = {}
    cost = {"eval_usd": 0.0, "eval_tokens": 0, "serial_seconds": 0.0}
    for s in suites:
        root = REPO_ROOT / "results" / f"v5_{s}"
        for task_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            b = task_dir / "run" / "baseline.json"
            if not b.is_file():
                continue
            r = v5collect.read_task_result(b, task_dir.name)
            if r is None:
                continue
            trials.setdefault(task_dir.name, []).extend(float(x) for x in (r.get("trial_rewards") or []))
            for k, f in (("eval_usd", "cost_usd"), ("eval_tokens", "tokens"), ("serial_seconds", "seconds")):
                cost[k] += r.get(f) or 0
    reward = {}
    for split in ("feedback", "test"):
        rows = [(t, statistics.fmean(v), len(v)) for t, v in trials.items() if split_of.get(t) == split and v]
        paired = [(m, seed[split][t]) for t, m, _ in rows if t in seed[split]]
        d = [a - b for a, b in paired]
        reward[split] = {"n_tasks": len(paired), "trials_per_task": sorted({n for _, _, n in rows}),
                         "mean": statistics.fmean([a for a, _ in paired]) if paired else None,
                         "seed_mean_same_tasks": statistics.fmean([b for _, b in paired]) if paired else None,
                         "paired_delta": statistics.fmean(d) if d else None,
                         "delta_se": (statistics.stdev(d) / len(d) ** 0.5) if len(d) > 1 else None}
    out = {"suite": name, "pooled_from": suites, "cost": cost, "reward": reward,
           "note": "Trials pooled per task across the listed suites (same bundle, disjoint seeds). Seed = "
                   "v6_g2_e1's 10-trial Seed measurement on the same tasks (paired). Errored trials are "
                   "absent, never scored as 0."}
    dst = REPO_ROOT / "results" / "v6_t4_e1" / "eval" / f"{name}.json"
    dst.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"suite": name, **cost, "F": reward["feedback"], "test": reward["test"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
