#!/usr/bin/env python3
"""select_candidates.py — build a candidate pool for the swebench SMOKE tier.

Offline dev tool, run by hand when re-picking smoke tasks — NOT invoked by CI or
run_suite.sh. Lives under utils/ so it doesn't read as runtime code.

Goal: a small set of SWE-bench instances that a MID-tier reader (gpt-oss-120b) doing
single-shot ORACLE patching can *sometimes* solve — nonzero but not saturated — so the
benchmark shows headroom for future PRs (mirrors how the tau2 smoke set was chosen).

Selection funnel (all deterministic; no model calls):
  1. Verified ∩ Lite — Verified supplies OpenAI's `difficulty` annotation; Lite supplies
     the well-tested Docker eval images and the `*_oracle` prompt context.
  2. difficulty == "<15 min fix"  (the Easy bucket: avg 1.0 files / 1.4 hunks / ~5 lines).
  3. gold patch is small + localized: single file, ≤ max-hunks, ≤ max-lines changed.
  4. oracle `text` fits a token budget (skip the rare 100k+ char monsters).
  5. diversify across repos (round-robin, capped per repo) up to --pool-size.

The output is a POOL to baseline on skillberry-1, not the final smoke set. Baseline the
pool at num_trials=10 with aws/gpt-oss-120b and keep those landing in ~10–70% pass@10.

Usage:
  pip install datasets
  python3 select_candidates.py --out candidates.json [--pool-size 30] [--max-lines 15] ...
"""
from __future__ import annotations

import argparse
import json
import sys

VERIFIED = "princeton-nlp/SWE-bench_Verified"
LITE = "princeton-nlp/SWE-bench_Lite"
LITE_ORACLE = "princeton-nlp/SWE-bench_Lite_oracle"
SPLIT = "test"
EASY_DIFFICULTY_PREFIX = "<15"  # matches "<15 min fix"


def _patch_stats(patch: str) -> tuple[int, int, int]:
    """Return (n_files, n_hunks, n_changed_lines) for a unified-diff string."""
    files = patch.count("diff --git ")
    if files == 0:
        files = sum(1 for ln in patch.splitlines() if ln.startswith("+++ "))
    hunks = sum(1 for ln in patch.splitlines() if ln.startswith("@@"))
    changed = sum(
        1
        for ln in patch.splitlines()
        if (ln.startswith("+") and not ln.startswith("+++"))
        or (ln.startswith("-") and not ln.startswith("---"))
    )
    return files, hunks, changed


def _load(name: str, split: str):
    from datasets import load_dataset

    return load_dataset(name, split=split)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="candidates.json", help="output JSON path")
    ap.add_argument("--pool-size", type=int, default=30, help="max candidates to emit")
    ap.add_argument("--max-lines", type=int, default=15, help="max changed gold-patch lines")
    ap.add_argument("--max-hunks", type=int, default=2, help="max gold-patch hunks")
    ap.add_argument("--max-files", type=int, default=1, help="max gold-patch files (1 = single-file)")
    ap.add_argument("--max-oracle-chars", type=int, default=60000, help="skip larger oracle prompts")
    ap.add_argument("--per-repo", type=int, default=4, help="cap candidates per repo (diversity)")
    args = ap.parse_args()

    try:
        verified = {r["instance_id"]: r for r in _load(VERIFIED, SPLIT)}
        lite_ids = {r["instance_id"] for r in _load(LITE, SPLIT)}
        oracle_chars = {r["instance_id"]: len(r.get("text", "")) for r in _load(LITE_ORACLE, SPLIT)}
    except Exception as e:  # noqa: BLE001
        print(f"error: could not load datasets ({e}). Run `pip install datasets`.", file=sys.stderr)
        return 2

    inter = sorted(verified.keys() & lite_ids)
    rows = []
    for iid in inter:
        v = verified[iid]
        difficulty = (v.get("difficulty") or "").strip()
        if not difficulty.startswith(EASY_DIFFICULTY_PREFIX):
            continue
        files, hunks, changed = _patch_stats(v.get("patch", ""))
        if files == 0 or files > args.max_files:
            continue
        if hunks > args.max_hunks or changed > args.max_lines:
            continue
        ochars = oracle_chars.get(iid, 0)
        if ochars == 0 or ochars > args.max_oracle_chars:
            continue
        rows.append({
            "id": iid,
            "repo": v.get("repo", ""),
            "difficulty": difficulty,
            "files": files,
            "hunks": hunks,
            "lines": changed,
            "oracle_chars": ochars,
        })

    # Rank easiest-first, then round-robin across repos (capped) for diversity.
    rows.sort(key=lambda r: (r["lines"], r["hunks"], r["oracle_chars"]))
    by_repo: dict[str, list[dict]] = {}
    for r in rows:
        by_repo.setdefault(r["repo"], []).append(r)

    picked: list[dict] = []
    exhausted = False
    while len(picked) < args.pool_size and not exhausted:
        exhausted = True
        for repo, bucket in by_repo.items():
            taken = sum(1 for p in picked if p["repo"] == repo)
            if bucket and taken < args.per_repo:
                picked.append(bucket.pop(0))
                exhausted = False
                if len(picked) >= args.pool_size:
                    break

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(picked, f, indent=2)

    # Human-readable summary to stderr (stdout stays clean JSON path for scripting).
    print(f"candidate pool: {len(picked)} instances "
          f"(from {len(inter)} Verified∩Lite, {len(rows)} passed filters)", file=sys.stderr)
    repos = sorted({p["repo"] for p in picked})
    print(f"repos ({len(repos)}): {', '.join(repos)}", file=sys.stderr)
    for p in picked:
        print(f"  {p['id']:45} {p['lines']:>2}L {p['hunks']}h  {p['oracle_chars']:>6}c  {p['repo']}",
              file=sys.stderr)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
