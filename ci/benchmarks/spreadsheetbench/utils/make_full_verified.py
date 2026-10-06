#!/usr/bin/env python3
"""Generate the `full_verified` tier's task list from the VERIFIED 400-task SpreadsheetBench release.

WHY THIS EXISTS — AND WHY IT NEEDS THE ARCHIVE

All 400 verified ids also appear in the original 912-task set, so it looks as though this tier
could be produced by filtering ``full/tasks.json``. It cannot. The verified release is a
re-release with corrected content, not a curated subset:

    - 226 of the 400 instructions were REWRITTEN (several substantively — e.g. 17-35 goes from
      "How can I successfully filtering dates…" to an imperative with an added requirement)
    - 4 answer_positions changed
    - 61 of 394 resolvable golden workbooks differ byte-for-byte from the 912 answer
    - ONE graded test case per task instead of three, under different filenames

So the id list must come from the verified archive's own ``dataset.json``. Filtering the 912
would score the OLD benchmark while claiming comparability with work that reports the new one.

The archive is deliberately not vendored (it is 15MB of xlsx blobs). Fetch it first:

    SPREADSHEETBENCH_VARIANT=verified_400 ci/benchmarks/spreadsheetbench/fetch_data.sh

which prints the extracted dataset root to pass as ``--data-dir``.

USAGE
    # tasks.json only (prints to stdout)
    python3 ci/benchmarks/spreadsheetbench/utils/make_full_verified.py --data-dir <root>

    # write tasks.json AND its split, in one go
    python3 ci/benchmarks/spreadsheetbench/utils/make_full_verified.py --data-dir <root> --write

The split itself is produced by the SAME generator `full` uses (make_split.py, seed 42,
2:1:7) — see that file for the provenance of those numbers. 2:1:7 over 400 gives 80/40/280,
which is exactly what WikiSkill (arXiv 2608.27454v1) Table 6 publishes for SpreadSheet.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH_DIR = HERE.parent
TIER_DIR = BENCH_DIR / "full_verified"
TASKS_OUT = TIER_DIR / "tasks.json"
SPLIT_OUT = TIER_DIR / "split_ids.json"

EXPECTED_TASKS = 400
# full_verified must differ from `full` in the DATASET only, so the two numbers stay comparable to
# each other. Changing the agent model is a separate, deliberate decision.
AGENT_MODEL = "aws/gpt-oss-120b"
TAG = "full_verified"


def load_verified_ids(data_dir: Path) -> list[str]:
    """Read the verified release's own id list, and refuse anything that is not it."""
    dataset = data_dir / "dataset.json"
    if not dataset.exists():
        raise SystemExit(
            f"{dataset} not found. --data-dir must point at the extracted verified_400 root "
            f"(fetch it with `SPREADSHEETBENCH_VARIANT=verified_400 "
            f"ci/benchmarks/spreadsheetbench/fetch_data.sh`)."
        )
    entries = json.loads(dataset.read_text(encoding="utf-8"))
    ids = [str(e["id"]) for e in entries]
    if len(ids) != EXPECTED_TASKS:
        raise SystemExit(
            f"{dataset} has {len(ids)} tasks, expected {EXPECTED_TASKS}. This is probably the "
            f"912-task or 200-task archive — those are DIFFERENT benchmarks (see this file's "
            f"docstring), not supersets of the verified 400."
        )
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate ids in the verified dataset.json")
    return ids


def build_tasks(ids: list[str]) -> list[dict]:
    """One entry per task, ordered exactly as the archive lists them (stable, reviewable)."""
    return [{"id": i, "tag": TAG, "agent": AGENT_MODEL} for i in ids]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, required=True,
                    help="extracted spreadsheetbench_verified_400/ root (contains dataset.json)")
    ap.add_argument("--write", action="store_true",
                    help=f"write {TASKS_OUT.name} and {SPLIT_OUT.name} instead of printing")
    args = ap.parse_args(argv)

    payload = json.dumps(build_tasks(load_verified_ids(args.data_dir)), indent=2) + "\n"

    if not args.write:
        print(payload, end="")
        return 0

    TIER_DIR.mkdir(parents=True, exist_ok=True)
    TASKS_OUT.write_text(payload, encoding="utf-8")
    print(f"wrote {TASKS_OUT}: {EXPECTED_TASKS} tasks (agent={AGENT_MODEL})")

    # Delegate the partition to the generator `full` uses, so both tiers share one provenance.
    subprocess.run(
        [sys.executable, str(HERE / "make_split.py"),
         "--tasks", str(TASKS_OUT), "--out", str(SPLIT_OUT), "--write"],
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
