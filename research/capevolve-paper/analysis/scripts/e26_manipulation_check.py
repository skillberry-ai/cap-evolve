#!/usr/bin/env python3
"""E26/E36 manipulation check (amendment 8G): per seed and iteration, count proposer tool calls in the saved transcripts.
usage: e26_manipulation_check.py <cell root, e.g. runs/E26/NOHIST> <out.json>
Categories (a call can fall in several):
  designed_rejected_reads  - calls whose input names rejected.jsonl (the one history-like pointer the ablation keeps)
  parent_dir_calls         - calls naming '../..' (registered broad pattern; includes the designed reads)
  hidden_path_attempts     - calls naming history.jsonl, run_main/(candidates|rollouts|native_sims|events|eval_index|state|baseline),
                             LEDGER, JOURNAL, RUNMAP, prior_iterations, INSIGHTS, frozen/, claude_cfg, rollouts_metrics, cand_logger
  registered_hits          - the scan_history_reads.py rule (8G as registered)
  diagnosis_json_writes    - Write/Edit of DIAGNOSIS.json or a shell redirect into it"""
import json, glob, re, sys, os
root, out = sys.argv[1], sys.argv[2]
HID = re.compile(r"history\.jsonl|run_main/(candidates|rollouts|native_sims|events|eval_index|state|baseline)|\.\./(candidates|rollouts|events)|\.\./\.\./(candidates|rollouts|native_sims|events|eval_index|state|baseline|history|work/cand|JOURNAL)|LEDGER|JOURNAL|RUNMAP|prior_iterations|INSIGHTS|frozen/|claude_cfg|rollouts_metrics|cand_logger", re.I)
REG = re.compile(r"(?i)LEDGER|JOURNAL|RUNMAP|prior_iterations|INSIGHTS|run_main/(?:candidates|rollouts|native_sims|events|eval_index|state|baseline|history)|/frozen/|rollouts_metrics|cand_logger|claude_cfg|\.\./\.\.")
CAND = re.compile(r"work/(cand_\d+)")
res = {"cell_root": root, "seeds": {}}
for sdir in sorted(glob.glob(os.path.join(root, "s*"))):
    seed = os.path.basename(sdir); its = []
    for f in sorted(glob.glob(sdir + "/claude_cfg/projects/*/*.jsonl")):
        m = re.search(r"work-(cand-\d+)", f); own = m.group(1).replace("-", "_") if m else None
        row = dict(candidate=own, tool_calls=0, designed_rejected_reads=0, parent_dir_calls=0, hidden_path_attempts=0, registered_hits=0, diagnosis_json_writes=0, hidden_examples=[])
        for line in open(f, errors="replace"):
            try: d = json.loads(line)
            except ValueError: continue
            c = (d.get("message") or {}).get("content")
            if not isinstance(c, list): continue
            for b in c:
                if not (isinstance(b, dict) and b.get("type") == "tool_use"): continue
                inp = b.get("input") or {}; t = json.dumps(inp); row["tool_calls"] += 1
                texts = [v for k, v in inp.items() if k in ("command", "file_path", "path", "pattern") and isinstance(v, str)]
                tt = " ".join(texts)
                if "rejected.jsonl" in tt: row["designed_rejected_reads"] += 1
                if "../.." in tt: row["parent_dir_calls"] += 1
                others = [x for x in CAND.findall(tt) if x != own]
                if HID.search(tt) or others:
                    row["hidden_path_attempts"] += 1
                    if len(row["hidden_examples"]) < 2: row["hidden_examples"].append(tt[:160])
                if REG.search(tt) or others: row["registered_hits"] += 1
                if b.get("name") in ("Write", "Edit") and "DIAGNOSIS.json" in str(inp.get("file_path", "")): row["diagnosis_json_writes"] += 1
                elif b.get("name") == "Bash" and re.search(r">\s*\S*DIAGNOSIS\.json|DIAGNOSIS\.json\s*<<", str(inp.get("command", ""))): row["diagnosis_json_writes"] += 1
        its.append(row)
    tot = {k: sum(r[k] for r in its) for k in ("tool_calls", "designed_rejected_reads", "parent_dir_calls", "hidden_path_attempts", "registered_hits", "diagnosis_json_writes")}
    wd = os.path.join(sdir, ".capevolve/run_main/work")
    forb = [p for p in glob.glob(wd + "/*/*") if re.search(r"LEDGER|JOURNAL|RUNMAP|INSIGHTS|prior_iterations", os.path.basename(p))]
    diag = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(wd + "/*/DIAGNOSIS.json"))
    res["seeds"][seed] = dict(iterations_with_transcript=len(its), workdirs=len(glob.glob(wd + "/*")), forbidden_files_in_workdirs=len(forb), diagnosis_json_files_in_workdirs=diag, totals=tot, per_iteration=its)
json.dump(res, open(out, "w"), indent=1)
for s, v in res["seeds"].items(): print(s, v["iterations_with_transcript"], v["workdirs"], v["forbidden_files_in_workdirs"], v["diagnosis_json_files_in_workdirs"], v["totals"])
