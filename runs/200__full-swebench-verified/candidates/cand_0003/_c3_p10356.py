import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

def obs_of(s):
    if not s.get("observation"):
        return "", None
    try:
        j = json.loads(s["observation"]["results"][0]["content"])
        return j.get("output", "") or "", j.get("returncode")
    except Exception:
        return "", None

# Deep dive on the tasks where the agent DID successfully run tests but still failed:
# pytest-10356 (ranOK=1) — the tests passed but the verifier failed. Why?
# Look at what the agent ran and what the verifier ran.
d = load("pytest-dev__pytest-10356")
out = ((d.get("rollout") or {}).get("output")) or {}
steps = out.get("steps") or []
for i, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    for tc in (s.get("tool_calls") or []):
        c = (tc.get("arguments") or {}).get("command", "")
        obs, rc = obs_of(s)
        if re.search(r"(pytest|py\.test)", c) and not c.startswith(("grep", "cat ", "ls")):
            print(f"--- step {i} rc={rc}: {c[:200]}")
            o = obs or ""
            for l in o.splitlines()[-8:]:
                print(f"   | {l[:150]}")
            print()
meta = ((d.get("rollout") or {}).get("metadata")) or {}
vs = meta.get("verifier_stdout", "") or ""
print("VERIFIER TAIL:")
print(vs[-1500:])
