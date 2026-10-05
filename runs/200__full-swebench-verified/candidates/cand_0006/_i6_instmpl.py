import json, os

TRAJ = './trajectories'

def get_rollout(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    return d.get("rollout") or {}

ro = get_rollout("django__django-16667")
out = ro.get("output") or {}
extra = (out.get("agent") or {}).get("extra") or {}
cfg = extra.get("agent_config") or {}
print(cfg.get("instance_template"))
