"""Dump a readable digest of a trajectory (optimizer scratch, not part of the candidate).

Usage: python3 _scratch_digest.py <traj.json> [--full] [--steps N]
"""
import json
import sys

path = sys.argv[1]
full = "--full" in sys.argv
max_steps = None
if "--steps" in sys.argv:
    max_steps = int(sys.argv[sys.argv.index("--steps") + 1])

with open(path) as f:
    d = json.load(f)

ro = d["rollout"]
tr = ro["trace"]
steps = tr["steps"]
score = d["score"]

print(f"### TASK {score['task_id']}  reward={score['reward']}  n_steps={len(steps)}")
print(f"### feedback: {score.get('feedback','')[:300]}")

out = []
for s in steps:
    src = s.get("source", "?")
    msg = s.get("message", "") or ""
    if src == "assistant":
        # assistant messages may carry tool calls / commands
        out.append(f"\n===== STEP {s.get('step_id')} [{src}] =====\n{msg}")
    elif src in ("user", "environment", "tool"):
        out.append(f"\n----- STEP {s.get('step_id')} [{src}] -----\n{msg[:1500]}")
    else:
        out.append(f"\n----- STEP {s.get('step_id')} [{src}] -----\n{msg[:400]}")

text = "".join(out)
if max_steps:
    text = "".join(out[:max_steps])
print(text[:200000] if full else text[:40000])
