#!/usr/bin/env python3
"""Generate the SpreadsheetBench `smoke` tier — 10 tasks that are ALSO part of `full_verified`.

WHY THIS EXISTS

Smoke is the cheap signal that guards the tiers we report. It used to be an arbitrary 10 tasks
from the 200-task sample with no relation to any reported roster, and that is precisely how the
verified-release scoring bug survived review: smoke ran three graded cases per task on
`sample_200` and passed green, while `full_verified` would have scored 0.000 on all 400 tasks.
A green smoke has to mean something about the tier whose numbers get published.

THE SELECTION RULE

    pool = sample_200 ids  ∩  full_verified TRAIN ids

Both halves are load-bearing:

  - ``sample_200`` because that is the dataset the smoke tier actually evaluates (see
    ci/benchmarks/lib/ci_setup.sh). An id outside it cannot be scored — and as of this change
    the adapter REFUSES such a run rather than silently shrinking it.
  - ``full_verified``'s **train** split, not its whole roster, because smoke runs a real (if
    short) optimization. Drawing it from the selection or sealed-test splits would tune against
    tasks whose scores get reported — the same reason `pilot` is restricted to full's train ids.

Within the pool, candidates that are ALSO outside `full`'s sealed test split are preferred, so
smoke overlaps the other reported tier as little as the pool allows. Both instruction types are
kept represented: Cell-Level and Sheet-Level exercise different comparison paths, and a smoke
set of only one type silently stops guarding the other.

WHAT THIS DOES *NOT* GUARANTEE

The smoke tier evaluates each task using `sample_200`'s copy of it. For ids the verified release
rewrote (226 of its 400 instructions changed), smoke therefore grades the OLDER wording. Smoke
tasks are part of `full_verified` **by id**, not by content. That is deliberate: keeping smoke on
`sample_200` is what preserves cheap coverage of the THREE-graded-case path that `full` and
`pilot` depend on — the verified release's single-case layout is covered by unit tests
(core/tests/test_spreadsheetbench_case_layout.py) rather than by a paid rollout.

USAGE
    data=$(SPREADSHEETBENCH_VARIANT=sample_200 ci/benchmarks/spreadsheetbench/fetch_data.sh)
    python3 ci/benchmarks/spreadsheetbench/utils/make_smoke.py --data-dir "$data"          # print
    python3 ci/benchmarks/spreadsheetbench/utils/make_smoke.py --data-dir "$data" --write  # write

PREREQUISITE: full/split_ids.json and full_verified/split_ids.json (both normally already
committed) must exist before running this script — it reads both to build the selection pool
and does not generate either itself. Produce them first if missing:
    python3 ci/benchmarks/spreadsheetbench/utils/make_split.py --write
    python3 ci/benchmarks/spreadsheetbench/utils/make_full_verified.py --data-dir <verified_400 root> --write
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH_DIR = HERE.parent
SMOKE_OUT = BENCH_DIR / "smoke" / "tasks.json"
VERIFIED_SPLIT = BENCH_DIR / "full_verified" / "split_ids.json"
FULL_SPLIT = BENCH_DIR / "full" / "split_ids.json"

N_TASKS = 10
MIN_PER_TYPE = 3          # both instruction types must be a real presence, not a token one
SEED = 42                 # same seed the splits use, for one provenance story
AGENT = "aws/gpt-oss-120b"
TAG = "repr"

_TYPE_KEY = {"Cell-Level Manipulation": "cell", "Sheet-Level Manipulation": "sheet"}


def build_smoke(sample_ids: dict[str, str], verified_train: set[str],
                full_test: set[str], *, seed: int = SEED,
                n: int = N_TASKS, min_per_type: int = MIN_PER_TYPE) -> list[dict]:
    """Pick `n` smoke tasks deterministically from sample_200 ∩ full_verified.train.

    ``sample_ids`` maps id -> instruction_type for everything in the smoke dataset.
    Selection depends only on (id set, types, seed), never on file ordering.
    """
    pool = sorted(set(sample_ids) & verified_train)
    if len(pool) < n:
        raise SystemExit(
            f"only {len(pool)} ids are in both sample_200 and full_verified's train split; "
            f"need {n}. Widening the pool means relaxing one of the two constraints — see this "
            f"file's docstring before doing that."
        )

    rng = random.Random(seed)
    # Prefer candidates outside full's sealed test split, so smoke overlaps the OTHER reported
    # tier as little as the pool allows. Shuffle within each band for a stable, unbiased pick.
    preferred = [i for i in pool if i not in full_test]
    fallback = [i for i in pool if i in full_test]
    rng.shuffle(preferred)
    rng.shuffle(fallback)
    ordered = preferred + fallback

    chosen: list[str] = []
    # First satisfy the per-type floor, then fill in preference order.
    for want_type in ("cell", "sheet"):
        for i in ordered:
            if len([c for c in chosen if _TYPE_KEY[sample_ids[c]] == want_type]) >= min_per_type:
                break
            if i not in chosen and _TYPE_KEY[sample_ids[i]] == want_type:
                chosen.append(i)
    for i in ordered:
        if len(chosen) >= n:
            break
        if i not in chosen:
            chosen.append(i)

    if len(chosen) != n:
        raise SystemExit(f"selected {len(chosen)} tasks, expected {n}")
    for t in ("cell", "sheet"):
        got = len([c for c in chosen if _TYPE_KEY[sample_ids[c]] == t])
        if got < min_per_type:
            raise SystemExit(f"only {got} {t}-level tasks in the pool; need {min_per_type}")

    # Sorted output for a reviewable diff; the harness keys by task id, so order is cosmetic.
    return [{"id": i, "tag": TAG, "agent": AGENT, "type": _TYPE_KEY[sample_ids[i]]}
            for i in sorted(chosen)]


def load_split_ids(path: Path, key: str, *, generator_hint: str) -> set[str]:
    """Read one id set out of a `split_ids.json`, refusing with a clear message if it's missing.

    Unlike `make_full_verified.py`'s own `load_verified_ids()`, this file has no fallback if
    its two split files aren't there yet — surface that as a helpful SystemExit instead of a
    raw FileNotFoundError.
    """
    if not path.exists():
        raise SystemExit(f"{path} not found. Generate it first: {generator_hint}")
    return {str(i) for i in json.loads(path.read_text(encoding="utf-8"))[key]}


def load_sample_types(data_dir: Path) -> dict[str, str]:
    ds = data_dir / "dataset.json"
    if not ds.exists():
        raise SystemExit(
            f"{ds} not found. --data-dir must point at the extracted sample_200 root "
            f"(SPREADSHEETBENCH_VARIANT=sample_200 ci/benchmarks/spreadsheetbench/fetch_data.sh)."
        )
    entries = json.loads(ds.read_text(encoding="utf-8"))
    unknown = {e["instruction_type"] for e in entries} - set(_TYPE_KEY)
    if unknown:
        raise SystemExit(f"unrecognized instruction_type(s) in {ds}: {sorted(unknown)}")
    return {str(e["id"]): e["instruction_type"] for e in entries}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, required=True,
                    help="extracted sample_data_200/ root (the dataset the smoke tier evaluates)")
    ap.add_argument("--write", action="store_true", help=f"write {SMOKE_OUT.name}")
    args = ap.parse_args(argv)

    tasks = build_smoke(
        load_sample_types(args.data_dir),
        load_split_ids(VERIFIED_SPLIT, "train", generator_hint=(
            "python3 ci/benchmarks/spreadsheetbench/utils/make_full_verified.py "
            "--data-dir <verified_400 root> --write")),
        load_split_ids(FULL_SPLIT, "test", generator_hint=(
            "python3 ci/benchmarks/spreadsheetbench/utils/make_split.py --write")),
    )
    payload = json.dumps(tasks, indent=2) + "\n"

    if args.write:
        SMOKE_OUT.write_text(payload, encoding="utf-8")
        kinds = {}
        for t in tasks:
            kinds[t["type"]] = kinds.get(t["type"], 0) + 1
        print(f"wrote {SMOKE_OUT}: {len(tasks)} tasks {kinds} (seed={SEED}, agent={AGENT})")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
