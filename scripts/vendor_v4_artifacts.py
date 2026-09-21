#!/usr/bin/env python3
"""Vendor each T2-optimized task's candidate bundles from parsec-intake_v4's
gitignored .capevolve/ tree into artifacts/v4/<task>/{best,rejected,discarded}/.

Usage: python3 scripts/vendor_v4_artifacts.py [--check] [--only TASK_ID]
  --check   exit 1 if any destination file would change, instead of writing it.
  --only    vendor a single task (for iterating without re-copying all 21).
"""
import filecmp
import glob
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = ROOT / "results" / "v4" / "results.json"
ARTIFACTS_V4 = ROOT / "artifacts" / "v4"
SOURCE_ROOT = Path(
    "/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v4"
)


def copy_dir(src, dst, check_only, changed):
    """Copy every file directly under src/ into dst/, tracking changed paths."""
    for s in sorted(p for p in src.iterdir() if p.is_file()):
        d = dst / s.name
        if d.exists() and filecmp.cmp(s, d, shallow=False):
            continue
        changed.append(str(d.relative_to(ROOT)))
        if not check_only:
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)


def vendor_task(row, changed, check_only):
    task = row["task"]
    run_dir = SOURCE_ROOT / row["run_dir"]
    best_tag = row["best_tag"]
    dest = ARTIFACTS_V4 / task

    if best_tag == "seed":
        note = dest / "NOTE.md"
        text = (
            f"# {task} -- best candidate is the seed\n\n"
            f"T2's optimizer ran on this task (`{row['run_dir']}`) but no candidate "
            f"beat the seed bundle on validation (`best_tag: \"seed\"` in "
            f"`results/v4/results.json`). There is no separate `best/` bundle to "
            f"vendor here -- it is byte-identical to `../seed/`.\n"
        )
        if not (note.exists() and note.read_text() == text):
            changed.append(str(note.relative_to(ROOT)))
            if not check_only:
                dest.mkdir(parents=True, exist_ok=True)
                note.write_text(text)
    else:
        copy_dir(run_dir / "candidates" / best_tag, dest / "best", check_only, changed)

    cand_dirs = sorted(p.name for p in (run_dir / "candidates").iterdir()
                        if p.is_dir() and p.name.startswith("cand_"))
    for cand in cand_dirs:
        if cand == best_tag:
            continue
        copy_dir(run_dir / "candidates" / cand, dest / "rejected" / cand, check_only, changed)

    all_run_dirs = sorted(glob.glob(str(SOURCE_ROOT / f".capevolve/v4_t2_e1_{task}/run_*")))
    if len(all_run_dirs) > 1:
        canonical = str(run_dir)
        for other in all_run_dirs:
            if other == canonical:
                continue
            run_ts = Path(other).name
            other_cands = sorted(p.name for p in (Path(other) / "candidates").iterdir()
                                  if p.is_dir() and p.name.startswith("cand_"))
            for cand in other_cands:
                copy_dir(Path(other) / "candidates" / cand,
                         dest / "discarded" / f"{run_ts}-{cand}", check_only, changed)


def main():
    check_only = "--check" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None

    results = json.loads(RESULTS_JSON.read_text())
    rows = [r for r in results["task_ledger"] if r["status"] == "optimized"]
    if only:
        rows = [r for r in rows if r["task"] == only]
    assert rows, "no optimized task rows found"

    changed = []
    for row in rows:
        vendor_task(row, changed, check_only)

    if not changed:
        print("artifacts/v4/ already up to date.")
        return 0
    if check_only:
        print(f"{len(changed)} file(s) would change under artifacts/v4/:", file=sys.stderr)
        for c in changed:
            print(f"  {c}", file=sys.stderr)
        return 1

    print(f"Wrote/updated {len(changed)} file(s) under artifacts/v4/ for {len(rows)} task(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
