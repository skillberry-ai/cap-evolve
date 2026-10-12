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
GOLD_MARKERS = ["spreadsheetbench_verified_400", "/data/extracted", "golden", "answer_key", "ground_truth", "reference_path", "SPREADSHEETBENCH_GOLD", "gold_dir", "/gold/", "gold.xlsx", "solution.xlsx"]
res = {"staged_files_scanned": 0, "marker_hits": [], "val_or_test_id_in_payload": [], "probes": []}
for inp in run.glob("study/iterations/*/*/input"):
    for f in inp.rglob("*"):
        if f.is_file():
            t = f.read_text(errors="ignore"); res["staged_files_scanned"] += 1
            for m in GOLD_MARKERS:
                if m in t.lower() or m in t:
                    # 'gold-free' appears in our own feedback label; ignore that exact label only
                    t2 = t.replace("scorer_feedback_gold_free", "").replace("gold-free", "")
                    if m.lower() in t2.lower(): res["marker_hits"].append([str(f.relative_to(run)), m])
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
res["pass"] = not res["marker_hits"] and not res["val_or_test_id_in_payload"] and all(p["refused"] for p in res["probes"]) and res["staged_files_scanned"] > 0
(run / "negative_test.json").write_text(json.dumps(res, indent=1)); print(json.dumps(res, indent=1))
