import json, os, sys
TRAJ = "trajectories"
t = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
vs = (d['rollout'].get('metadata') or {}).get('verifier_stdout', '') or ''
lines = [ln for ln in vs.splitlines() if 'Creating table' not in ln and 'Applying' not in ln]
txt = "\n".join(lines)
i = txt.find("testing/test_reports.py:1")  # file:line markers in tracebacks
print("marker at", i)
# search for the failure detail lines that follow the summary (short test summary with traceback text)
j = txt.find("test_xdist_longrepr_to_str_issue_241 _")
print("underscore header at", j)
if j >= 0:
    print(txt[j-100:j+2500])
