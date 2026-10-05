import json, os, sys

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

def obs_of(s):
    obs, rc = "", None
    if s.get("observation"):
        try:
            c = s["observation"]["results"][0]["content"]
            j = json.loads(c)
            obs = j.get("output", "") or ""
            rc = j.get("returncode")
        except Exception:
            pass
    return obs, rc

task = sys.argv[1]
d = load(task)
r = d["rollout"]
steps = (r.get("trace") or {}).get("steps") or []
meta = r.get("metadata") or {}
vs = meta.get("verifier_stdout", "") or ""

# Where does the verifier's test run fail? Grab the FAILED lines and surrounding context.
lines = vs.splitlines()
interesting = []
for i, ln in enumerate(lines):
    if ln.startswith("FAILED ") or "ERROR test" in ln or "ERROR:" in ln[:30]:
        interesting.append(i)
print(f"== {task}: verifier FAILED/ERROR lines ({len(interesting)})")
for i in interesting[:25]:
    print("  ", lines[i][:200])

# Show the summary lines
for ln in lines:
    if ln.startswith(("=====", "PASSED ", "FAILED ", "ERROR ", "SKIPPED ", "Ran ", "OK", "FAILED (", "= FAIL", "= PASS", "= ERROR")):
        print("S>", ln[:200])
