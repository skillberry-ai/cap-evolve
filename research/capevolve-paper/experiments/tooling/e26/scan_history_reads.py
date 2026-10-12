#!/usr/bin/env python3
"""E26 manipulation check: count proposer tool calls that touch prior-iteration material.
usage: scan_history_reads.py <run dir W> [--json out]   (reads W/claude_cfg/projects/*/*.jsonl)
A tool call (Bash command, Read/Edit/Write file_path, Grep/Glob path+pattern) is a HISTORY READ when its text matches
  - the framework history names: LEDGER, JOURNAL, RUNMAP, prior_iterations, INSIGHTS (any case), or
  - run-dir internals: run_main/(candidates|rollouts|native_sims|events|eval_index|state|baseline), /frozen/,
    rollouts_metrics, cand_logger, claude_cfg, or another candidate workdir: work/cand_#### other than the session's own,
  - parent traversal out of the workdir that reaches the run dir: '../..' or the run dir path W itself outside the own workdir.
Own PROCESS.md and rejected.jsonl (designed pointer) are not counted. Counts are per session (= per iteration) and per seed."""
import json, re, sys, glob, os
from pathlib import Path
W = Path(sys.argv[1]).resolve()
PAT = re.compile(r"(?i)LEDGER|JOURNAL|RUNMAP|prior_iterations|INSIGHTS|run_main/(?:candidates|rollouts|native_sims|events|eval_index|state|baseline|history)|/frozen/|rollouts_metrics|cand_logger|claude_cfg|\.\./\.\.")
CAND = re.compile(r"work/(cand_\d+)")
def texts(block):
    inp = block.get("input") or {}
    for k in ("command", "file_path", "path", "pattern", "notebook_path", "description", "prompt"):
        v = inp.get(k)
        if isinstance(v, str):
            yield v
res = {"run": str(W), "sessions": [], "total": 0}
for f in sorted(glob.glob(str(W / "claude_cfg/projects/*/*.jsonl"))):
    own = None
    m = re.search(r"work-(cand-\d+)", f)
    if m:
        own = m.group(1).replace("-", "_")
    hits = []
    for line in open(f, errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        msg = d.get("message") or {}
        c = msg.get("content")
        if not isinstance(c, list):
            continue
        for b in c:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                for t in texts(b):
                    hit = PAT.search(t)
                    others = [x for x in CAND.findall(t) if x != own]
                    if hit or others:
                        hits.append({"tool": b.get("name"), "match": (hit.group(0) if hit else others[0]), "text": t[:200]})
    res["sessions"].append({"file": os.path.relpath(f, W), "own": own, "n_hits": len(hits), "hits": hits[:20]})
    res["total"] += len(hits)
print(json.dumps({"run": res["run"], "total_hits": res["total"], "per_session": [(s["file"].split("/")[-2][-30:], s["n_hits"]) for s in res["sessions"]]}, indent=1))
if "--json" in sys.argv:
    json.dump(res, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
