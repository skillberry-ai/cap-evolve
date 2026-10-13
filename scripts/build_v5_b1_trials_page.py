#!/usr/bin/env python3
"""Regenerate the DATA/SUMMARIES blocks in ui/trials_v5_b1_e1.html from
results/v5/v5_b1_e1/results.json.

This is the per-trial view: one row per task showing every individual trial
as its own mark, so run-to-run stochasticity is visible instead of hidden
behind the mean. 68% of v5's tasks are non-deterministic, which is the single
most load-bearing fact about this benchmark for anyone designing an optimizer
gate -- a page that showed only means would misrepresent it.

Same splice contract as ui/heatmap_v4_t.html and its generator: the HTML
skeleton (CSS, axis, legend, render JS) is hand-maintained, and only the two
regex-delimited data blocks are rewritten here.

Usage: python3 scripts/build_v5_b1_trials_page.py [--check]
  --check   exit 1 if regenerating would change the page, instead of writing it.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = ROOT / "results" / "v5" / "v5_b1_e1" / "results.json"
PAGE_HTML = ROOT / "ui" / "trials_v5_b1_e1.html"

DATA_START_RE = re.compile(r"^const DATA = \[\n", re.MULTILINE)
DATA_END_RE = re.compile(r"^\];\n", re.MULTILINE)
SUMMARY_RE = re.compile(r"(const SUMMARIES =\n)(.*?)(\n;\n)", re.DOTALL)

FIELDS = [
    "task", "category", "task_set", "reward", "stderr",
    "trial_rewards", "trial_min", "trial_max", "spread", "sd",
    "variable", "errored_trials", "cost_usd",
]


def build_data_block(tasks):
    entries = [{k: t.get(k) for k in FIELDS} for t in tasks]
    body = json.dumps(entries, indent=2)
    lines = body.splitlines()
    assert lines[0] == "[" and lines[-1] == "]"
    return "\n".join(lines[1:-1])


def build_summaries_block(results):
    """One row per category plus an overall row, plus the two task-set rows,
    each carrying the variability stats the page displays."""
    s = results["sections"]
    rows = []

    def row(label, kind, blk):
        return {
            "label": label,
            "kind": kind,
            "n_tasks": blk["n_tasks"],
            "reward_mean": blk["reward_mean"],
            "n_saturated": blk["n_saturated"],
            "n_variable": blk["n_variable"],
            "pct_variable": blk["pct_variable"],
            "mean_sd_all": blk["mean_sd_all"],
        }

    rows.append(row("ALL TASKS", "overall", s["overall"]))
    for st in ("10-10", "10-12"):
        rows.append(row(f"set {st}", "set", s["by_task_set"][st]))
    for c in ("platform", "icinga", "cloud", "cost"):
        rows.append(row(c, "category", s["by_category"][c]))
    return rows


def regenerate(results, check_only):
    html = PAGE_HTML.read_text()

    start_m = DATA_START_RE.search(html)
    if not start_m:
        print("ERROR: could not find 'const DATA = [' in trials_v5_b1_e1.html", file=sys.stderr)
        return 2
    end_m = DATA_END_RE.search(html, start_m.end())
    if not end_m:
        print("ERROR: could not find closing '];' for DATA block", file=sys.stderr)
        return 2

    new_html = (html[: start_m.end()]
                + build_data_block(results["task_ledger"]) + "\n"
                + html[end_m.start():])

    s_m = SUMMARY_RE.search(new_html)
    if not s_m:
        print("ERROR: could not find 'const SUMMARIES =' block", file=sys.stderr)
        return 2
    new_html = (new_html[: s_m.start()]
                + s_m.group(1)
                + json.dumps(build_summaries_block(results), indent=2)
                + s_m.group(3)
                + new_html[s_m.end():])

    if new_html == html:
        print("trials_v5_b1_e1.html DATA/SUMMARIES blocks already up to date.")
        return 0
    if check_only:
        print("trials_v5_b1_e1.html is STALE relative to results/v5/v5_b1_e1/results.json.",
              file=sys.stderr)
        return 1

    PAGE_HTML.write_text(new_html)
    print(f"Regenerated trials_v5_b1_e1.html from {len(results['task_ledger'])} tasks.")
    return 0


def main():
    check_only = "--check" in sys.argv
    results = json.loads(RESULTS_JSON.read_text())
    return regenerate(results, check_only)


if __name__ == "__main__":
    raise SystemExit(main())
