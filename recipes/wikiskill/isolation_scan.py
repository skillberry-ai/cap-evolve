#!/usr/bin/env python3
"""§4.1 gold-isolation scan for one WikiSkill run dir. Prints COUNTS only, never a test id.

The WikiSkill roles (Maintainer, Proposer) have exactly two tools, upstream RoleTools.read_file (confined to the
role's staged workspace by tools_server.safe) and finish. Everything a role ever saw or said is therefore:
  * optimizer_transcript.jsonl  every GLM request message + response of every role session (also per attempt),
  * engine/iterations/*/{maintainer,proposer}/attempt-*/  the staged inputs, tool receipts, final text,
  * engine/wiki/  the wiki the roles wrote, engine/events.jsonl (gate + impact records), arm.log.
Scanned for:
  gold paths : exp895/data, _golden.xlsx, _answer.xlsx, spreadsheetbench/evaluation, ~/secrets
  test ids   : each official TEST id as a whole token; 'path' hits = next to a path separator/file prefix
  control    : train ids, same matcher; must be > 0 (shows the scan can see ids)
  read_file  : every role read_file argument, resolved against its own workspace; any path outside = escape
Usage: isolation_scan.py RUN_DIR SPLIT_IDS_JSON CONTROL_ID [CONTROL_ID ...]
"""
import json
import re
import sys
from pathlib import Path

run, split = Path(sys.argv[1]), json.load(open(sys.argv[2]))
controls = sys.argv[3:]
if not (run / "optimizer_transcript.jsonl").is_file():
    sys.exit("ISOLATION_SCAN error: no optimizer_transcript.jsonl (nothing to scan)")
files = [run / "optimizer_transcript.jsonl", run / "arm.log", run / "engine/events.jsonl"]
files += sorted((run / "engine/iterations").rglob("*")) if (run / "engine/iterations").exists() else []
files += sorted((run / "engine/wiki").rglob("*")) if (run / "engine/wiki").exists() else []
files = [f for f in files if f.is_file() and ("/maintainer/" in str(f) or "/proposer/" in str(f)
                                              or not str(f.relative_to(run)).startswith("engine/iterations"))]
text = "\n".join(f.read_text(errors="replace") for f in files).replace("\\/", "/")

GOLD = {"exp895/data": r"exp895/data", "_golden.xlsx": r"_golden\.xlsx", "_answer.xlsx": r"_answer\.xlsx",
        "spreadsheetbench/evaluation": r"spreadsheetbench/evaluation", "secrets": r"/secrets\b|\.env\b"}
out = {"n_files_scanned": len(files), "chars_scanned": len(text),
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

reads = escapes = failed = 0
for ev in sorted((run / "engine/iterations").glob("*/*/attempt-*/runtime/tool-events.jsonl")):
    ws = (ev.parent.parent / "input").resolve()
    for line in ev.read_text().splitlines():
        r = json.loads(line)
        if r.get("tool") != "read_file":
            continue
        reads += 1
        p = str((r.get("arguments") or {}).get("path", ""))
        if not (ws / p).resolve().is_relative_to(ws):
            escapes += 1
        if not r.get("ok"):
            failed += 1
out["role_read_file"] = {"calls": reads, "outside_workspace": escapes, "refused_or_failed": failed}
print("ISOLATION_SCAN", json.dumps(out))
