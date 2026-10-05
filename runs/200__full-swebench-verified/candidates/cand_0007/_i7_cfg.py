import json, os

TRAJ = "trajectories"

# The candidate skill for this run is a SWE-bench fixing skill (SKILL.md, prompt.md).
# We need to understand: how does the harness construct the agent from SKILL.md?
# Look at agent_config in a trajectory to see what system prompt it got.
p = os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")
d = json.load(open(p))
out = d["rollout"]["output"]
extra = out.get("agent", {}).get("extra", {})
cfg = extra.get("agent_config", {})
for k, v in cfg.items():
    if isinstance(v, str) and len(v) > 300:
        print(f"### {k} (len {len(v)})")
        print(v[:600])
        print("...")
    else:
        print(f"### {k} = {json.dumps(v)[:500]}")
