import json, os, sys
TRAJ = "trajectories"
t = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
vs = (d['rollout'].get('metadata') or {}).get('verifier_stdout', '') or ''
lines = [ln for ln in vs.splitlines() if 'Creating table' not in ln and 'Applying' not in ln]
txt = "\n".join(lines)
# look for "FAILED testing/test_reports.py::...test_xdist" with -rA there should be a FAILURES section before the summary
i = txt.find("= FAILURES =")
if i < 0:
    i = txt.find("_ test_xdist_longrepr_to_str_issue_241 _")
print("section at", i)
print(txt[max(0,i-200):i+2500])
