import json

# Look at the last agent messages (message content, not just commands) for a few
# failing vs passing tasks, and the final observation, to see if the agent reported
# a patch. Also look at what the rollout 'output' has besides steps.

for task in ["django__django-16667", "django__django-12039"]:
    d = json.load(open(f"trajectories/{task}__cand_0002__t0.json"))
    ro = d.get("rollout") or {}
    out = ro.get("output") or {}
    print(f"\n########## {task} ##########")
    print("output keys:", sorted(out.keys()))
    steps = out.get("steps") or []
    # last 3 steps messages
    for s in steps[-3:]:
        src = s.get("source")
        m = s.get("message") or ""
        print(f"--- source={src} message tail ---")
        print(m[-1500:])
        print()
