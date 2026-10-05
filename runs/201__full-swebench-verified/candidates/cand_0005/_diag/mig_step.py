import json

d = json.load(open("trajectories/django__django-10554__seed__t0.json"))
blob = open("trajectories/django__django-10554__seed__t0.json").read()
# find which step the migrations run appears in
steps = d["rollout"]["trace"]["steps"]
for s in steps:
    sb = json.dumps(s)
    if "Applying admin.0001_initial" in sb:
        print("STEP", s.get("step_id"), "source", s.get("source"))
        for tc in s.get("tool_calls") or []:
            print("  CMD:", (tc.get("arguments") or {}).get("command", "")[:400])
