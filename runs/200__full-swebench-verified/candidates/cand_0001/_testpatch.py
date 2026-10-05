import json, os, sys

TRAJ = "trajectories"
t = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
vs = (d['rollout'].get('metadata') or {}).get('verifier_stdout', '') or ''
# Find the test_patch diff the harness applied (shows the expected test behavior)
lines = vs.splitlines()
in_patch = False
buf = []
for ln in lines:
    if ln.startswith("diff --git a/tests/") or ln.startswith("diff --git b/tests/"):
        in_patch = True
        buf.append(ln)
        continue
    if in_patch:
        if ln.startswith("+ ") or ln.startswith("++ tee") or ln.startswith("+ git") or ln.startswith("++ mktemp"):
            in_patch = False
            print("\n".join(buf))
            print("~~~~ end patch ~~~~\n")
            buf = []
            continue
        buf.append(ln)
