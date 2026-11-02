#!/usr/bin/env python3
"""§4.1 isolation scan for one SkillOpt run: count gold paths and TEST ids in everything the optimizer saw.

The SkillOpt optimizer is a plain chat model with no tools: it sees exactly the messages in
optimizer_transcript.jsonl (system + user prompts it was sent, and its replies). That file is the primary
scan target; the files SkillOpt assembles those prompts from (skillopt_out/**) are scanned too.
Prints counts only, never a test id. A positive control (train/val ids of this run) shows the scan can see ids.

Usage: scan_isolation.py <run_dir> <official split_ids.json>  -> writes <run_dir>/isolation_scan.json
"""
import json
import re
import sys
from pathlib import Path

run, official = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text())
GOLD = {"gold_data_dir": "exp895/data", "golden_xlsx": "_golden.xlsx", "answer_xlsx": "_answer.xlsx",
        "scorer_dir": "spreadsheetbench/evaluation", "secrets": "/secrets/", "claude_cfg": "/.claude"}
test_ids = set(map(str, official["test"]))
split = run / "split"
seen_ids = {str(i["id"]) for n in ("train", "val") for i in json.loads((split / n / "items.json").read_text())}
tok = re.compile(r"(?<![\w-])(\d+(?:-\d+)?)(?![\w-])")
# A bare number in a spreadsheet preview can equal a numeric test id by coincidence; an id in an id CONTEXT
# (spreadsheet/<id>, <n>_<id>_..., id=<id>, Task <id>) is what a real leak looks like. Both are counted.
ctx = re.compile(r"(?:spreadsheet/|\d_|id=|id\": \"|Task |task_id\W+)(\d+(?:-\d+)?)(?![\w-])")


def scan(paths):
    c = {k: 0 for k in GOLD}
    c.update(test_id_hits=0, test_id_in_id_context=0, control_split_id_hits=0, control_split_id_in_id_context=0,
             bytes=0, files=0)
    for p in paths:
        try:
            s = p.read_text(errors="replace")
        except OSError:
            continue
        c["files"] += 1
        c["bytes"] += len(s)
        for k, pat in GOLD.items():
            c[k] += s.count(pat)
        for m in tok.finditer(s):
            t = m.group(1)
            if t in test_ids:
                c["test_id_hits"] += 1
            if t in seen_ids:
                c["control_split_id_hits"] += 1
        for m in ctx.finditer(s):
            t = m.group(1)
            c["test_id_in_id_context"] += t in test_ids
            c["control_split_id_in_id_context"] += t in seen_ids
    return c


tr = run / "optimizer_transcript.jsonl"
res = {"optimizer_transcript": scan([tr]) if tr.exists() else None,
       "optimizer_transcript_calls": sum(1 for _ in tr.open()) if tr.exists() else 0,
       "skillopt_out_tree": scan([p for p in (run / "skillopt_out").rglob("*")
                                  if p.is_file() and p.suffix in (".json", ".jsonl", ".md", ".txt")])}
(run / "isolation_scan.json").write_text(json.dumps(res, indent=1))
print("ISOLATION_SCAN", json.dumps(res))
