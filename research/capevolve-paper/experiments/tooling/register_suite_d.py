#!/usr/bin/env python3
"""Append the Suite D pre-registration items to experiments/registry.jsonl (same append-only, hash-chained line format as
experiments/final/freeze.py: every line carries the sha256 of the previous line).  Idempotent per (item, sha256).

    python3 -I register_suite_d.py            # run from anywhere; paths are relative to the paper directory
"""
import hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

PAPER = Path(__file__).resolve().parents[2]
REG = PAPER / "experiments" / "registry.jsonl"
ITEMS = [
    ("suite_D_registration", PAPER / "experiments/configs/suite_D_registration.json", "cells, contrasts, Holm families, margin, final set"),
    ("analysis_plan_suite_D_amendment7", PAPER / "protocol/analysis_plan.md", "analysis plan incl. 5-AMENDMENT 7 (Suite D)"),
    ("suite_D_experiment_design", PAPER / "redesign/EXPERIMENTS.md", "experiment-designer proposal the registration was written against"),
]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    lines = [l for l in (REG.read_text().splitlines() if REG.exists() else []) if l.strip()]
    have = {(json.loads(l).get("item"), json.loads(l).get("sha256")) for l in lines}
    head = subprocess.check_output(["git", "-C", str(PAPER), "rev-parse", "HEAD"], text=True).strip()
    added = 0
    for item, path, note in ITEMS:
        h = sha(path)
        if (item, h) in have:
            continue
        prev = hashlib.sha256(lines[-1].encode()).hexdigest() if lines else None
        d = {"item": item, "sha256": h, "path": str(path.relative_to(PAPER)), "t_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "script_commit": head, "prev_line_sha256": prev, "note": note}
        lines.append(json.dumps(d, sort_keys=True)); have.add((item, h)); added += 1
    REG.write_text("\n".join(lines) + "\n")
    print(f"registry: {added} line(s) added, {len(lines)} total")


if __name__ == "__main__":
    sys.exit(main())
