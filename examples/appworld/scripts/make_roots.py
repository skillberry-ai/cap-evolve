"""Build root_opt (search-time APPWORLD_ROOT) from root_full: train + dev tasks only, no test files.

Usage: python make_roots.py   (paths from awpaths; AW_EVAL overrides /tmp/aw_eval)

Also writes the lint cache ($AW_EVAL/lint_cache.json) from root_opt. The optimizer lints its
candidate from that cache, because root_opt is hidden from it (README: Isolation).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "adapters"))
from awpaths import EVAL, EXPECTED_COUNTS, ROOT_FULL, ROOT_OPT, SPLITS, read_split, sha256_file, sha256_tree, update_manifest  # noqa: E402

import lints  # noqa: E402

LINT_CACHE = EVAL / "lint_cache.json"


def build_lint_cache(root_opt: Path = ROOT_OPT, cache: Path = LINT_CACHE) -> Path:
    """Write the lint cache from ``root_opt``, world-readable, never from root_full."""
    out = lints.write_cache(root=root_opt, cache=cache)
    os.chmod(out, 0o644)
    return out


def main() -> int:
    counts = {s: len(read_split(s)) for s in SPLITS}
    if counts != EXPECTED_COUNTS:
        print(f"split counts {counts} != {EXPECTED_COUNTS}", file=sys.stderr)
        return 1
    keep = set(read_split("train")) | set(read_split("dev"))
    test_ids = set(read_split("test_normal")) | set(read_split("test_challenge"))
    src, dst = ROOT_FULL / "data", ROOT_OPT / "data"
    if ROOT_OPT.exists():
        shutil.rmtree(ROOT_OPT)
    dst.mkdir(parents=True)
    for item in src.iterdir():
        if item.name in ("tasks", "datasets"):
            continue
        (shutil.copytree if item.is_dir() else shutil.copy2)(item, dst / item.name)
    (dst / "datasets").mkdir()
    for s in ("train", "dev"):
        shutil.copy2(src / "datasets" / f"{s}.txt", dst / "datasets" / f"{s}.txt")
    (dst / "tasks").mkdir()
    for tid in sorted(keep | {"_base_"}):
        shutil.copytree(src / "tasks" / tid, dst / "tasks" / tid)

    # No test id may appear anywhere under root_opt, in names or in content.
    hits = []
    for p in ROOT_OPT.rglob("*"):
        if any(t in str(p) for t in test_ids):
            hits.append(str(p))
        elif p.is_file():
            text = p.read_bytes().decode("utf-8", "ignore")
            hits += [f"{p}:{t}" for t in test_ids if t in text]
    if hits:
        print(f"test ids found under root_opt: {hits[:10]} (total {len(hits)})", file=sys.stderr)
        return 1
    n_tasks = sum(1 for _ in (dst / "tasks").iterdir()) - 1
    cache = build_lint_cache()
    update_manifest(root_opt={"tasks": n_tasks, "test_id_hits": 0, "sha256_tree": sha256_tree(ROOT_OPT)},
                    lint_cache={"path": str(cache), "sha256": sha256_file(cache)})
    print(f"root_opt built: {n_tasks} tasks, 0 test-id hits; lint cache {cache}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
