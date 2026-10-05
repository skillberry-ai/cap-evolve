import json

d = json.load(open("trajectories/django__django-10554__seed__t0.json"))
steps = d["rollout"]["trace"]["steps"]
for s in steps:
    sb = json.dumps(s)
    if "Applying admin" in sb or "runtests.py\", line 564" in sb:
        print("STEP", s.get("step_id"), "source", s.get("source"))
        if s.get("source") == "agent":
            for tc in s.get("tool_calls") or []:
                print("  CMD:", (tc.get("arguments") or {}).get("command", "")[:500])
