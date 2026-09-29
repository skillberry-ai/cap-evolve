#!/usr/bin/env python3
"""Vendor the G2 (v4_g_e1) run's candidate bundles into
artifacts/v4/v4_g_e1/{best,rejected}/.

Unlike T2, G2 evolved one shared bundle jointly across all 34 tasks, so
there is a single best/ and a single set of rejected/ candidates -- no
per-task split.

Usage: python3 scripts/vendor_v4_g_artifacts.py [--run-dir DIR] [--check]
  --run-dir   the optimizer run directory to vendor from (default: the
              canonical v4_g2_e1 optimize run in the parsec_g2 worktree).
  --check     exit 1 if any destination file would change, instead of
              writing it.
"""
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = ROOT / "results" / "v4" / "v4_g_e1" / "results.json"
ARTIFACTS_G = ROOT / "artifacts" / "v4" / "v4_g_e1"
DEFAULT_RUN_DIR = (
    ROOT.parent / "parsec_g2" / ".capevolve" / "v4_g2_e1"
    / "run_optimize_fix_20260925_082813"
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


def main():
    check_only = "--check" in sys.argv
    run_dir = DEFAULT_RUN_DIR
    if "--run-dir" in sys.argv:
        run_dir = Path(sys.argv[sys.argv.index("--run-dir") + 1])

    import json
    results = json.loads(RESULTS_JSON.read_text())
    best_id = results["best_id_overall"]

    changed = []
    copy_dir(run_dir / "candidates" / best_id, ARTIFACTS_G / "best", check_only, changed)

    cand_dirs = sorted(p.name for p in (run_dir / "candidates").iterdir()
                        if p.is_dir() and p.name.startswith("cand_"))
    for cand in cand_dirs:
        if cand == best_id:
            continue
        copy_dir(run_dir / "candidates" / cand, ARTIFACTS_G / "rejected" / cand, check_only, changed)

    if not changed:
        print("artifacts/v4/v4_g_e1/{best,rejected}/ already up to date.")
        return 0
    if check_only:
        print(f"{len(changed)} file(s) stale:", file=sys.stderr)
        for c in changed:
            print(f"  {c}", file=sys.stderr)
        return 1

    print(f"Wrote/updated {len(changed)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
