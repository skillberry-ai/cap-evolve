#!/usr/bin/env python3
"""§4.1 gold-isolation scan for one MIPROv2 run dir. Prints COUNTS only, never a test id.

MIPRO's optimizer (the prompt model) is a plain chat completion with no tools: everything it ever sees and
says is in prompt_lm_log.jsonl (every request's messages + every reply). The scan also covers the arm log,
MIPRO's own log_dir, the proposed candidates' text and the arm's bookkeeping files.

  gold paths  : exp895/data, _golden.xlsx, _answer.xlsx, spreadsheetbench/evaluation, ~/secrets
  test ids    : each official TEST id as a whole token; 'path' hits = the id next to a dataset path separator
  control     : the smoke's own train ids, same matcher, must be > 0 (the scan can see ids).

Usage: isolation_scan.py RUN_DIR SPLIT_IDS_JSON CONTROL_ID [CONTROL_ID ...]
"""
import json
import re
import sys
from pathlib import Path

run, split = Path(sys.argv[1]), json.load(open(sys.argv[2]))
controls = sys.argv[3:]
if not (run / "prompt_lm_log.jsonl").is_file():
    sys.exit("ISOLATION_SCAN error: no prompt_lm_log.jsonl (nothing to scan)")
files = [run / n for n in ("prompt_lm_log.jsonl", "arm.log", "mipro_evals.jsonl", "mipro_forward.jsonl")]
files += sorted((run / "mipro").rglob("*")) if (run / "mipro").exists() else []
files += sorted(p for p in (run / "candidates").rglob("*.md")) if (run / "candidates").exists() else []
files = [f for f in files if f.is_file()]
text = "\n".join(f.read_text(errors="replace") for f in files).replace("\\/", "/")
optimizer_only = (run / "prompt_lm_log.jsonl").read_text(errors="replace").replace("\\/", "/")

GOLD = {"exp895/data": r"exp895/data", "_golden.xlsx": r"_golden\.xlsx", "_answer.xlsx": r"_answer\.xlsx",
        "spreadsheetbench/evaluation": r"spreadsheetbench/evaluation", "secrets": r"/secrets\b|\.env\b"}


def hits(ids, t):
    tok = path = 0
    for i in ids:
        e = re.escape(str(i))
        tok += len(re.findall(rf"(?<![\w.:-]){e}(?![\w-])", t))
        path += len(re.findall(rf"(?:spreadsheet/|/){e}(?:/|_)|(?:^|[/\s])\d+_{e}_", t))
    return tok, path


out = {"files_scanned": [str(f.relative_to(run)) for f in files], "chars_scanned": len(text),
       "optimizer_log_chars": len(optimizer_only),
       "gold": {k: len(re.findall(p, text)) for k, p in GOLD.items()}}
t_tok, t_path = hits(split["test"], text)
c_tok, c_path = hits(controls, text)
o_tok, _ = hits(controls, optimizer_only)
out["test_ids"] = {"token_hits": t_tok, "path_hits": t_path, "n_ids_checked": len(split["test"])}
out["control_train_ids"] = {"ids": controls, "token_hits": c_tok, "path_hits": c_path,
                            "token_hits_in_optimizer_log": o_tok}
print("ISOLATION_SCAN", json.dumps(out))
