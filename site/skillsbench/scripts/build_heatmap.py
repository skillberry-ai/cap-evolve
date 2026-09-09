#!/usr/bin/env python3
"""Regenerate the `DATA` array embedded in ui/heatmap.html from results/results.json.

Why this exists: ui/heatmap.html has no build step and no fetch() (it's meant to be opened
straight from a checkout over file://, so CORS rules out fetch()). Its DATA array is a
copy of results.json pasted in by hand, and it has drifted before — DATA was missing
`final_test`, so the page's own pass-rate rule (best >= 1.0 OR final_test >= 1.0) silently
undercounted by one task (63/87 instead of 64/87). See results/task-by-task-87/summary.md's
"Known inconsistency" note.

Usage: python3 scripts/build_heatmap.py [--check]
  --check   exit 1 if regenerating would change the file (for CI/pre-commit use), instead
            of writing the update.

This script only touches the first data block (`const DATA = [ ... ];`). The second block
(`const DATA_C4 = [ ... ];`, the c4 prev-vs-curr re-run section) is hand-maintained and left
untouched — it has no equivalent source-of-truth file yet.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = ROOT / "results" / "results.json"
HEATMAP_HTML = ROOT / "ui" / "heatmap.html"

# Field order for each DATA entry. Matches results.json's own task-object field order,
# minus `subcategory` and `iters_spent` (not used by the page's rendering or aggregate
# logic today — add them here if a future feature needs them).
FIELDS = [
    "task", "category", "source", "status",
    "seed", "cand_0001", "cand_0002", "cand_0003", "cand_0004",
    "best", "best_tag", "final_test", "delta",
]

DATA_START_RE = re.compile(r"^const DATA = \[\n", re.MULTILINE)
DATA_END_RE = re.compile(r"^\];\n", re.MULTILINE)


def build_data_block(tasks: list[dict]) -> str:
    entries = []
    for t in tasks:
        entry = {k: t.get(k) for k in FIELDS}
        entries.append(entry)
    # json.dumps with indent=2 gives the same shape as the hand-pasted original
    # (2-space indent, double-quoted keys); re-indent each entry to match the
    # surrounding `  {`/`  }` at 2 spaces already used in the file.
    body = json.dumps(entries, indent=2)
    # json.dumps top-level list uses 0-indent brackets; strip them, we supply our own.
    lines = body.splitlines()
    assert lines[0] == "[" and lines[-1] == "]"
    return "\n".join(lines[1:-1])


def main() -> int:
    check_only = "--check" in sys.argv

    results = json.loads(RESULTS_JSON.read_text())
    tasks = results["tasks"]
    assert len(tasks) == results["total_tasks"], "results.json task count mismatch"

    html = HEATMAP_HTML.read_text()

    start_m = DATA_START_RE.search(html)
    if not start_m:
        print("ERROR: could not find 'const DATA = [' in ui/heatmap.html", file=sys.stderr)
        return 2
    end_m = DATA_END_RE.search(html, start_m.end())
    if not end_m:
        print("ERROR: could not find closing '];' for DATA block", file=sys.stderr)
        return 2

    new_block = build_data_block(tasks) + "\n"
    new_html = html[: start_m.end()] + new_block + html[end_m.start() :]

    if new_html == html:
        print("ui/heatmap.html DATA block already up to date.")
        return 0

    if check_only:
        print("ui/heatmap.html DATA block is STALE relative to results/results.json.", file=sys.stderr)
        return 1

    HEATMAP_HTML.write_text(new_html)
    print(f"Regenerated DATA block from {len(tasks)} tasks in results/results.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
