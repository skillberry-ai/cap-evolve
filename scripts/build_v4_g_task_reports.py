#!/usr/bin/env python3
"""Build reports/v4/v4_g_e1/<task>.md from
results/v4/v4_g_e1/results.json.

G2 evolved one shared bundle across all 34 tasks jointly (unlike T2's
per-task optimization), so every report's diff block is against the same
artifacts/v4/v4_g_e1/best/ directory, and no per-task narrative has been
hand-written -- each report carries only the generated auto and diff blocks
plus a pointer to the arm summary.

Usage: python3 scripts/build_v4_g_task_reports.py [--check] [--stats]
  --check   exit 1 if any auto block is stale, instead of writing it.
  --stats   print coverage: how many reports exist, how many have a
            hand-written narrative (no NOT_YET_WRITTEN placeholder).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v4_report_common import AUTO_END, AUTO_START, build_diff_block, build_report, fmt

ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = ROOT / "results" / "v4" / "v4_g_e1" / "results.json"
REPORTS_DIR = ROOT / "reports" / "v4" / "v4_g_e1"
SEED_DIR = ROOT / "artifacts" / "v4" / "seed"
BEST_DIR = ROOT / "artifacts" / "v4" / "v4_g_e1" / "best"

CANDS = ["cand_0001", "cand_0002", "cand_0003", "cand_0004", "cand_0005", "cand_0006"]

NOT_YET_WRITTEN = (
    "_Per-task narrative not yet written -- see "
    "[`../../../results/v4/v4_g_e1/summary.md`](../../../results/v4/v4_g_e1/summary.md)._"
)


def measurement_rows(row):
    rows = [("our baseline (v4_t1_e1)", "test", row["our_baseline_n"], row["our_baseline"])]
    rows.append(("seed (val, v4_g2_e1)", "val", row.get("seed_n"), row["seed"]))
    for tag in CANDS:
        if row.get(tag) is not None:
            marker = "  <- best (val)" if row["best_tag"] == tag else ""
            rows.append((f"{tag} (val, v4_g2_e1){marker}", "val", row.get(f"{tag}_n"), row[tag]))
    return rows


def build_auto_block(row):
    lines = [AUTO_START, ""]
    lines.append(f"**task:** `{row['task']}`  ")
    lines.append(f"**category:** {row['category']}  ")
    lines.append(f"**tranche:** {row['tranche']}  ")
    lines.append(f"**services:** {row['services']}  ")
    lines.append("")
    lines.append("_Read no cell without the `n` and split beside it._")
    lines.append("")
    lines.append("| measurement | split | n | reward |")
    lines.append("|---|---|--:|--:|")
    for label, split, n, value in measurement_rows(row):
        lines.append(f"| {label} | {split} | {fmt(n)} | {fmt(value)} |")
    lines.append("")
    lines.append(f"best: {fmt(row['best'])} ({row['best_tag']}) · "
                  f"delta vs our baseline: {fmt(row['delta_vs_our_baseline'])}")
    lines.append("")
    lines.append(AUTO_END)
    return "\n".join(lines)


def diff_block_for():
    return build_diff_block(
        SEED_DIR,
        BEST_DIR,
        ("artifacts/v4/seed/", "../../../artifacts/v4/seed/"),
        ("artifacts/v4/v4_g_e1/best/", "../../../artifacts/v4/v4_g_e1/best/"),
    )


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
                if NOT_YET_WRITTEN not in path.read_text():
                    analysed += 1
        print(f"{written}/{len(rows)} written, {analysed}/{len(rows)} fully analysed.")
        return 0

    diff_block = diff_block_for()
    stale = []
    for row in rows:
        path = REPORTS_DIR / f"{row['task']}.md"
        existing = path.read_text() if path.exists() else None
        new_text = build_report(
            row["task"],
            build_auto_block(row),
            diff_block,
            existing,
            prefilled_hand=NOT_YET_WRITTEN,
        )
        if new_text == existing:
            continue
        stale.append(str(path.relative_to(ROOT)))
        if not check_only:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(new_text)

    if not stale:
        print("reports/v4/v4_g_e1/*.md already up to date.")
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
