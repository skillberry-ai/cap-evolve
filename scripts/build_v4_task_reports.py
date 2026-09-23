#!/usr/bin/env python3
"""Build reports/task-by-task/v4/<task>.md from results/v4/results.json.

Usage: python3 scripts/build_v4_task_reports.py [--check] [--stats]
  --check   exit 1 if any auto block is stale, instead of writing it.
  --stats   print coverage: how many reports exist, how many have a
            hand-written narrative (no "_Not yet analysed._" placeholder).
"""
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = ROOT / "results" / "v4" / "results.json"
REPORTS_DIR = ROOT / "reports" / "task-by-task" / "v4"
ARTIFACTS_DIR = ROOT / "artifacts" / "v4"

AUTO_START = "<!-- BEGIN:auto -->"
AUTO_END = "<!-- END:auto -->"
AUTO_RE = re.compile(re.escape(AUTO_START) + r".*?" + re.escape(AUTO_END), re.DOTALL)

DIFF_START = "<!-- BEGIN:diff -->"
DIFF_END = "<!-- END:diff -->"
DIFF_RE = re.compile(re.escape(DIFF_START) + r".*?" + re.escape(DIFF_END), re.DOTALL)

PLACEHOLDER = "_Not yet analysed._"

PREFILLED_NOT_OPTIMIZED = (
    "T2 never targeted this task: its seed bundle already scored a perfect "
    "1.0 on our baseline run (`our_baseline`), so there was no headroom to "
    "optimize against (spec Sec.3). `seed`/`best`/`final` above all repeat "
    "`our_baseline` because no independent optimizer measurement exists -- "
    "they are not three separate results.\n\n"
    "This task will be evaluated again once a category or global merge "
    "(C3/C4/G3/G4, spec Sec.2) produces a bundle edited by other tasks' "
    "optimizer runs, as a regression check (spec Sec.3)."
)

PREFILLED_SEED_WINS = (
    "T2 ran the optimizer on this task, but no candidate beat the seed "
    "bundle on validation (`best_tag: \"seed\"`) -- see `{run_dir}/report.md` "
    "and `{run_dir}/JOURNAL.md` in the `parsec-intake_v4` worktree (not "
    "committed here) for what it tried. `final` above is the seed's own "
    "held-out test measurement, not a fallback."
)


def fmt(v):
    return "—" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))


def measurement_rows(row):
    """[(label, split, n, value), ...] -- only measurements that actually exist."""
    rows = [
        ("JB baseline", "test", row["jb_n"], row["jb_reward"]),
        ("our baseline (v4_t1_e1)", "test", row["our_baseline_n"], row["our_baseline"]),
    ]
    if row["status"] != "optimized":
        return rows
    val_n = row.get("final_n")
    rows.append(("seed (val, v4_t2_e1)", "val", val_n, row["seed"]))
    for tag in ("cand_0001", "cand_0002", "cand_0003"):
        if row.get(tag) is not None:
            marker = "  <- best (val)" if row["best_tag"] == tag else ""
            rows.append((f"{tag} (val, v4_t2_e1){marker}", "val", val_n, row[tag]))
    rows.append(("final (test, v4_t2_e1)", "test", val_n, row["final"]))
    return rows


def build_auto_block(row):
    lines = [AUTO_START, ""]
    lines.append(f"**task:** `{row['task']}`  ")
    lines.append(f"**category:** {row['category']}  ")
    lines.append(f"**tranche:** {row['tranche']}  ")
    lines.append(f"**services:** {row['services']}  ")
    lines.append(f"**status:** {row['status']}  ")
    if row.get("run_dir"):
        lines.append(f"**run:** `{row['run_dir']}` (n_runs: {row.get('n_runs')})  ")
    lines.append("")
    lines.append("_Read no cell without the `n` and split beside it._")
    lines.append("")
    lines.append("| measurement | split | n | reward |")
    lines.append("|---|---|--:|--:|")
    for label, split, n, value in measurement_rows(row):
        lines.append(f"| {label} | {split} | {fmt(n)} | {fmt(value)} |")
    lines.append("")
    lines.append(f"delta vs JB: {fmt(row['delta_vs_jb'])} · "
                  f"delta vs our baseline: {fmt(row['delta_vs_our_baseline'])}")
    if row.get("t2_cost_usd") is not None:
        lines.append("")
        lines.append(
            f"**T2 cost/time:** ${row['t2_cost_usd']:.2f}, {row['t2_tokens']:,} tokens, "
            f"{row['t2_time_s']/3600:.2f}h "
            f"(eval ${row['t2_eval_cost_usd']:.2f}/{row['t2_eval_tokens']:,}tok · "
            f"optimizer ${row['t2_opt_cost_usd']:.2f}/{row['t2_opt_tokens']:,}tok) — "
            f"see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)"
        )
    if row.get("run_dir"):
        lines.append("")
        lines.append(
            f"Optimizer run material (not committed here -- `parsec-intake_v4` "
            f"worktree, gitignored): `{row['run_dir']}/report.md`, "
            f"`{row['run_dir']}/JOURNAL.md`"
        )
    lines.append("")
    lines.append(AUTO_END)
    return "\n".join(lines)


