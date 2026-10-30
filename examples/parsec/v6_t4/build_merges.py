#!/usr/bin/env python3
"""Build the two deterministic v6_t4 merges of the 34 v6_t2 task edits (no evaluation, no judgment).

  m1_order        apply every task's diff in a fixed order with `git merge -X theirs` semantics:
                  each diff is applied to the result so far; a region a later task changes takes
                  that task's version. Order: ascending absolute gain (T2 best − Seed), ties by
                  task name, so the highest-gain edit is applied last and wins every contest.
  m2_nonconflict  keep every hunk that no other task's hunk overlaps; drop every contested hunk.

Both work on the same hunks: difflib opcodes of each task's champion against the Seed, per file.
Two hunks conflict when their Seed ranges overlap, or when both insert at the same Seed line (git
conflicts in both cases). The merge order uses only the per-task gains T2 already recorded; nothing
is measured here.

Usage (from the worktree root):
    python3 examples/parsec/v6_t4/build_merges.py --suite-id e1 --out results/v6_t4_e1
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

T4_DIR = Path(__file__).resolve().parent
REPO_ROOT = T4_DIR.parents[2]
sys.path.insert(0, str(T4_DIR.parent / "v6_t2"))
import scaffold_projects as S  # noqa: E402

FILES = S.PROMPT_FILES


def champion_dir(suite: str, task: str) -> Path:
    run = REPO_ROOT / ".capevolve" / f"v6_t2_{suite}_{task}" / f"run_{task}"
    return run / "candidates" / json.loads((run / "state.json").read_text())["best_id"]


def seed_dir(suite: str) -> Path:
    t = S.TASK_IDS[0]
    return REPO_ROOT / ".capevolve" / f"v6_t2_{suite}_{t}" / f"run_{t}" / "candidates" / "seed"


def read_lines(p: Path) -> list[str]:
    return p.read_text(encoding="utf-8").splitlines(keepends=True)


def hunks_of(seed: list[str], cand: list[str]) -> list[tuple[int, int, list[str]]]:
    """(i1, i2, replacement lines) for every non-equal opcode: seed[i1:i2] becomes replacement."""
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, seed, cand, autojunk=False).get_opcodes():
        if op != "equal":
            out.append((i1, i2, cand[j1:j2]))
    return out


def clash(a: tuple[int, int], b: tuple[int, int]) -> bool:
    (a1, a2), (b1, b2) = a, b
    if a1 < b2 and b1 < a2:                       # overlapping replaced ranges
        return True
    if a1 == a2 and b1 == b2 and a1 == b1:        # two inserts at the same seed line
        return True
    if a1 == a2 and b1 <= a1 <= b2:               # insert touching a replaced range
        return True
    if b1 == b2 and a1 <= b1 <= a2:
        return True
    return False


def apply_hunks(seed: list[str], hunks: list[tuple[int, int, list[str]]]) -> list[str]:
    """Apply non-overlapping seed-anchored hunks; hunks at the same insert point keep their order."""
    out, pos = [], 0
    for i1, i2, rep in sorted(hunks, key=lambda h: (h[0], h[1])):
        if i1 < pos:
            raise ValueError(f"overlapping hunks at seed line {i1}")
        out.extend(seed[pos:i1])
        out.extend(rep)
        pos = i2
    out.extend(seed[pos:])
    return out


def merge_by_order(seed: list[str], ordered: list[list[tuple[int, int, list[str]]]]) -> list[str]:
    """-X theirs over seed-anchored hunks: a later task's hunk replaces every earlier hunk it clashes with."""
    kept: list[tuple[int, int, list[str]]] = []
    for task_hunks in ordered:
        for h in task_hunks:
            kept = [k for k in kept if not clash((k[0], k[1]), (h[0], h[1]))]
            kept.append(h)
    return apply_hunks(seed, kept)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite-id", required=True)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    ledger = json.loads((REPO_ROOT / f"results/v6_t2_{args.suite_id}/report/results.json").read_text())
    gain = {r["task"]: r["t2"]["best"] - r["seed"] for r in ledger["tasks"] if r["t2"]}
    order = sorted(S.TASK_IDS, key=lambda t: (round(gain[t], 6), t))
    sd = seed_dir(args.suite_id)

    log_order = ["# m1_order — merge log", "",
                 "Diffs applied in this order (ascending gain, ties by name); a later diff wins any",
                 "region it contests (`-X theirs`).", "",
                 "| # | task | gain |", "|--:|---|--:|"]
    log_order += [f"| {i} | {t} | {gain[t]:+.3f} |" for i, t in enumerate(order, 1)]
    log_nc = ["# m2_nonconflict — merge log", "",
              "Kept: hunks no other task's hunk overlaps. Dropped: every contested hunk.", "",
              "| file | hunks | kept | dropped |", "|---|--:|--:|--:|"]
    tot = {"hunks": 0, "kept": 0}
    per_task_kept: dict[str, list[int]] = {t: [0, 0] for t in S.TASK_IDS}

    for name, sub in (("m1_order", "m1_order"), ("m2_nonconflict", "m2_nonconflict")):
        (args.out / sub).mkdir(parents=True, exist_ok=True)

    for f in FILES:
        seed = read_lines(sd / f)
        by_task = {t: hunks_of(seed, read_lines(champion_dir(args.suite_id, t) / f)) for t in S.TASK_IDS}
        merged1 = merge_by_order(seed, [by_task[t] for t in order])
        (args.out / "m1_order" / f).write_text("".join(merged1), encoding="utf-8")

        flat = [(t, h) for t in S.TASK_IDS for h in by_task[t]]
        keep = []
        for i, (t, h) in enumerate(flat):
            contested = any(t2 != t and clash((h[0], h[1]), (h2[0], h2[1])) for j, (t2, h2) in enumerate(flat) if j != i)
            per_task_kept[t][1] += 1
            if not contested:
                keep.append(h)
                per_task_kept[t][0] += 1
        merged2 = apply_hunks(seed, keep)
        (args.out / "m2_nonconflict" / f).write_text("".join(merged2), encoding="utf-8")
        tot["hunks"] += len(flat); tot["kept"] += len(keep)
        log_nc.append(f"| {f} | {len(flat)} | {len(keep)} | {len(flat) - len(keep)} |")

    log_nc += [f"| **all** | {tot['hunks']} | {tot['kept']} | {tot['hunks'] - tot['kept']} |", "",
               "Per task (kept / total hunks):", "",
               "| task | kept | total |", "|---|--:|--:|"]
    log_nc += [f"| {t} | {k} | {n} |" for t, (k, n) in sorted(per_task_kept.items())]
    (args.out / "m1_order" / "MERGE_LOG.md").write_text("\n".join(log_order) + "\n", encoding="utf-8")
    (args.out / "m2_nonconflict" / "MERGE_LOG.md").write_text("\n".join(log_nc) + "\n", encoding="utf-8")

    words = lambda d: sum(len((d / f).read_text().split()) for f in FILES)  # noqa: E731
    print(json.dumps({"seed_words": words(sd), "m1_order_words": words(args.out / "m1_order"),
                      "m2_nonconflict_words": words(args.out / "m2_nonconflict"),
                      "m2_hunks_kept": tot["kept"], "m2_hunks_total": tot["hunks"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
