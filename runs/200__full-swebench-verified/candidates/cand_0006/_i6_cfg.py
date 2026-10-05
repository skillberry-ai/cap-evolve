import json, os, re

TRAJ = './trajectories'

def get_rollout(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    return d.get("rollout") or {}

# Understand the agent_config — what tools, what system prompt is fed, what the environment looks like
task = "django__django-16667"
ro = get_rollout(task)
out = ro.get("output") or {}
extra = (out.get("agent") or {}).get("extra") or {}
cfg = extra.get("agent_config") or {}
for k, v in cfg.items():
    if isinstance(v, str) and len(v) > 400:
        print(f"--- {k} (len {len(v)}) first 300 ---")
        print(v[:300])
    else:
        print(f"--- {k} ---")
        print(v if isinstance(v, str) else json.dumps(v)[:600])
