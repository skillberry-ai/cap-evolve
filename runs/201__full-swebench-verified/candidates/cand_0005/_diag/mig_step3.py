import json

d = json.load(open("trajectories/django__django-10554__seed__t0.json"))
steps = d["rollout"]["trace"]["steps"]
for s in steps:
    for r in (s.get("observation") or {}).get("results") or []:
        c = r.get("content", "")
        if "Applying admin" in c:
            print("STEP", s.get("step_id"), "source", s.get("source"))
            print(c[:2000])
