#!/usr/bin/env python3
"""Regenerate the DATA/SUMMARIES blocks in ui/heatmap_v5_t1_e1.html from
results/v5/v5_t1_e1/results.json.

Usage: python3 scripts/build_v5_t1_heatmap.py [--check]
  --check   exit 1 if regenerating would change heatmap_v5_t1_e1.html, instead of writing it.
"""
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = ROOT / "results" / "v5" / "v5_t1_e1" / "results.json"
HEATMAP_HTML = ROOT / "ui" / "heatmap_v5_t1_e1.html"

DATA_START_RE = re.compile(r"^const DATA = \[\n", re.MULTILINE)
DATA_END_RE = re.compile(r"^\];\n", re.MULTILINE)
SUMMARY_RE = re.compile(r"(const SUMMARIES =\n)(.*?)(\n;\n)", re.DOTALL)

FIELDS = [
    "task", "category", "origin", "status",
    "reward", "stderr", "errored_trials", "cost_usd", "headroom",
    "prior_arm", "prior_arm_mean", "delta_vs_prior_arm",
]


def build_data_block(tasks):
    entries = [{k: t.get(k) for k in FIELDS} for t in tasks]
    body = json.dumps(entries, indent=2)
    lines = body.splitlines()
    assert lines[0] == "[" and lines[-1] == "]"
    return "\n".join(lines[1:-1])


def build_summaries_block(ledger, category_summaries):
    """One MEAN row per category plus a pooled "overall" row, each carrying
    the matched-subset prior-arm mean too (over only the tasks in that
    category that actually have a prior_arm_mean, same discipline as the
    comparison report: never average two different task subsets together)."""
    rows = []
    for s in category_summaries:
        cat = s["category"]
        rows_c = ledger if cat == "overall" else [r for r in ledger if r["category"] == cat]
        with_prior = [r for r in rows_c if r["prior_arm_mean"] is not None]
        row = {
            "category": cat,
            "n_tasks": s["n_tasks"],
            "reward_mean": s["reward_mean"],
            "n_with_prior_arm": len(with_prior),
            "prior_arm_mean_mean": (
                round(statistics.fmean(r["prior_arm_mean"] for r in with_prior), 4)
                if with_prior else None
            ),
            "delta_vs_prior_arm_mean": (
                round(statistics.fmean(r["delta_vs_prior_arm"] for r in with_prior), 4)
                if with_prior else None
            ),
        }
        rows.append(row)
    return rows


def regenerate(results, check_only):
    html = HEATMAP_HTML.read_text()

    start_m = DATA_START_RE.search(html)
    if not start_m:
        print("ERROR: could not find 'const DATA = [' in heatmap_v5_t1_e1.html", file=sys.stderr)
        return 2
    end_m = DATA_END_RE.search(html, start_m.end())
    if not end_m:
        print("ERROR: could not find closing '];' for DATA block", file=sys.stderr)
        return 2

    new_data_block = build_data_block(results["task_ledger"]) + "\n"
    new_html = html[: start_m.end()] + new_data_block + html[end_m.start():]

    s_m = SUMMARY_RE.search(new_html)
    if not s_m:
        print("ERROR: could not find 'const SUMMARIES =' block in heatmap_v5_t1_e1.html", file=sys.stderr)
        return 2
    summaries = build_summaries_block(results["task_ledger"], results["sections"]["task"]["summaries"])
    new_html = (
        new_html[: s_m.start()]
        + s_m.group(1)
        + json.dumps(summaries, indent=2)
        + s_m.group(3)
        + new_html[s_m.end():]
    )

    if new_html == html:
        print("heatmap_v5_t1_e1.html DATA/SUMMARIES blocks already up to date.")
        return 0
    if check_only:
        print("heatmap_v5_t1_e1.html is STALE relative to results/v5/v5_t1_e1/results.json.", file=sys.stderr)
        return 1

    HEATMAP_HTML.write_text(new_html)
    print(f"Regenerated heatmap_v5_t1_e1.html from {len(results['task_ledger'])} tasks.")
    return 0


def main():
    check_only = "--check" in sys.argv
    results = json.loads(RESULTS_JSON.read_text())
    return regenerate(results, check_only)


if __name__ == "__main__":
    raise SystemExit(main())
