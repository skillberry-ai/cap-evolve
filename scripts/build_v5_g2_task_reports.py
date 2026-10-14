#!/usr/bin/env python3
"""Build reports/v5/v5_g2_e1/<task>.md from results/v5/v5_g2_e1/results.json.

Each report's auto block carries two measurement rows -- this arm and
v5_b1_e1 on the same task -- plus the per-trial vector and the delta that is
this arm's whole point. Reuses scripts/v4_report_common.py's splice
machinery unchanged, same as build_v5_b1_task_reports.py.

No diff block: cand_0004 was optimized once, for v4's 34 tasks, and reused
here as-is -- no per-task `artifacts/v5/v5_g2_e1/<task>/best/` directory
exists for any of the 136 tasks, so build_diff_block's own `best_dir.is_dir()`
check returns None for every task, the same path v5_b1_e1's never-optimized
tasks and v4's never-optimized tasks already take.

Usage: python3 scripts/build_v5_g2_task_reports.py [--check] [--stats]
  --check   exit 1 if any auto block is stale, instead of writing it.
  --stats   print coverage: how many reports exist, how many have a
            hand-written narrative (no "_Not yet analysed._" placeholder).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v4_report_common import AUTO_END, AUTO_START, PLACEHOLDER, build_diff_block, build_report, fmt

ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = ROOT / "results" / "v5" / "v5_g2_e1" / "results.json"
REPORTS_DIR = ROOT / "reports" / "v5" / "v5_g2_e1"
ARTIFACTS_DIR = ROOT / "artifacts"

ORIGIN_NOTE = {
    "v4-34": (
        "**Lineage:** one of v4's original 34 tasks. `cand_0004` was itself optimized against "
        "this exact 34-task set in v4's G2 arm, so this is the only group where the skill under "
        "test was actually tuned on the task it is being scored on."
    ),
    "h4-rewritten": (
        "**Lineage:** shares an id with an h4 held-out task, but its instruction, contract, seed "
        "data and verifier were all rewritten going into v5 -- `cand_0004` was never tuned "
        "against this task's v5 content, h4-rewritten or otherwise."
    ),
    "renamed-content-changed": (
        "**Lineage:** kept a v4/h4 task number but has different content; `cand_0004` was never "
        "tuned against this content."
    ),
    "new-10-10": "**Lineage:** new in the `v5_2026-10-10` drop -- `cand_0004` was never tuned against it.",
    "new-10-12": "**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.",
}

MOVE_NOTE = {
    "up": "**Moved up {d:+.3f}** vs `v5_b1_e1`, beyond the ~{nf:.2f} per-task noise floor.",
    "down": "**Moved down {d:+.3f}** vs `v5_b1_e1`, beyond the ~{nf:.2f} per-task noise floor.",
    "flat": "Moved {d:+.3f} vs `v5_b1_e1` -- inside the ~{nf:.2f} per-task noise floor; not distinguishable from no change at n=5.",
}


def build_auto_block(row, overall, noise_floor):
    lines = [AUTO_START, ""]
    lines.append(f"**task:** `{row['task']}`  ")
    lines.append(f"**category:** {row['category']}  ")
    lines.append(f"**task set:** {row['task_set']}  ")
    lines.append(f"**origin:** {row['origin']}  ")
    lines.append(f"**deterministic:** {'no' if row['variable'] else 'yes'}  ")
    lines.append(f"**move vs v5_b1_e1:** {row['move']}  ")
    lines.append("")
    lines.append("| measurement | split | n | reward |")
    lines.append("|---|---|--:|--:|")
    lines.append(f"| v5_g2_e1 (cand_0004, reused as-is) | val | {fmt(row['n_valid'])} "
                 f"| {fmt(row['reward'])} |")
    lines.append(f"| v5_b1_e1 (original skill) | val | {fmt(row['v5_b1_n'])} "
                 f"| {fmt(row['v5_b1_reward'])} |")
    lines.append("")
    trials = ", ".join(fmt(v) for v in (row.get("trial_rewards") or []))
    lines.append(f"per-trial rewards: [{trials}]  ")
    lines.append(f"min {fmt(row['trial_min'])} · max {fmt(row['trial_max'])} · "
                 f"spread {fmt(row['spread'])} · sd {fmt(row['sd'])} · "
                 f"errored trials {row['errored_trials']}  ")
    lines.append(f"delta vs v5_b1_e1: {row['delta_vs_v5_b1']:+.3f}  ")
    if row.get("pooled_note"):
        lines.append("")
        lines.append(f"**pooling:** {row['pooled_note']}")
    lines.append("")
    lines.append(
        f"**cost/time:** ${row['cost_usd']:.4f}, {row['tokens']:,} tokens, "
        f"{row['seconds']/60:.1f} min -- see "
        f"[`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)"
    )
    lines.append("")
    lines.append(AUTO_END)
    return "\n".join(lines)


def prefilled_hand(row, overall, noise_floor):
    parts = [MOVE_NOTE[row["move"]].format(d=row["delta_vs_v5_b1"], nf=noise_floor)]
    parts.append(ORIGIN_NOTE[row["origin"]])
    return "\n\n".join(parts)


def diff_block_for(task):
    # No per-task best/ dir exists for this arm -- cand_0004 was optimized once
    # (for v4's 34 tasks) and reused unchanged everywhere. Returns None for
    # every task, same path v5_b1_e1's never-optimized tasks already take.
    return build_diff_block(
        ARTIFACTS_DIR / "v4" / "v4_g_e1" / "best",
        ARTIFACTS_DIR / "v5" / "v5_g2_e1" / task / "best",
        ("artifacts/v4/v4_g_e1/best/", "../../../artifacts/v4/v4_g_e1/best/"),
        (f"artifacts/v5/v5_g2_e1/{task}/best/", f"../../../artifacts/v5/v5_g2_e1/{task}/best/"),
    )


def main():
    check_only = "--check" in sys.argv
    stats_only = "--stats" in sys.argv

    results = json.loads(RESULTS_JSON.read_text())
    rows = results["task_ledger"]
    overall = results["sections"]["overall"]
    noise_floor = results["sections"]["comparison_v5_b1"]["noise_floor"]

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
        new_text = build_report(
            row["task"],
            build_auto_block(row, overall, noise_floor),
            diff_block_for(row["task"]),
            existing,
            prefilled_hand=prefilled_hand(row, overall, noise_floor),
        )
        if new_text == existing:
            continue
        stale.append(str(path.relative_to(ROOT)))
        if not check_only:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(new_text)

    if not stale:
        print("reports/v5/v5_g2_e1/*.md already up to date.")
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
