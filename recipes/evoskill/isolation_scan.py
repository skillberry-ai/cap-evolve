#!/usr/bin/env python3
"""§4.1 gold-isolation scan for one EvoSkill run dir. Prints COUNTS only, never a test id.

EvoSkill's proposer and generator are Claude Code sessions (Read/Bash/Glob/Grep/Write/Edit) inside the bwrap sandbox,
cwd = the EvoSkill project. The scan covers every session's query + full message stream
(optimizer_transcript.jsonl), every permission decision (optimizer_permissions.jsonl), the CLI's stderr, the arm
log, and every file in the project the optimizer could read or wrote (skills, feedback history, program.yaml).

  gold paths  : exp895/data, _golden.xlsx, _answer.xlsx, spreadsheetbench/evaluation, ~/secrets
  test ids    : each official TEST id as a whole token (not inside a longer word/number/cell ref);
                'path' hits = the id next to a dataset path separator or file prefix, i.e. a real task reference.
  control     : the smoke's own train ids, same matcher, must be > 0 (the scan can see ids).

Usage: isolation_scan.py RUN_DIR SPLIT_IDS_JSON CONTROL_ID [CONTROL_ID ...]
"""
import json
import re
import sys
from pathlib import Path

run, split = Path(sys.argv[1]), json.load(open(sys.argv[2]))
controls = sys.argv[3:]
files = [run / n for n in ("optimizer_transcript.jsonl", "optimizer_permissions.jsonl", "optimizer_stderr.log",
                           "arm.log")]
proj = run / "project"
if proj.exists():
    files += sorted(f for f in proj.rglob("*") if f.is_file() and ".git" not in f.relative_to(proj).parts)
files = [f for f in files if f.is_file() and f.suffix not in (".bin", ".pyc")]
if not (run / "optimizer_transcript.jsonl").is_file():
    sys.exit("ISOLATION_SCAN error: no optimizer_transcript.jsonl (nothing to scan)")
text = "\n".join(f.read_text(errors="replace") for f in files)
text = text.replace("\\/", "/")

GOLD = {"exp895/data": r"exp895/data", "_golden.xlsx": r"_golden\.xlsx", "_answer.xlsx": r"_answer\.xlsx",
        "spreadsheetbench/evaluation": r"spreadsheetbench/evaluation", "secrets": r"/secrets\b|\.env\b"}
out = {"files_scanned": [str(f.relative_to(run)) for f in files], "chars_scanned": len(text),
       "gold": {k: len(re.findall(p, text)) for k, p in GOLD.items()}}


def hits(ids):
    tok = path = 0
    for i in ids:
        e = re.escape(str(i))
        tok += len(re.findall(rf"(?<![\w.:-]){e}(?![\w-])", text))
        path += len(re.findall(rf"(?:spreadsheet/|/){e}(?:/|_)|(?:^|[/\s])\d+_{e}_|TASK::{e}\b", text))
    return tok, path


t_tok, t_path = hits(split["test"])
c_tok, c_path = hits(controls)
out["test_ids"] = {"token_hits": t_tok, "path_hits": t_path, "n_ids_checked": len(split["test"])}
out["control_train_ids"] = {"ids": controls, "token_hits": c_tok, "path_hits": c_path}
# Tool calls the optimizer made that touch paths outside the project (the sandbox should make them fail anyway).
outside = 0
for line in (run / "optimizer_permissions.jsonl").read_text().splitlines() if (run / "optimizer_permissions.jsonl").is_file() else []:
    try:
        d = json.loads(line)
    except json.JSONDecodeError:
        continue
    outside += (not d.get("allow"))
out["approver_denials"] = outside
print("ISOLATION_SCAN", json.dumps(out))
