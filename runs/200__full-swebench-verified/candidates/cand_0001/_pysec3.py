import json, os, sys
TRAJ = "trajectories"
t = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
vs = (d['rollout'].get('metadata') or {}).get('verifier_stdout', '') or ''
lines = [ln for ln in vs.splitlines() if 'Creating table' not in ln and 'Applying' not in ln]
txt = "\n".join(lines)
# print all indices of "test_xdist_longrepr"
import re
for m in re.finditer(r"test_xdist_longrepr_to_str_issue_241", txt):
    print("hit at", m.start())
i = txt.find("test_xdist_longrepr_to_str_issue_241")
print(txt[max(0,i-3000):i][:3000])
