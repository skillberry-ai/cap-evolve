#!/usr/bin/env python3
"""Re-score a kept spreadsheetbench run dir IN PLACE so its reward is another recorded metric.

Every rollout records all four spreadsheetbench metrics (soft/hard x recalc/as-saved), so a run
measured under one reward can be re-read under another without re-running anything. Used on a
COPY of the kept latest run before `reuse_baseline`, so a run with the as-saved reward is not
gated against a seed baseline that was measured with recalculation.

    rescore_run.py <run_dir> --metric hard_no_recalc

Rewrites each rollout's `score.reward`, `primary` settings and pass-count feedback, then
rebuilds `baseline.json` (val, train) and the seed's test result in `final.json` from the
rewritten rollouts.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "core"))

from cap_evolve.harness import split_result_from_rollouts  # noqa: E402
from cap_evolve.loop import aggregate_scores  # noqa: E402
from cap_evolve.rundir import RunDir  # noqa: E402
from cap_evolve.types import Score  # noqa: E402

_PASSED = re.compile(r"^\d+/\d+ test cases passed")
_FORMULA_NOTE = (
    "Test case(s) {cases} FAILED because the answer cells hold FORMULAS: the grader reads the "
    "values saved in the file and does not recalculate, so a formula written with openpyxl reads "
    "back as empty. The formula logic itself was right — compute the result in Python and write "
    "the literal value instead."
)


def _rescore_rollout(path: Path, metric: str) -> None:
    rec = json.loads(path.read_text(encoding="utf-8"))
    sc = rec.get("score") or {}
    metrics = sc.get("metrics") or []
    values = {m.get("name"): m.get("value") for m in metrics}
    if metric not in values:
        return  # errored or pre-metric rollout: nothing to re-read, leave it as scored
    sc["reward"] = float(values[metric])
    for m in metrics:
        m["primary"] = m.get("name") == metric
    raw = sc.get("raw") or {}
    graded_key = "test_case_results_no_recalc" if metric.endswith("_no_recalc") else "test_case_results"
    graded, recalc = raw.get(graded_key), raw.get("test_case_results")
    if isinstance(graded, list) and graded and isinstance(sc.get("feedback"), str):
        fb = _PASSED.sub(f"{sum(graded)}/{len(graded)} test cases passed", sc["feedback"], count=1)
        if graded_key != "test_case_results" and isinstance(recalc, list):
            only = [i + 1 for i, (r, n) in enumerate(zip(recalc, graded)) if r and not n]
            if only:
                fb = fb.replace(" All checks passed.", "") + " " + _FORMULA_NOTE.format(cases=only)
        sc["feedback"] = fb
    raw["reward_metric"] = metric
    sc["raw"] = raw
    rec["score"] = sc
    path.write_text(json.dumps(rec, default=str), encoding="utf-8")


def _rescore_result(split: str, result: dict, metric: str) -> dict:
    """Re-score a stored SplitResult dict from its per-task metrics.

    For a split with no rollouts on disk — a seed test score that was itself carried over by an
    earlier reuse exists only as this stored result.
    """
    scores = []
    for pt in result.get("per_task") or []:
        metrics = [dict(m) for m in pt.get("metrics") or []]
        values = {m.get("name"): m.get("value") for m in metrics}
        reward = float(values[metric]) if metric in values else float(pt.get("reward") or 0.0)
        for m in metrics:
            m["primary"] = m.get("name") == metric
        n = int(pt.get("n") or 1)
        scores.append(Score(task_id=pt["task_id"], reward=reward, feedback=pt.get("feedback", ""),
                            n=n, trial_rewards=[reward] * n, raw=pt.get("raw") or {},
                            metrics=metrics if metric in values else []))
    return aggregate_scores(split, scores).to_dict()


def _split(rd: RunDir, tag: str, split: str, stored: dict | None, metric: str) -> dict:
    sr = split_result_from_rollouts(rd, tag, split)
    if sr.per_task:
        return sr.to_dict()
    if stored and stored.get("per_task"):
        return _rescore_result(split, stored, metric)
    raise SystemExit(f"::error:: no {split} result to re-score for tag {tag!r}: no rollouts and no stored result")


def rescore(run_dir: Path, metric: str, test_ids: set[str] | None = None) -> dict:
    for f in sorted((run_dir / "rollouts").glob("*/*.json")):
        _rescore_rollout(f, metric)
    rd = RunDir.open(run_dir)
    out = {}

    baseline = json.loads((run_dir / "baseline.json").read_text(encoding="utf-8"))
    baseline["val"] = _split(rd, "seed", "val", baseline.get("val"), metric)
    out["val"] = baseline["val"]["reward"]
    if "train" in baseline:
        baseline["train"] = _split(rd, "seed", "train", baseline.get("train"), metric)
        out["train"] = baseline["train"]["reward"]
    baseline["reward_metric"] = metric
    (run_dir / "baseline.json").write_text(json.dumps(baseline, indent=2), encoding="utf-8")

    final_p = run_dir / "final.json"
    if final_p.exists():
        final = json.loads(final_p.read_text(encoding="utf-8"))
        seed_is_best = final.get("best_id") == "seed"
        # The seed's test rollouts are missing when this run REUSED its seed test score; the
        # stored seed result is then the only record, and is re-scored from its metrics.
        stored = (final.get("seed") or {}).get("test") or final.get("test_baseline")
        test = _split(rd, "FINAL" if seed_is_best else "FINAL_seed", "test", stored, metric)
        if test_ids is not None:
            # exp #606: a probe tier tests on a SUBSET of the kept run's test split, so the reused
            # seed test score must be the one measured on exactly those tasks.
            rows = [pt for pt in test.get("per_task") or [] if str(pt["task_id"]) in test_ids]
            missing = test_ids - {str(pt["task_id"]) for pt in rows}
            if missing:
                raise SystemExit(f"::error:: the kept seed has no test row for {sorted(missing)}")
            test = _rescore_result("test", dict(test, per_task=rows), metric)
        final["test_baseline"] = test
        final.setdefault("seed", {})["test"] = test
        if seed_is_best:
            final["test"] = test
        final["reward_metric"] = metric
        final_p.write_text(json.dumps(final, indent=2), encoding="utf-8")
        out["test"] = test["reward"]
    if test_ids is not None:
        splits_p = run_dir / "splits.json"
        splits = json.loads(splits_p.read_text(encoding="utf-8"))
        splits["test"] = sorted(test_ids)
        splits_p.write_text(json.dumps(splits, indent=2), encoding="utf-8")
        out["test_n"] = len(test_ids)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--metric", required=True,
                    choices=["soft_restriction", "hard_restriction", "soft_no_recalc", "hard_no_recalc"])
    ap.add_argument("--test-subset", type=Path, default=None,
                    help="split_ids.json whose `test` ids the seed test result is restricted to")
    args = ap.parse_args()
    test_ids = None
    if args.test_subset:
        test_ids = set(map(str, json.loads(args.test_subset.read_text(encoding="utf-8"))["test"]))
    print(json.dumps({"rescored": str(args.run_dir), "metric": args.metric,
                      **rescore(args.run_dir, args.metric, test_ids)}))


if __name__ == "__main__":
    main()
