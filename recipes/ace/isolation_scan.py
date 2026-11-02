#!/usr/bin/env python3
"""§4.1 gold-isolation scan for one ACE run dir. Prints COUNTS only, never a test id.

ACE's Reflector and Curator are plain chat completions with no tools: everything they ever see is their prompt.
ACE's own logger writes every call's full prompt and response (ace/ace_run_*/detailed_llm_logs/*.json), so the
scan covers those, the Generator responses this port built (generator_calls.jsonl), the bullet-usage log, the
playbooks, curator diffs, and the arm log.

  gold paths  : exp895/data, _golden.xlsx, _answer.xlsx, spreadsheetbench/evaluation, ~/secrets
  test ids    : each official TEST id as a whole token; 'path' hits = the id next to a dataset path separator
  control     : the smoke's own train ids, same matcher, must be > 0 (the scan can see ids)

Usage: isolation_scan.py RUN_DIR SPLIT_IDS_JSON CONTROL_ID [CONTROL_ID ...]
"""
import json
import re
import sys
from pathlib import Path

run, split = Path(sys.argv[1]), json.load(open(sys.argv[2]))
controls = sys.argv[3:]
files = [run / "generator_calls.jsonl", run / "arm.log", run / "best_playbook.txt", run / "final_playbook.txt"]
files += sorted(p for p in (run / "ace").rglob("*")) if (run / "ace").exists() else []
files = [f for f in files if f.is_file()]
llm_logs = [f for f in files if "detailed_llm_logs" in f.parts and f.suffix == ".json"]
if not llm_logs:
    sys.exit("ISOLATION_SCAN error: no ACE detailed_llm_logs (nothing to scan)")
def visible(f: Path) -> str:
    """Optimizer-visible text only. From generator_calls.jsonl that is each record's `response` (what the
    Reflector receives as the reasoning trace); its metadata fields (trial seeds, spend) are never shown to an
    LLM, and a trial seed such as 3002 would otherwise collide with a numeric task id."""
    t = f.read_text(errors="replace")
    if f.name == "generator_calls.jsonl":
        return "\n".join(json.loads(x).get("response", "") for x in t.splitlines() if x.strip())
    return t


text = "\n".join(visible(f) for f in files).replace("\\/", "/")
roles = {}
for f in llm_logs:
    try:
        roles[json.loads(f.read_text()).get("role", "?")] = roles.get(json.loads(f.read_text()).get("role", "?"), 0) + 1
    except Exception:  # noqa: BLE001
        roles["unparsed"] = roles.get("unparsed", 0) + 1

GOLD = {"exp895/data": r"exp895/data", "_golden.xlsx": r"_golden\.xlsx", "_answer.xlsx": r"_answer\.xlsx",
        "spreadsheetbench/evaluation": r"spreadsheetbench/evaluation", "secrets": r"/secrets\b|\.env\b"}
out = {"n_files_scanned": len(files), "llm_call_logs_by_role": roles, "chars_scanned": len(text),
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
