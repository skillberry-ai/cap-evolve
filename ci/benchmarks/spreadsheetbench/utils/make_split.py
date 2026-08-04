#!/usr/bin/env python3
"""Generate the deterministic held-out train/selection/test split for SpreadsheetBench full.

WHY THIS EXISTS
    The default CI split for every benchmark tier is a NO-HOLDOUT FIT split
    (train == val == test == all tier tasks; see ci/benchmarks/lib/run_suite.sh). That is
    honest for smoke — the report labels it a FIT metric — but it cannot be compared against
    a paper that reports held-out test scores. SkillOpt (arXiv 2605.23904) does, so a
    SkillOpt comparison needs a genuinely disjoint split.

WHAT THIS REPRODUCES, AND WHAT IT DOES NOT
    From the paper:
      - ``split_seed = 42``                                     (stated globally)
      - a "default 2:1:7 split when no benchmark-specific split is stated" (Appendix C),
        which the train-size ablation protocol repeats.
    NOT from the paper — these are OUR choices, because the paper does not report them:
      - No SpreadsheetBench-specific split is given, so the 2:1:7 default is applied.
      - No SpreadsheetBench task count is given, so ALL 912 tasks of the original
        benchmark are used.
      - Table 2's caption states 4:1:5 for an *ablation panel*. Two other mentions say
        2:1:7, so 2:1:7 is taken as the headline configuration. Regenerate with
        ``--ratios 4,1,5`` if that reading turns out to be wrong.

    So the committed split is a documented RECONSTRUCTION of SkillOpt's stated default, not
    a reproduction of their actual split. Any comparison must say so.

DETERMINISM
    ids are sorted into a canonical order first, then shuffled with ``random.Random(seed)``,
    so the output depends only on (task id set, seed, ratios) — not on dict/file ordering.
    Re-running reproduces the committed file byte for byte, which a test asserts.

USAGE
    python3 ci/benchmarks/spreadsheetbench/utils/make_split.py            # print to stdout
    python3 ci/benchmarks/spreadsheetbench/utils/make_split.py --write    # write full/split_ids.json
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH_DIR = HERE.parent
DEFAULT_TASKS = BENCH_DIR / "full" / "tasks.json"
DEFAULT_OUT = BENCH_DIR / "full" / "split_ids.json"

SKILLOPT_SEED = 42
SKILLOPT_RATIOS = (2, 1, 7)  # train : selection(val) : test


def build_split(ids: list[str], *, seed: int, ratios: tuple[int, int, int]) -> dict:
    """Partition ``ids`` into disjoint train/val/test by ``ratios``, deterministically.

    Sizes use floor for train and val and give the remainder to test, so the three parts
    always sum to len(ids) exactly with no id dropped or duplicated.
    """
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"duplicate task ids in input: {dupes[:5]}")
    total_parts = sum(ratios)
    if total_parts <= 0:
        raise ValueError(f"ratios must be positive, got {ratios}")

    ordered = sorted(ids)                 # canonical order -> reproducible regardless of input order
    random.Random(seed).shuffle(ordered)

    n = len(ordered)
    n_train = n * ratios[0] // total_parts
    n_val = n * ratios[1] // total_parts
    train = ordered[:n_train]
    val = ordered[n_train:n_train + n_val]
    test = ordered[n_train + n_val:]

    assert len(train) + len(val) + len(test) == n, "split must cover every id exactly once"
    assert not (set(train) & set(val)), "train/val overlap"
    assert not (set(train) & set(test)), "train/test overlap"
    assert not (set(val) & set(test)), "val/test overlap"

    # Sort each part for a stable, reviewable diff. Order within a split does not affect
    # evaluation (the harness keys by task id), only readability of the committed file.
    return {"train": sorted(train), "val": sorted(val), "test": sorted(test)}


def load_task_ids(tasks_json: Path) -> list[str]:
    entries = json.loads(tasks_json.read_text(encoding="utf-8"))
    return [str(e["id"]) for e in entries]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasks", type=Path, default=DEFAULT_TASKS,
                    help=f"tier tasks.json to split (default: {DEFAULT_TASKS})")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help=f"where --write puts the split (default: {DEFAULT_OUT})")
    ap.add_argument("--seed", type=int, default=SKILLOPT_SEED,
                    help=f"split seed (default {SKILLOPT_SEED}, SkillOpt's stated split_seed)")
    ap.add_argument("--ratios", default=",".join(str(r) for r in SKILLOPT_RATIOS),
                    help="train,val,test integer ratios (default 2,1,7 — SkillOpt's stated default)")
    ap.add_argument("--write", action="store_true", help="write --out instead of printing")
    args = ap.parse_args(argv)

    ratios = tuple(int(x) for x in str(args.ratios).split(","))
    if len(ratios) != 3:
        ap.error(f"--ratios needs exactly three values, got {args.ratios!r}")

    ids = load_task_ids(args.tasks)
    split = build_split(ids, seed=args.seed, ratios=ratios)  # type: ignore[arg-type]
    payload = json.dumps(split, indent=2, sort_keys=True) + "\n"

    if args.write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
        print(f"wrote {args.out}: "
              f"train={len(split['train'])} val={len(split['val'])} test={len(split['test'])} "
              f"(seed={args.seed} ratios={':'.join(str(r) for r in ratios)})")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
