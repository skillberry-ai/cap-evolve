import json, os

TRAJ = "trajectories"
# Check for the interpreter the verifier actually used: look at the first ~40 lines of verifier_stdout
for f in sorted(os.listdir(TRAJ)):
    if not f.endswith(".json"):
        continue
    d = json.load(open(os.path.join(TRAJ, f)))
    vs = (d["rollout"]["metadata"] or {}).get("verifier_stdout", "") or ""
    lines = vs.splitlines()
    exec_lines = [l for l in lines if "/bin/python" in l or "executable:" in l or "python -X dev" in l]
    if exec_lines:
        print(f.split("__")[0], "->", exec_lines[0].strip()[:160])
