#!/usr/bin/env python3
"""§4.1 gold-isolation scan for one Meta-Harness run dir. Prints COUNTS only, never a test id.

The optimizer is sandboxed Claude Code (Bash + filesystem) whose cwd is RUN/work. Everything it saw or did is in
claude_wrapper's session logs (work/logs/claude_sessions/*/events.jsonl, meta.json, response.md, tools/*.txt),
plus whatever it wrote under work/ (candidates, reports, pending_eval.json). The scan covers all of work/ and
the outer loop's arm.log.

  gold paths  : exp895/data, _golden.xlsx, _answer.xlsx, spreadsheetbench/evaluation, secrets
  val leak    : val_private/ never inside work/; each val id's token hits inside the session logs (should be 0:
                val is exposed only as an aggregate)
  test ids    : each official TEST id as a whole token; 'path' hits = next to a dataset path separator
  control     : the smoke's own train ids, same matcher, must be > 0 (the scan can see ids)

Usage: isolation_scan.py RUN_DIR SPLIT_IDS_JSON VAL_IDS_FILE CONTROL_ID [CONTROL_ID ...]
"""
import json
import re
import sys
from pathlib import Path

run, split = Path(sys.argv[1]), json.load(open(sys.argv[2]))
val_ids = [l.strip() for l in open(sys.argv[3]) if l.strip()]
controls = sys.argv[4:]
work = run / "work"
sess = work / "logs" / "claude_sessions"
files = sorted(p for p in work.rglob("*") if p.is_file() and "__pycache__" not in p.parts) + [run / "arm.log"]
files = [f for f in files if f.is_file()]
sess_files = [f for f in files if sess in f.parents]
if not sess_files:
    sys.exit("ISOLATION_SCAN error: no claude_sessions logs (nothing to scan)")


def load(fs):
    return "\n".join(f.read_text(errors="replace") for f in fs).replace("\\/", "/")


text, stext = load(files), load(sess_files)
GOLD = {"exp895/data": r"exp895/data", "_golden.xlsx": r"_golden\.xlsx", "_answer.xlsx": r"_answer\.xlsx",
        "spreadsheetbench/evaluation": r"spreadsheetbench/evaluation", "secrets": r"/secrets\b|\.env\b",
        "dot_claude_home": r"/u/[^/\s]+/\.claude"}


def hits(ids, t):
    tok = path = 0
    for i in ids:
        e = re.escape(str(i))
        tok += len(re.findall(rf"(?<![\w.:-]){e}(?![\w-])", t))
        path += len(re.findall(rf"(?:spreadsheet/|/){e}(?:/|_)|(?:^|[/\s])\d+_{e}_", t))
    return tok, path


t_tok, t_path = hits(split["test"], text)
v_tok, v_path = hits([v for v in val_ids if v not in controls], stext)
c_tok, c_path = hits(controls, stext)
out = {"n_files_scanned": len(files), "n_session_files": len(sess_files), "chars_scanned": len(text),
       "gold": {k: len(re.findall(p, text)) for k, p in GOLD.items()},
       "test_ids": {"token_hits": t_tok, "path_hits": t_path, "n_ids_checked": len(split["test"])},
       "val_ids_in_sessions": {"token_hits": v_tok, "path_hits": v_path,
                               "n_ids_checked": len([v for v in val_ids if v not in controls])},
       "val_private_inside_work": any("val_private" in p.parts for p in work.rglob("*")),
       "control_train_ids_in_sessions": {"ids": controls, "token_hits": c_tok, "path_hits": c_path}}
print("ISOLATION_SCAN", json.dumps(out))
