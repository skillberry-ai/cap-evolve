import json, os, sys

TR = "trajectories"

def load(name):
    return json.load(open(os.path.join(TR, name)))

d = load("django__django-10554__seed__t0.json")
steps = d["rollout"]["output"]["steps"]
for i, s in enumerate(steps[:12]):
    msg = s.get("message", "")
    if len(msg) > 700:
        msg = msg[:700] + f"...[+{len(s.get('message',''))-700} chars]"
    print(f"--- step {s.get('step_id')} source={s.get('source')} role={s.get('role','-')}")
    print(msg)
    print()
