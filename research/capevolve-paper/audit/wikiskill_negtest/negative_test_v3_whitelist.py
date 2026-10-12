#!/usr/bin/env python3
"""Gold-isolation negative test for the WikiSkill community adapter. usage: negative_test.py <run_dir> -> <run_dir>/negative_test.json
(a) every file staged to a role (the ONLY filesystem view the maintainer/proposer has) is scanned for gold paths/ids;
(b) upstream RoleTools (the sole tool executor) is probed with escape attempts and must refuse every one."""
import json, sys, tempfile
from pathlib import Path
BASE = Path("/home/dev/projects2/campaign-scratch/baselines")
sys.path.insert(0, str(BASE / "wikiskill_community/repo/src")); sys.path.insert(0, str(BASE / "code"))
from wikiskill.isolated.tools_server import RoleTools
import sb_eval_lib as L
run = Path(sys.argv[1]); sp = L.load_split()
GOLD_MARKERS = ["spreadsheetbench_verified_400", "/data/extracted", "golden", "gold", "answer_key", "ground_truth", "reference_path",
                "SPREADSHEETBENCH_GOLD", "_output.xlsx", "_answer.xlsx", "answer.xlsx", "all_data_912", "sample_data_200",
                "spreadsheetbench-data", "capevolve-ci", "reused_seed_run", "rollouts/test", "test_per_task"]
import re
# Whitelist of benign contexts (v3). Anything not whitelisted is a REAL hit. Every occurrence is logged.
OUT_PATH = re.compile(r"/mnt/data/outputs/[\w\-]+_\d+_[0-9a-f]+/\d+_[\w\-]+_output\.xlsx")   # the agent's own output_path
def whitelisted(marker, text, i, f):
    """-> reason id or None. Reasons are documented in the audit file; everything else is a REAL hit."""
    ml = marker.lower()
    if ml == "_output.xlsx":
        j = text.rfind("/mnt/data/outputs/", 0, i + len(marker))
        if j >= 0 and OUT_PATH.match(text, j) and text.find(marker, j) == i: return "W1 agent's own output_path /mnt/data/outputs/<task>_<n>_<hash>/1_<task>_output.xlsx"
        if re.search(r"1_[\w\-<>]+_output\.xlsx$", text[max(0, i - 40):i + len(marker)]): return "W2 agent's own output filename 1_<task>_output.xlsx (truncated-path / os.path.join variants, or the <id> placeholder in skill text)"
        if text[max(0, i - 8):i] == "limit.]\n" or text[max(0, i - 9):i] == "limit.]\\n" or "character limit.]" in text[max(0, i - 12):i]: return "W5 tail fragment of the agent's output filename after the 15000-char trace-truncation marker"
        return None
    if ml == "gold":
        if f.name == "40892.md" and re.search(r"Jumper Gold|Col B: Gold|'Gold'|: Gold|Gold  ", text[max(0, i - 100):i + 60]): return "W3 task 40892 workbook cell value 'Gold' (colour column)"
        if f.name == "ambiguous-blank-spec-na-vs-empty-string.md" and text[max(0, i - 14):i + 4] == "described the gold": return "W4 maintainer wiki prose: 'described the gold' = the checker's expectation inferred from the campaign's gold-safe scorer feedback (counts of expected cells), no gold values/paths"
    return None
res = {"markers": GOLD_MARKERS, "staged_files_scanned": 0, "matches": [], "marker_hits": [], "val_or_test_id_in_payload": [], "probes": []}
for inp in run.glob("study/iterations/*/*/input"):
    for f in inp.rglob("*"):
        if f.is_file():
            t = f.read_text(errors="ignore"); tl = t.lower(); res["staged_files_scanned"] += 1
            for m in GOLD_MARKERS:
                for mo in re.finditer(re.escape(m.lower()), tl):
                    i = mo.start()
                    if m == "gold" and tl[max(0, i - 11):i + 4] == "scorer_feedback_gold_free"[:0]: pass
                    ctx_ = t[max(0, i - 70):i + 50].replace("\n", "\\n")
                    if "gold-free" in t[max(0, i - 1):i + 9] or "gold_free" in t[max(0, i - 1):i + 9]:
                        wl = "W0 our own label"      # our own label 'gold-free' / 'scorer_feedback_gold_free' (a negation, not data)
                    else:
                        wl = whitelisted(m, t, i, f)
                    rec = {"file": str(f.relative_to(run)), "marker": m, "offset": i, "context": ctx_, "whitelisted": bool(wl), "whitelist_reason": wl or None}
                    res["matches"].append(rec)
                    if not wl: res["marker_hits"].append([rec["file"], m])
            for i in sp["val"] + sp["test"]:
                if f"Task {i}\n" in t: res["val_or_test_id_in_payload"].append([str(f.relative_to(run)), i])
with tempfile.TemporaryDirectory() as d:
    d = Path(d); (d / "w/traces").mkdir(parents=True); (d / "c").mkdir(); (d / "outside_secret.txt").write_text("SECRET")
    (d / "w/traces/t1.md").write_text("ok"); (d / "w/skills.json").write_text("{}")
    s = RoleTools(d / "w", d / "c", "proposer", "python3")
    for p in ["../outside_secret.txt", str(d / "outside_secret.txt"), "../../../../etc/passwd", "/etc/passwd",
              str(BASE / "work/agent_view_verified400/dataset.json"), "/home/dev/projects2/campaign-scratch/bench/data/extracted",
              "traces/../../outside_secret.txt"]:
        try:
            v = s.call("read_file", {"path": p}); res["probes"].append({"path": p, "refused": False, "got": str(v)[:40]})
        except Exception as e:
            res["probes"].append({"path": p, "refused": True, "error": type(e).__name__})
    try: s.call("bash", {"command": "cat /etc/passwd"}); res["probes"].append({"path": "bash tool", "refused": False})
    except Exception as e: res["probes"].append({"path": "bash tool", "refused": True, "error": type(e).__name__})
res["n_matches"] = len(res["matches"]); res["n_whitelisted"] = sum(m["whitelisted"] for m in res["matches"])
res["pass"] = not res["marker_hits"] and not res["val_or_test_id_in_payload"] and all(p["refused"] for p in res["probes"]) and res["staged_files_scanned"] > 0
(run / "negative_test.json").write_text(json.dumps(res, indent=1)); print(json.dumps(res, indent=1))
