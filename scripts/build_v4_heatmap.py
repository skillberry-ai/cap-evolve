#!/usr/bin/env python3
"""Regenerate the DATA/SUMMARIES blocks in ui/heatmap_v4.html from
results/v4/results.json.

Usage: python3 scripts/build_v4_heatmap.py [--check]
  --check   exit 1 if regenerating would change heatmap_v4.html, instead of writing it.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = ROOT / "results" / "v4" / "results.json"
HEATMAP_HTML = ROOT / "ui" / "heatmap_v4.html"

DATA_START_RE = re.compile(r"^const DATA = \[\n", re.MULTILINE)
DATA_END_RE = re.compile(r"^\];\n", re.MULTILINE)
SUMMARY_RE = re.compile(r"(const SUMMARIES =\n)(.*?)(\n;\n)", re.DOTALL)

FIELDS = [
    "task", "category", "tranche", "services", "status",
    "jb_reward", "jb_completion", "jb_tool_calls", "jb_answer", "jb_n",
    "our_baseline", "our_baseline_n",
    "seed", "cand_0001", "cand_0002", "cand_0003",
    "best", "best_tag",
    "final", "final_n",
    "delta_vs_jb", "delta_vs_our_baseline",
    "t4_reward", "t4_delta_vs_our_baseline",
]


def build_data_block(tasks):
    entries = [{k: t.get(k) for k in FIELDS} for t in tasks]
    body = json.dumps(entries, indent=2)
    lines = body.splitlines()
    assert lines[0] == "[" and lines[-1] == "]"
    return "\n".join(lines[1:-1])


def build_summaries_block(task_section):
    """Merge sections.task.summaries (T1/T2 comparison) with t4_summary
    (T4's regression check) by tranche, so the heatmap's one MEAN row per
    tranche can show both without a second summary table."""
    t4_by_tranche = {s["tranche"]: s for s in task_section["t4_summary"]}
    merged = []
    for s in task_section["summaries"]:
        row = dict(s)
        t4 = t4_by_tranche.get(s["tranche"])
        if t4:
            row["t4_reward_mean"] = t4["t4_reward_mean"]
            row["t4_delta_vs_our_baseline_mean"] = t4["delta_vs_our_baseline_mean"]
        merged.append(row)
    return merged


def regenerate(results, check_only):
    html = HEATMAP_HTML.read_text()

    start_m = DATA_START_RE.search(html)
    if not start_m:
        print("ERROR: could not find 'const DATA = [' in heatmap_v4.html", file=sys.stderr)
        return 2
    end_m = DATA_END_RE.search(html, start_m.end())
    if not end_m:
        print("ERROR: could not find closing '];' for DATA block", file=sys.stderr)
        return 2

    new_data_block = build_data_block(results["task_ledger"]) + "\n"
    new_html = html[: start_m.end()] + new_data_block + html[end_m.start():]

    s_m = SUMMARY_RE.search(new_html)
    if not s_m:
        print("ERROR: could not find 'const SUMMARIES =' block in heatmap_v4.html", file=sys.stderr)
        return 2
    new_html = (
        new_html[: s_m.start()]
        + s_m.group(1)
        + json.dumps(build_summaries_block(results["sections"]["task"]), indent=2)
        + s_m.group(3)
        + new_html[s_m.end():]
    )

    if new_html == html:
        print("heatmap_v4.html DATA/SUMMARIES blocks already up to date.")
        return 0
    if check_only:
        print("heatmap_v4.html is STALE relative to results/v4/results.json.", file=sys.stderr)
        return 1

    HEATMAP_HTML.write_text(new_html)
    print(f"Regenerated heatmap_v4.html from {len(results['task_ledger'])} tasks.")
    return 0


def main():
    check_only = "--check" in sys.argv
    results = json.loads(RESULTS_JSON.read_text())
    return regenerate(results, check_only)


if __name__ == "__main__":
    raise SystemExit(main())
