#!/usr/bin/env python3
"""Build reports/v5/v5_t1_e1/<task>.md from results/v5/v5_t1_e1/results.json.

v5_t1_e1 is a zero-shot sweep (no optimization), so every task gets the same
simple auto-block shape: one measurement row for v5_t1_e1 itself, plus a
second row for the matched prior arm when one exists (v4_t4_e1/e2 or
h4_t1_e1/e3 -- see results.json's `origin`/`prior_arm*` fields). No existing
report anywhere in this repo has this exact shape -- the closest precedent
(v4_t_e1's not-optimized reports) always compares against two *other*
pre-existing baselines, never a single zero-shot eval of itself -- so this is
a new, minimal auto-block design, reusing v4_report_common.py's splice
machinery unchanged.

No diff block: v5_t1_e1 has no `best/` directory anywhere (nothing was
optimized), so build_diff_block's `best_dir.is_dir()` check naturally returns
None for every task, same as any not-optimized v4 task with no best/ dir.

Usage: python3 scripts/build_v5_t1_task_reports.py [--check] [--stats]
  --check   exit 1 if any auto block is stale, instead of writing it.
  --stats   print coverage: how many reports exist, how many have a
            hand-written narrative (no "_Not yet analysed._" placeholder).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v4_report_common import PLACEHOLDER, build_diff_block, build_report, fmt

ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = ROOT / "results" / "v5" / "v5_t1_e1" / "results.json"
REPORTS_DIR = ROOT / "reports" / "v5" / "v5_t1_e1"
ARTIFACTS_DIR = ROOT / "artifacts" / "v5"

ORIGIN_NOTE = {
    "v4-34": (
        "This task id is byte-identical to one of v4's original 34-task set. "
        "The prior-arm row above is the mean of two independent zero-shot "
        "repeats on that set, `v4_t4_e1`/`v4_t4_e2` -- see "
        "[`../../../results/v4/v4_t_e1/cost_time/`](../../../results/v4/v4_t_e1/cost_time/)."
    ),
    "h4-30": (
        "This task id matches one of h4's 30-task held-out set. The prior-arm "
        "row above is the mean of two drops of that set, `h4_t1_e1` (Oct-04) "
        "and `h4_t1_e3` (Oct-06, harder -- all 5 services declared) -- see "
        "[`../../../reports/v4/h4/all-arms-per-trial.md`](../../h4/all-arms-per-trial.md)."
    ),
    "renamed-content-changed": (
        "This task kept its v4/h4 task **number** but was confirmed to have "
        "different content (`golden.json`/seeds/`verify.py` diff found during "
        "setup) -- there is deliberately no prior-arm comparison row above, "
        "since it would not be measuring the same thing."
    ),
    "new": (
        "This task has no counterpart in v4's 34-task set or h4's 30-task "
        "held-out set -- it is new to v5."
    ),
}


def measurement_rows(row):
    rows = [("v5_t1_e1 (T1, zero-shot)", "val", row["n_trials"], row["reward"])]
    if row.get("prior_arm_mean") is not None:
        rows.append((row["prior_arm"], "val", 5, row["prior_arm_mean"]))
    return rows


def build_auto_block(row):
    from v4_report_common import AUTO_END, AUTO_START

    lines = [AUTO_START, ""]
    lines.append(f"**task:** `{row['task']}`  ")
    lines.append(f"**category:** {row['category']}  ")
    lines.append(f"**origin:** {row['origin']}  ")
    lines.append(f"**status:** {row['status']}  ")
    lines.append("")
    lines.append("_Read no cell without the `n` and split beside it._")
    lines.append("")
    lines.append("| measurement | split | n | reward |")
    lines.append("|---|---|--:|--:|")
    for label, split, n, value in measurement_rows(row):
        lines.append(f"| {label} | {split} | {fmt(n)} | {fmt(value)} |")
    lines.append("")
    trial_str = ", ".join(fmt(v) for v in (row.get("trial_rewards") or []))
    lines.append(f"trial rewards: [{trial_str}] · errored trials: {row['errored_trials']}")
    if row.get("delta_vs_prior_arm") is not None:
        lines.append("")
        lines.append(f"delta vs prior arm ({row['prior_arm']}): {fmt(row['delta_vs_prior_arm'])}")
    lines.append("")
    lines.append(
        f"**cost/time:** ${row['cost_usd']:.4f}, {row['tokens']:,} tokens, "
        f"{row['seconds']/60:.1f} min -- see "
        f"[`../../../results/v5/v5_t1_e1/cost_time/`](../../../results/v5/v5_t1_e1/cost_time/)"
    )
    lines.append("")
    lines.append(AUTO_END)
    return "\n".join(lines)


def diff_block_for(task):
    seed_dir = ARTIFACTS_DIR / "seed"
    best_dir = ARTIFACTS_DIR / "v5_t1_e1" / task / "best"  # never exists -- no optimization
    return build_diff_block(
        seed_dir,
        best_dir,
        ("artifacts/v5/seed/", "../../../artifacts/v5/seed/"),
        (f"artifacts/v5/v5_t1_e1/{task}/best/", f"../../../artifacts/v5/v5_t1_e1/{task}/best/"),
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
            build_auto_block(row),
            diff_block_for(row["task"]),
            existing,
            prefilled_hand=ORIGIN_NOTE[row["origin"]],
        )
        if new_text == existing:
            continue
        stale.append(str(path.relative_to(ROOT)))
        if not check_only:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(new_text)

    if not stale:
        print("reports/v5/v5_t1_e1/*.md already up to date.")
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
