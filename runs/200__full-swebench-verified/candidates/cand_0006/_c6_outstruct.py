import json

for task in ["django__django-16667", "django__django-12039", "django__django-16032"]:
    d = json.load(open(f"trajectories/{task}__cand_0002__t0.json"))
    ro = d.get("rollout") or {}
    out = ro.get("output") or {}
    print(f"\n########## {task} ##########")
    print("notes:", json.dumps(out.get("notes"))[:500])
    print("final_metrics:", json.dumps(out.get("final_metrics"))[:600])
    agent = out.get("agent") or {}
    print("agent keys:", sorted(agent.keys()))
    print("agent (subset):", json.dumps({k: v for k, v in agent.items() if k != "extra"})[:800])
    ex = agent.get("extra") or {}
    print("agent.extra keys:", sorted(ex.keys()))
    hist = ex.get("history") or ex.get("trajectory") or None
    if hist:
        print("history type:", type(hist), len(hist))
