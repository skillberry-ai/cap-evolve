#!/usr/bin/env python3
"""Draw v6's F / C / test split: stratified by category and by drop, seeded, written once.

Every bench-v6-* task under $PARSEC_V6N/_run/tasks is assigned to the feedback set F
(the optimizer sees its traces), the confirm set C (hidden; decides accepts) or test
(sealed until finalize). Within each (category, drop) stratum the tasks are shuffled
with ``--seed`` and dealt round-robin in the order of ``--fractions``, so every set
gets the same mix of categories and drops. A drop is named by a membership file
(``--drop NAME=FILE``, one task id per line); tasks in no file belong to ``--base-drop``.
When the tree carries ``task_sets.json`` (written by build_v6_tree.py), each task's ``drop``
is read from it and ``--drop`` files are not needed.

``--exclude FILE`` keeps listed tasks out of all three sets.

Writes ``split_ids.json`` ({"feedback", "confirm", "test"}, read by cap-evolve under
``split_mode: pooled``), ``public_tasks.txt`` (F, read by the dispatching adapter) and
``split_report.md`` (the per-stratum counts, for review).

Usage:
    export PARSEC_V6N=/path/to/rhdp-parsec/v6_2026-10-16
    python3 examples/parsec/v6/make_split.py --out <dir> \\
        --drop 10-12=<task_set_10-12.txt> [--drop jb-3=<file>] [--exclude <file>] [--seed 6]
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROLES = ("feedback", "confirm", "test")
CATEGORY_RE = re.compile(r"^(cloud|cost|icinga|platform)-")


def category(task_id: str) -> str:
    m = CATEGORY_RE.match(task_id)
    if not m:
        raise ValueError(f"no category prefix on task id {task_id!r}")
    return m.group(1)


def read_ids(path: Path) -> list[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def interleave(weights, length: int = 60) -> list[str]:
    """Roles in a smooth weighted round-robin order: thirds give F, C, T, F, C, T, ... (never a run)."""
    total = float(sum(weights))
    credit = [0.0] * len(ROLES)
    out = []
    for _ in range(length):
        for i, w in enumerate(weights):
            credit[i] += w
        i = max(range(len(ROLES)), key=lambda j: credit[j])
        credit[i] -= total
        out.append(ROLES[i])
    return out


def draw(task_ids, drops: dict, base_drop: str, fractions, seed: int) -> dict:
    strata = defaultdict(list)
    for t in sorted(task_ids):
        strata[(category(t), drops.get(t, base_drop))].append(t)
    rng = random.Random(seed)
    roles = {r: [] for r in ROLES}
    # Deal each stratum round-robin over a role sequence built from the fractions, starting each
    # stratum where the previous one stopped, so remainders spread evenly instead of piling on F.
    pattern = interleave(fractions)
    pos = 0
    for key in sorted(strata):
        ids = strata[key][:]
        rng.shuffle(ids)
        for t in ids:
            roles[pattern[pos % len(pattern)]].append(t)
            pos += 1
    return {r: sorted(v) for r, v in roles.items()}, strata


def report(roles: dict, strata: dict, drops: dict, base_drop: str) -> str:
    role_of = {t: r for r, ids in roles.items() for t in ids}
    lines = ["# v6 split", "", "| category | drop | n | feedback | confirm | test |", "|---|---|--:|--:|--:|--:|"]
    for (cat, drop), ids in sorted(strata.items()):
        c = {r: sum(role_of[t] == r for t in ids) for r in ROLES}
        lines.append(f"| {cat} | {drop} | {len(ids)} | {c['feedback']} | {c['confirm']} | {c['test']} |")
    lines.append(f"| **total** | | **{len(role_of)}** | **{len(roles['feedback'])}** | "
                 f"**{len(roles['confirm'])}** | **{len(roles['test'])}** |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--drop", action="append", default=[], metavar="NAME=FILE")
    ap.add_argument("--base-drop", default="10-10")
    ap.add_argument("--exclude", type=Path)
    ap.add_argument("--fractions", default="1,1,1", help="feedback,confirm,test weights (default thirds)")
    ap.add_argument("--seed", type=int, default=6)
    ap.add_argument("--tasks-dir", type=Path, help="default $PARSEC_V6N/_run/tasks")
    args = ap.parse_args()

    tasks_dir = args.tasks_dir
    if tasks_dir is None:
        import os
        root = os.environ.get("PARSEC_V6N")
        if not root:
            print("set PARSEC_V6N or pass --tasks-dir", file=sys.stderr)
            return 2
        tasks_dir = Path(root) / "_run" / "tasks"
    ids = sorted(d.name[len("bench-v6-"):] for d in tasks_dir.glob("bench-v6-*") if d.is_dir())

    drops = {}
    sets_file = tasks_dir.resolve().parents[1] / "task_sets.json"
    if sets_file.is_file() and not args.drop:
        drops = {t: v["drop"] for t, v in json.loads(sets_file.read_text()).items()}
    for spec in args.drop:
        name, _, f = spec.partition("=")
        for t in read_ids(Path(f)):
            if t in drops:
                print(f"task {t} is in two drops ({drops[t]}, {name})", file=sys.stderr)
                return 2
            drops[t] = name
    unknown = sorted(set(drops) - set(ids))
    if unknown:
        print(f"drop files name {len(unknown)} task(s) not in {tasks_dir}: {unknown[:5]}", file=sys.stderr)
        return 2
    excluded = set(read_ids(args.exclude)) if args.exclude else set()
    ids = [t for t in ids if t not in excluded]

    fractions = [float(x) for x in args.fractions.split(",")]
    roles, strata = draw(ids, drops, args.base_drop, fractions, args.seed)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "split_ids.json").write_text(json.dumps(roles, indent=2) + "\n", encoding="utf-8")
    (args.out / "public_tasks.txt").write_text("\n".join(roles["feedback"]) + "\n", encoding="utf-8")
    text = report(roles, strata, drops, args.base_drop)
    (args.out / "split_report.md").write_text(text, encoding="utf-8")
    print(text, end="")
    if excluded:
        print(f"\nexcluded: {len(excluded)} task(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
