#!/usr/bin/env python3
"""Regenerate the DATA/SUMMARIES blocks in ui/heatmap_v6_g2_e1.html from
results/v6/v6_g2_e1/results.json's task_ledger + category_summary.

Unlike v4_g_e1/v5_g2_e1's heatmap builders, there is no per-candidate column here:
v6's task_ledger only ever carries seed vs. the final champion (the sealed test
split is scored exactly once, so no intermediate candidate has test-split numbers).

Usage: python3 scripts/build_v6_g2_heatmap.py [--check]
  --check   exit 1 if regenerating would change heatmap_v6_g2_e1.html, instead of writing it.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = ROOT / "results" / "v6" / "v6_g2_e1" / "results.json"
HEATMAP_HTML = ROOT / "ui" / "heatmap_v6_g2_e1.html"

DATA_START_RE = re.compile(r"^const DATA = \[\n", re.MULTILINE)
DATA_END_RE = re.compile(r"^\];\n", re.MULTILINE)
SUMMARY_RE = re.compile(r"(const SUMMARIES =\n)(.*?)(\n;\n)", re.DOTALL)

FIELDS = ["task", "category", "seed", "seed_n", "champion", "champion_n", "delta_vs_seed"]


def build_data_block(task_ledger):
    entries = [{k: t.get(k) for k in FIELDS} for t in task_ledger]
    body = json.dumps(entries, indent=2)
    lines = body.splitlines()
    assert lines[0] == "[" and lines[-1] == "]"
    return "\n".join(lines[1:-1])


def build_summaries(category_summary):
    rows = []
    for cat, s in category_summary.items():
        if cat == "overall":
            continue
        rows.append({
            "category": cat,
            "n_tasks": s["n_tasks"],
            "seed_mean": s["seed_mean"],
            "champion_mean": s["champion_mean"],
            "delta": s["delta"],
        })
    overall = category_summary["overall"]
    rows.append({
        "category": "overall",
        "n_tasks": overall["n_tasks"],
        "seed_mean": overall["seed_mean"],
        "champion_mean": overall["champion_mean"],
        "delta": overall["delta"],
    })
    return rows


def regenerate(results, check_only):
    html = HEATMAP_HTML.read_text()

    start_m = DATA_START_RE.search(html)
    if not start_m:
        print("ERROR: could not find 'const DATA = [' in heatmap_v6_g2_e1.html", file=sys.stderr)
        return 2
    end_m = DATA_END_RE.search(html, start_m.end())
    if not end_m:
        print("ERROR: could not find closing '];' for DATA block", file=sys.stderr)
        return 2

    new_data_block = build_data_block(results["task_ledger"]) + "\n"
    new_html = html[: start_m.end()] + new_data_block + html[end_m.start():]

    s_m = SUMMARY_RE.search(new_html)
    if not s_m:
        print("ERROR: could not find 'const SUMMARIES =' block in heatmap_v6_g2_e1.html", file=sys.stderr)
        return 2
    new_html = (
        new_html[: s_m.start()]
        + s_m.group(1)
        + json.dumps(build_summaries(results["category_summary"]), indent=2)
        + s_m.group(3)
        + new_html[s_m.end():]
    )

    if new_html == html:
        print(f"{HEATMAP_HTML} is up to date")
        return 0
    if check_only:
        print(f"ERROR: {HEATMAP_HTML} is stale (would change on regeneration)", file=sys.stderr)
        return 1

    HEATMAP_HTML.write_text(new_html)
    print(f"wrote {HEATMAP_HTML}")
    return 0


def main():
    check_only = "--check" in sys.argv
    results = json.loads(RESULTS_JSON.read_text())
    return regenerate(results, check_only)


if __name__ == "__main__":
    raise SystemExit(main())
