#!/usr/bin/env python3
"""§4.1 gold-isolation scan for one GEPA run dir. Prints COUNTS only, never a test id.

GEPA's optimizer is a plain chat completion with no tools: everything it ever sees is the reflection prompt.
So the scan covers every reflection prompt and raw GLM reply (reflection_log.jsonl), GEPA's run log and
state dir, and the GLM ledger's request side is not stored (the gateway logs metadata only).

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
files = [run / "reflection_log.jsonl", run / "gepa_events.jsonl", run / "arm.log"]
files += sorted((run / "gepa").rglob("*")) if (run / "gepa").exists() else []
files = [f for f in files if f.is_file() and f.suffix != ".bin"]
if not (run / "reflection_log.jsonl").is_file():
    sys.exit("ISOLATION_SCAN error: no reflection_log.jsonl (nothing to scan)")
text = "\n".join(f.read_text(errors="replace") for f in files)
# JSON-escaped and raw forms both appear; normalise escaped slashes
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
        path += len(re.findall(rf"(?:spreadsheet/|/){e}(?:/|_)|(?:^|[/\s])\d+_{e}_", text))
    return tok, path


t_tok, t_path = hits(split["test"])
c_tok, c_path = hits(controls)
out["test_ids"] = {"token_hits": t_tok, "path_hits": t_path, "n_ids_checked": len(split["test"])}
out["control_train_ids"] = {"ids": controls, "token_hits": c_tok, "path_hits": c_path}
print("ISOLATION_SCAN", json.dumps(out))
