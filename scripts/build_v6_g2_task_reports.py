#!/usr/bin/env python3
"""Build reports/v6/v6_g2_e1/<task>.md from results/v6/v6_g2_e1/results.json's
task_ledger (test-split only -- see build_v6_g2_results_json.py's docstring for
why there is no per-task F/C ledger).

Every report's diff block is seed vs. artifacts/v6/v6_g2_e1/best/ (the final
champion, cand_0005) -- the same shared-bundle diff for all 66 tasks, since this
is a global-scope run like v4_g_e1, not a per-task one like v4_t_e1.

Usage: python3 scripts/build_v6_g2_task_reports.py [--check] [--stats]
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
RESULTS_JSON = ROOT / "results" / "v6" / "v6_g2_e1" / "results.json"
REPORTS_DIR = ROOT / "reports" / "v6" / "v6_g2_e1"
SEED_DIR = ROOT / "artifacts" / "v6" / "v6_g2_e1" / "seed"
BEST_DIR = ROOT / "artifacts" / "v6" / "v6_g2_e1" / "best"

NOT_YET_WRITTEN = (
    "_Per-task narrative not yet written -- see "
    "[`../../../results/v6/v6_g2_e1/summary.md`](../../../results/v6/v6_g2_e1/summary.md)._"
)


def build_auto_block(row):
    lines = [AUTO_START, ""]
    lines.append(f"**task:** `{row['task']}`  ")
    lines.append(f"**category:** {row['category']}  ")
    lines.append("")
    lines.append("_Sealed test split, scored exactly once. n=10 trials/task for both rows._")
    lines.append("")
    lines.append("| measurement | split | n | reward |")
    lines.append("|---|---|--:|--:|")
    lines.append(f"| seed (unmodified bundle) | test | {fmt(row.get('seed_n'))} | {fmt(row['seed'])} |")
    lines.append(f"| cand_0005 (final champion) | test | {fmt(row.get('champion_n'))} | {fmt(row['champion'])} |")
    lines.append("")
    lines.append(f"delta vs seed: {fmt(row['delta_vs_seed'])}")
    lines.append("")
    lines.append(AUTO_END)
    return "\n".join(lines)


def diff_block_for():
    return build_diff_block(
        SEED_DIR,
        BEST_DIR,
        ("artifacts/v6/v6_g2_e1/seed/", "../../../artifacts/v6/v6_g2_e1/seed/"),
        ("artifacts/v6/v6_g2_e1/best/", "../../../artifacts/v6/v6_g2_e1/best/"),
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
        print("reports/v6/v6_g2_e1/*.md already up to date.")
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
