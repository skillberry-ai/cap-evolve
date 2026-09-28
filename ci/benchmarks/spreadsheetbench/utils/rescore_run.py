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
from cap_evolve.rundir import RunDir  # noqa: E402

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


def rescore(run_dir: Path, metric: str) -> dict:
    for f in sorted((run_dir / "rollouts").glob("*/*.json")):
        _rescore_rollout(f, metric)
    rd = RunDir.open(run_dir)
    out = {}

    baseline = json.loads((run_dir / "baseline.json").read_text(encoding="utf-8"))
    val = split_result_from_rollouts(rd, "seed", "val")
    baseline["val"] = val.to_dict()
    out["val"] = val.reward
    if "train" in baseline:
        train = split_result_from_rollouts(rd, "seed", "train")
        baseline["train"] = train.to_dict()
        out["train"] = train.reward
    baseline["reward_metric"] = metric
    (run_dir / "baseline.json").write_text(json.dumps(baseline, indent=2), encoding="utf-8")

    final_p = run_dir / "final.json"
    if final_p.exists():
        final = json.loads(final_p.read_text(encoding="utf-8"))
        seed_is_best = final.get("best_id") == "seed"
        test = split_result_from_rollouts(rd, "FINAL" if seed_is_best else "FINAL_seed", "test").to_dict()
        final["test_baseline"] = test
        final.setdefault("seed", {})["test"] = test
        if seed_is_best:
            final["test"] = test
        final["reward_metric"] = metric
        final_p.write_text(json.dumps(final, indent=2), encoding="utf-8")
        out["test"] = test["reward"]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--metric", required=True,
                    choices=["soft_restriction", "hard_restriction", "soft_no_recalc", "hard_no_recalc"])
    args = ap.parse_args()
    print(json.dumps({"rescored": str(args.run_dir), "metric": args.metric,
                      **rescore(args.run_dir, args.metric)}))


if __name__ == "__main__":
    main()
