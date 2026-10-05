import json, sys, os

TRAJ = './trajectories'

FAILING = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
]

def steps_of(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    return (d.get("rollout") or {}), ((d.get("rollout") or {}).get("trace") or {}).get("steps") or []

for task in FAILING:
    ro, steps = steps_of(task)
    meta = ro.get("metadata") or {}
    reward = meta.get("harbor_reward")
    vs = (meta.get("verifier_stdout") or "")[-2500:]
    # last agent message
    last_agent = None
    n_tool = 0
    for s in steps:
        if s.get("source") == "agent":
            last_agent = s
            n_tool += len(s.get("tool_calls") or [])
    print("=" * 100)
    print(f"TASK {task}  reward={reward}  steps={len(steps)}  agent_msgs_with_tools={n_tool}")
    print(f"VERIFIER TAIL: ...{vs!r}")
    if last_agent:
        print(f"LAST AGENT MSG (first 1200): {(last_agent.get('message') or '')[:1200]!r}")
