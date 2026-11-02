#!/usr/bin/env python3
"""Post-search gold-isolation scan for the gepa_full arm (issue #895 §4.1). Prints COUNTS only, never an id.

GEPA's optimizer is a plain reflection LM with no tools, so "what the optimizer saw" is exactly the text of its
prompts and replies. Those are recorded in reflection_log.jsonl (every prompt + raw reply, per component) and in
GEPA's own run_log.txt. Both are scanned for gold/scorer paths, for TEST ids (word-boundary match), and, as a
positive control that the scan can see ids at all, for the run's own train/val ids.

Usage: isolation_scan.py <run_dir>
"""
import json
import re
import sys
from pathlib import Path

REPO = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/sbv400-main")
run = Path(sys.argv[1])
files = [p for p in (run / "reflection_log.jsonl", run / "gepa" / "run_log.txt", run / "gepa" / "run_log_stderr.txt")
         if p.exists()]
text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in files)
gold_patterns = {
    "exp895_data_dir": r"exp895/data",
    "golden_xlsx": r"_golden\.xlsx",
    "answer_xlsx": r"_answer\.xlsx",
    "scorer_dir": r"spreadsheetbench/evaluation",
    "secrets": r"\.?/secrets|RITS_API_KEY|CB_LITELLM_TOKEN",
}
counts = {k: len(re.findall(p, text)) for k, p in gold_patterns.items()}
test_ids = {str(x) for x in json.load(open(REPO / "ci/benchmarks/spreadsheetbench/full_verified/split_ids.json"))["test"]}


def id_hits(ids):
    n = 0
    for i in ids:
        n += len(re.findall(rf"(?<![\w.\-]){re.escape(i)}(?![\w\-]|\.\d)", text))
    return n


own = {l.strip() for f in ("train_ids.txt", "val_ids.txt") if (run / f).exists() for l in open(run / f) if l.strip()}
counts["test_id_hits"] = id_hits(test_ids - own)
counts["positive_control_own_id_hits"] = id_hits(own)
counts["scanned_files"] = [p.relative_to(run).as_posix() for p in files]
counts["scanned_chars"] = len(text)
print("ISOLATION_SCAN", json.dumps(counts))
