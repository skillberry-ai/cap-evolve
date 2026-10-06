#!/usr/bin/env python3
"""Write full_verified_probe/: full_verified's train/val and a FIXED 100-task test subset (#606).

The subset is drawn once, with a stated seed, stratified by instruction_type and by whether the
reused seed passed the task, in the same proportions as the parent test split. It is drawn only from test tasks where the reused seed has a valid score,
so every subset task is paired. The seed's stored per-task results from the frozen #538 slot give
the subset's no-skill baseline, which is recorded in subset_source.json for the runs to check against.

    python3 make_probe_subset.py --dataset <verified_400>/dataset.json --slot <frozen slot dir> [--write]

Needs core/ on PYTHONPATH (it scores the subset with the same code the runs use).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

SEED, N = 606, 100
UTILS = Path(__file__).resolve().parent
PARENT, PROBE = UTILS.parent / "full_verified", UTILS.parent / "full_verified_probe"
METRIC = "hard_no_recalc"


def digest(ids) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


def build(dataset: Path, slot: Path):
    sys.path.insert(0, str(UTILS))
    from rescore_run import _rescore_result  # noqa: E402 — same scoring as the runs

    split = json.loads((PARENT / "split_ids.json").read_text())
    kind = {str(x["id"]): x["instruction_type"] for x in json.loads(dataset.read_text())}
    seed_test = json.loads((slot / "run_suite/final.json").read_text())["seed"]["test"]
    rows = {str(p["task_id"]): p for p in seed_test["per_task"]}
    full = _rescore_result("test", seed_test, METRIC)
    # a task with no valid trial is excluded from the seed's reward; keep it out of the subset too
    scored_ids = {i for i, p in rows.items()
                  if _rescore_result("test", dict(seed_test, per_task=[p]), METRIC)["n_scored"]}
    test = sorted(set(split["test"]))
    pool = [i for i in test if i in scored_ids]
    types = sorted({kind[i] for i in test})
    share = {t: sum(kind[i] == t for i in test) for t in types}
    # Strata are (instruction_type, seed passed?). Type alone let a random draw land 8.5 points
    # above the parent's seed score (0.52 vs 0.435, seed 606); the seed outcome is known before
    # any variant runs, so stratifying on it keeps the subset's baseline and headroom the parent's.
    passed = {i: float(rows[i]["reward"]) >= 1.0 for i in pool}
    strata = sorted({(kind[i], passed[i]) for i in pool})
    size = {s: sum((kind[i], passed[i]) == s for i in pool) for s in strata}
    exact = {s: N * size[s] / len(pool) for s in strata}
    want_s = {s: int(exact[s]) for s in strata}
    for s in sorted(strata, key=lambda s: exact[s] - want_s[s], reverse=True)[:N - sum(want_s.values())]:
        want_s[s] += 1  # largest remainder
    rng = random.Random(SEED)
    sub = sorted(i for s in strata
                 for i in rng.sample(sorted(i for i in pool if (kind[i], passed[i]) == s), want_s[s]))
    want = {t: sum(kind[i] == t for i in sub) for t in types}
    sub_res = _rescore_result("test", dict(seed_test, per_task=[rows[i] for i in sub]), METRIC)
    out_split = {"train": sorted(split["train"]), "val": sorted(split["val"]), "test": sub}
    keep = set(out_split["train"]) | set(out_split["val"]) | set(sub)
    tasks = [dict(t, tag="full_verified_probe")
             for t in json.loads((PARENT / "tasks.json").read_text()) if str(t["id"]) in keep]
    source = {
        "seed": SEED, "parent": "full_verified", "metric": METRIC,
        "slot_run_id": json.loads((slot / "latest.json").read_text()).get("run_id"),
        "parent_split_sha256": {k: digest(v) for k, v in split.items()},
        "parent_test_by_type": share, "parent_test_unscored": sorted(set(test) - scored_ids),
        "counts_by_type": want,
        "counts_by_stratum": {f"{t} | seed {'pass' if p else 'fail'}": n for (t, p), n in want_s.items()},
        "counts": {k: len(v) for k, v in out_split.items()},
        "sha256_sorted_ids": {k: digest(v) for k, v in out_split.items()},
        "seed_test_reward_on_subset": sub_res["reward"],
        "seed_test_n_scored_on_subset": sub_res.get("n_scored"),
        "seed_test_reward_on_parent": full["reward"],
    }
    return out_split, tasks, source


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--slot", type=Path, required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    split, tasks, source = build(a.dataset, a.slot)
    print(json.dumps(source, indent=2))
    if a.write:
        PROBE.mkdir(exist_ok=True)
        (PROBE / "split_ids.json").write_text(json.dumps(split, indent=1, sort_keys=True) + "\n")
        (PROBE / "tasks.json").write_text(json.dumps(tasks, indent=2) + "\n")
        (PROBE / "subset_source.json").write_text(json.dumps(source, indent=2) + "\n")


if __name__ == "__main__":
    main()
