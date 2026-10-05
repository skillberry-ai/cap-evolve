import json, os, sys

TRAJ = "trajectories"

tasks = sys.argv[1:]
for t in tasks:
    d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
    vs = (d['rollout'].get('metadata') or {}).get('verifier_stdout', '') or ''
    lines = vs.splitlines()
    # capture traceback context around FAIL lines
    out = []
    capture = False
    for ln in lines:
        if 'Traceback (most recent call last)' in ln or ln.startswith('FAIL:') or ln.startswith('FAILED'):
            capture = True
            out.append(ln[:250])
        elif capture:
            out.append(ln[:250])
            if len(out) > 400:
                capture = False
    print(f"===== {t} =====")
    # dedupe consecutive
    prev = None
    for ln in out:
        if ln != prev:
            print(ln)
        prev = ln
    print()