def file_diff(seed_path, best_path):
    """(diff_lines, added, removed) for one file, seed -> best."""
    seed_lines = seed_path.read_text().splitlines(keepends=True)
    best_lines = best_path.read_text().splitlines(keepends=True)
    diff_lines = list(difflib.unified_diff(
        seed_lines, best_lines,
        fromfile=f"seed/{seed_path.name}", tofile=f"{best_path.parent.parent.name}/best/{seed_path.name}",
    ))
    added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
    return diff_lines, added, removed


def build_diff_block(task):
    """Auto-managed 'what changed' section: seed/*.md vs <task>/best/*.md.

    None means no best/ dir exists for this task (T2 never ran, or the
    task's only artifact is a NOTE.md) -- the caller drops any stale block.
    """
    seed_dir = ARTIFACTS_DIR / "seed"
    best_dir = ARTIFACTS_DIR / task / "best"
    if not best_dir.is_dir():
        return None

    seed_files = sorted(seed_dir.glob("*.md"))
    changed = []
    for seed_file in seed_files:
        best_file = best_dir / seed_file.name
        if not best_file.is_file():
            continue
        diff_lines, added, removed = file_diff(seed_file, best_file)
        if diff_lines:
            changed.append((seed_file.name, added, removed, diff_lines))

    lines = [DIFF_START, "", "## What changed (seed → best)", ""]
    if not changed:
        lines.append(
            "Every skill file is byte-identical to "
            "[`artifacts/v4/seed/`](../../../artifacts/v4/seed/) -- the champion "
            "made no edits."
        )
        lines += ["", DIFF_END]
        return "\n".join(lines)

    lines.append(
        f"{len(changed)} of {len(seed_files)} skill files changed. Full unified "
        f"diffs, [`artifacts/v4/seed/`](../../../artifacts/v4/seed/) → "
        f"[`artifacts/v4/{task}/best/`](../../../artifacts/v4/{task}/best/):"
    )
    lines.append("")
    for name, added, removed, diff_lines in changed:
        lines.append("<details>")
        lines.append(f"<summary><code>{name}</code> (+{added}/−{removed})</summary>")
        lines.append("")
        lines.append("```diff")
        lines.extend(l.rstrip("\n") for l in diff_lines)
        lines.append("```")
        lines.append("")
        lines.append("</details>")
        lines.append("")
    lines.append(DIFF_END)
    return "\n".join(lines)


def prefilled_hand_section(row):
    if row["status"] != "optimized":
        return PREFILLED_NOT_OPTIMIZED
    if row["best_tag"] == "seed":
        return PREFILLED_SEED_WINS.format(run_dir=row["run_dir"])
    return None


def build_report(row, existing_text):
    auto_block = build_auto_block(row)
    diff_block = build_diff_block(row["task"])

    if existing_text is None:
        hand = prefilled_hand_section(row)
        if hand is None:
            hand = PLACEHOLDER
        text = f"# {row['task']}\n\n{auto_block}\n\n{hand}\n"
    elif AUTO_RE.search(existing_text):
        text = AUTO_RE.sub(auto_block, existing_text, count=1)
    else:
        text = existing_text.rstrip("\n") + "\n\n" + auto_block + "\n"

    if diff_block is None:
        return DIFF_RE.sub("", text) if DIFF_RE.search(text) else text
    if DIFF_RE.search(text):
        return DIFF_RE.sub(diff_block, text, count=1)
    return text.rstrip("\n") + "\n\n" + diff_block + "\n"


def main():
    check_only = "--check" in sys.argv
    stats_only = "--stats" in sys.argv

    results = json.loads(RESULTS_JSON.read_text())
    rows = results["task_ledger"]

    if stats_only:
        written = analysed = 0
        for row in rows:
            path = REPORTS_DIR / f"{row['task']}.md"
            if path.exists():
                written += 1
                if PLACEHOLDER not in path.read_text():
                    analysed += 1
        print(f"{written}/{len(rows)} written, {analysed}/{len(rows)} fully analysed.")
        return 0

    stale = []
    for row in rows:
        path = REPORTS_DIR / f"{row['task']}.md"
        existing = path.read_text() if path.exists() else None
        new_text = build_report(row, existing)
        if new_text == existing:
            continue
        stale.append(str(path.relative_to(ROOT)))
        if not check_only:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(new_text)

    if not stale:
        print("reports/task-by-task/v4/*.md already up to date.")
        return 0
    if check_only:
        print(f"{len(stale)} report(s) stale:", file=sys.stderr)
        for s in stale:
            print(f"  {s}", file=sys.stderr)
        return 1

    print(f"Wrote/updated {len(stale)} report(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
