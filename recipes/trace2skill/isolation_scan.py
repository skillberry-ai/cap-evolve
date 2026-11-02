#!/usr/bin/env python3
"""§4.1 gold-isolation scan for one Trace2Skill run dir. Prints COUNTS only, never a test id.

Trace2Skill's optimizer roles (error analyst, success analyst, MAP/MERGE/translation/verification editors) are plain
chat completions with no tools, so everything GLM ever saw or said is on disk:
  analysis/{error,success}/*_prompt.md          full input messages + reply of every analyst call (upstream writes them)
  evolve_*/intermediates/**                     every editor phase's system + user prompt + reply (--save-intermediates)
  evolve_*/proposer_system_prompts.json          the injected proposer system prompts
  evolve_*/evolve.log, analysis_*.log, pool_logs/** (the agent traces the analysts read)
  gold paths : exp895/data, _golden.xlsx, _answer.xlsx, spreadsheetbench/evaluation, secrets
  test ids   : each official TEST id as a whole token; 'path' hits = next to a dataset path separator / file prefix
  control    : the run's own train ids, same matcher, must be > 0 (the scan can see ids)
Usage: isolation_scan.py RUN_DIR SPLIT_IDS_JSON CONTROL_ID [CONTROL_ID ...]
"""
import json
import re
import sys
from pathlib import Path

run, split = Path(sys.argv[1]), json.load(open(sys.argv[2]))
controls = sys.argv[3:]
roots = [run / "analysis", run / "pool_logs"] + sorted(run.glob("evolve_*"))
files = [f for r in roots if r.exists() for f in sorted(r.rglob("*")) if f.is_file()
         and "llm_cache" not in f.parts]          # llm_cache = diskcache sqlite; the same text is in intermediates
files += [f for f in (run / "analysis_error.log", run / "analysis_success.log") if f.is_file()]
prompts = [f for f in files if f.name.endswith("_prompt.md") or "prompt_samples" in f.parts]
if not prompts:
    sys.exit("ISOLATION_SCAN error: no optimizer prompt files found (nothing to scan)")
text = "\n".join(f.read_text(errors="replace") for f in files).replace("\\/", "/")

GOLD = {"exp895/data": r"exp895/data", "_golden.xlsx": r"_golden\.xlsx", "_answer.xlsx": r"_answer\.xlsx",
        "spreadsheetbench/evaluation": r"spreadsheetbench/evaluation", "secrets": r"/secrets\b|\.env\b"}
out = {"n_files_scanned": len(files), "n_optimizer_prompt_files": len(prompts), "chars_scanned": len(text),
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
