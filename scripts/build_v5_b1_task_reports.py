#!/usr/bin/env python3
"""Build reports/v5/v5_b1_e1/<task>.md from results/v5/v5_b1_e1/results.json.

v5_b1_e1 is a zero-shot baseline, so each report's auto block is the simplest
shape in this branch: one measurement row (this arm, 5 trials) plus the
per-trial vector, because for a baseline "what happened" IS the trial vector.
Reuses scripts/v4_report_common.py's splice machinery unchanged -- the marker
logic must stay identical across arms or hand-written narrative gets clobbered.

No diff block: nothing was optimized in this arm, so there is no `best/`
directory anywhere and build_diff_block's own `best_dir.is_dir()` check
returns None for every task, exactly as it already does for v4's
never-optimized tasks.

Usage: python3 scripts/build_v5_b1_task_reports.py [--check] [--stats]
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
RESULTS_JSON = ROOT / "results" / "v5" / "v5_b1_e1" / "results.json"
REPORTS_DIR = ROOT / "reports" / "v5" / "v5_b1_e1"
ARTIFACTS_DIR = ROOT / "artifacts" / "v5"

ORIGIN_NOTE = {
    "v4-34": (
        "**Lineage:** one of v4's original 34 tasks, carried into v5 with its contract "
        "unchanged. The two v4 rows above are v4's own original-skill baselines on the "
        "same task, so the comparison is like-for-like. Across all 34 such tasks v5 "
        "reproduces v4 to {v4_delta:+.3f} on average (SE {v4_se:.3f})."
    ),
    "h4-rewritten": (
        "**Lineage:** shares an id with an h4 held-out task, but its instruction, "
        "contract, seed data and verifier were all rewritten going into v5. h4's "
        "numbers for this id describe a different task and are deliberately not shown."
    ),
    "renamed-content-changed": (
        "**Lineage:** kept a v4/h4 task number but has different content, so no "
        "earlier number is comparable."
    ),
    "new-10-10": "**Lineage:** new in the `v5_2026-10-10` drop -- no earlier measurement.",
    "new-10-12": "**Lineage:** new in the `v5_2026-10-12` drop -- no earlier measurement.",
}

DETERMINISTIC_NOTE = (
    "All five trials returned the identical reward, so this task's score carries "
    "no run-to-run noise -- unusual here: only {n_det} of {n_total} v5 tasks are "
    "deterministic."
)

VARIABLE_NOTE = (
    "This task is **non-deterministic**: {n} identical trials spanned "
    "{lo:.3f}-{hi:.3f} (sd {sd:.3f}). With n=5 its mean carries a ~95% CI of "
    "roughly +/-{ci:.3f}, so a later arm's change on this task alone is only "
    "meaningful well above that. It is one of {n_var} of {n_total} v5 tasks "
    "({pct:.0f}%) that vary across repeats."
)


def build_auto_block(row, overall):
    lines = [AUTO_START, ""]
    lines.append(f"**task:** `{row['task']}`  ")
    lines.append(f"**category:** {row['category']}  ")
    lines.append(f"**task set:** {row['task_set']}  ")
    lines.append(f"**origin:** {row['origin']}  ")
    lines.append(f"**deterministic:** {'no' if row['variable'] else 'yes'}  ")
    lines.append("")
    lines.append("_Read no cell without the `n` and split beside it._")
    lines.append("")
    lines.append("| measurement | split | n | reward |")
    lines.append("|---|---|--:|--:|")
    lines.append(f"| v5_b1_e1 (original skill, zero-shot) | val | {fmt(row['n_valid'])} "
                 f"| {fmt(row['reward'])} |")
    if row.get("v4_t1_reward") is not None:
        lines.append(f"| v4_t1_e1 (v4's original-skill baseline) | test | {fmt(row['v4_t1_n'])} "
                     f"| {fmt(row['v4_t1_reward'])} |")
        lines.append(f"| JB baseline-v2 (external) | test | {fmt(row['jb_n'])} "
                     f"| {fmt(row['jb_reward'])} |")
    lines.append("")
    trials = ", ".join(fmt(v) for v in (row.get("trial_rewards") or []))
    lines.append(f"per-trial rewards: [{trials}]  ")
    lines.append(f"min {fmt(row['trial_min'])} · max {fmt(row['trial_max'])} · "
                 f"spread {fmt(row['spread'])} · sd {fmt(row['sd'])} · "
                 f"errored trials {row['errored_trials']}  ")
    if row.get("delta_vs_v4_t1") is not None:
        lines.append(f"delta vs v4_t1_e1: {row['delta_vs_v4_t1']:+.3f}  ")
    if row.get("audit_note"):
        lines.append("")
        lines.append(f"**audit:** {row['errored_trials']} trial(s) excluded -- {row['audit_note']}.")
    lines.append("")
    lines.append(
        f"**cost/time:** ${row['cost_usd']:.4f}, {row['tokens']:,} tokens, "
        f"{row['seconds']/60:.1f} min -- see "
        f"[`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)"
    )
    lines.append("")
    lines.append(AUTO_END)
    return "\n".join(lines)


def prefilled_hand(row, overall, noise, results_sections):
    parts = []
    if row["variable"]:
        parts.append(VARIABLE_NOTE.format(n=row["n_valid"],
            lo=row["trial_min"], hi=row["trial_max"], sd=row["sd"],
            ci=noise["ci95_halfwidth_per_task"],
            n_var=overall["n_variable"], n_total=overall["n_tasks"],
            pct=overall["pct_variable"]))
    else:
        parts.append(DETERMINISTIC_NOTE.format(
            n_det=overall["n_deterministic"], n_total=overall["n_tasks"]))
    cmp4 = results_sections["comparison_v4"]
    parts.append(ORIGIN_NOTE[row["origin"]].format(v4_delta=cmp4["paired_delta_mean"],
                                                   v4_se=cmp4["paired_delta_se"]))
    return "\n\n".join(parts)


def diff_block_for(task):
    # No best/ dir exists for a baseline arm -- this returns None for every
    # task, which is the same path v4's never-optimized tasks take.
    return build_diff_block(
        ARTIFACTS_DIR / "seed",
        ARTIFACTS_DIR / "v5_b1_e1" / task / "best",
        ("artifacts/v5/seed/", "../../../artifacts/v5/seed/"),
        (f"artifacts/v5/v5_b1_e1/{task}/best/", f"../../../artifacts/v5/v5_b1_e1/{task}/best/"),
    )


def main():
    check_only = "--check" in sys.argv
    stats_only = "--stats" in sys.argv

    results = json.loads(RESULTS_JSON.read_text())
    rows = results["task_ledger"]
    overall = results["sections"]["overall"]
    noise = results["sections"]["noise_floor"]

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
            build_auto_block(row, overall),
            diff_block_for(row["task"]),
            existing,
            prefilled_hand=prefilled_hand(row, overall, noise, results["sections"]),
        )
        if new_text == existing:
            continue
        stale.append(str(path.relative_to(ROOT)))
        if not check_only:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(new_text)

    if not stale:
        print("reports/v5/v5_b1_e1/*.md already up to date.")
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
