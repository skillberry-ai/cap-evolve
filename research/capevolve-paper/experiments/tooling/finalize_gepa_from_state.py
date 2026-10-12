#!/usr/bin/env python3
"""finalize_gepa_from_state.py <run_dir> [--write] : build <run_dir>/final/ for a GEPA run that crashed at the hard rollout cap before gepa_run.py wrote best/.
Native selection rule = GEPA's own: best_idx = first argmax of the mean validation score over the programs saved in gepa_run/gepa_state.bin (res.best_idx).
Default is a DRY RUN (prints the selection and checks the frozen candidate dir); --write creates final/{prompt.md,task_template.md,sha256.txt,SELECTION.json}."""
import hashlib, json, pickle, sys
from pathlib import Path
sys.path.insert(0, "/home/dev/projects2/campaign-scratch/baselines/code"); import sb_eval_lib as L
run = Path(sys.argv[1]).resolve(); write = "--write" in sys.argv
st = pickle.load(open(run / "gepa_run/gepa_state.bin", "rb")); vs = st["prog_candidate_val_subscores"]
mean = lambda i: sum(vs[i].values()) / len(vs[i]); best = max(range(len(vs)), key=lambda i: (mean(i), -i))
art = st["program_candidates"][best]; fd = run / "candidates" / f"c{best}"
assert all((fd / f).read_text() == art[f] for f in L.FILES), "frozen candidate differs from GEPA state"
sel = {"rule": "gepa best_idx = first argmax of mean val over saved programs", "best_idx": best, "val_mean": mean(best), "n_programs": len(vs), "gepa_total_num_evals": st["total_num_evals"],
       "val_means": [round(mean(i), 4) for i in range(len(vs))], "frozen_dir": str(fd), "reason_no_best_dir": "gepa.optimize crashed with RolloutCap (hard cap 600) mid-iteration before best/ was written; state saved at the last completed iteration"}
print(json.dumps(sel))
if write:
    fin = run / "final"; fin.mkdir(exist_ok=True)
    for f in L.FILES: (fin / f).write_text(art[f])
    (fin / "sha256.txt").write_text("".join(f"{hashlib.sha256((fin/f).read_bytes()).hexdigest()}  {f}\n" for f in L.FILES)); (fin / "SELECTION.json").write_text(json.dumps(sel, indent=1))
    print((fin / "sha256.txt").read_text())
