#!/usr/bin/env python3
"""Counts-only view of a run_final root (v2 freeze rule: no reward statistic before the freeze).  Whitelist: jobs, done, missing, pending, infra, error counts.  Never reads reward fields.
usage: python3 -I counts_only.py <root>"""
import json
import sys
from pathlib import Path

KEEP = ("jobs", "done", "pending", "missing_hang", "infra_attempts", "infra_final", "candidate_errors", "empty_output", "raw_tool_text_last", "retried_jobs", "hangs")
root = Path(sys.argv[1])
d = json.load(open(root / "per_arm_report.json"))
tot = {k: 0 for k in KEEP}
for arm, v in sorted(d.items()):
    row = {k: v.get(k, 0) for k in KEEP}
    for k in KEEP:
        tot[k] += row[k] or 0
    print("%-14s %s" % (arm, " ".join("%s=%s" % (k, row[k]) for k in KEEP)))
print("TOTAL          %s" % " ".join("%s=%s" % (k, tot[k]) for k in KEEP))
