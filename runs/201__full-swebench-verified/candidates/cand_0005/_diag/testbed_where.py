"""Where did /opt/miniconda3/envs/testbed appear in django-10554? Print step context."""
import json

d = json.load(open("trajectories/django__django-10554__seed__t0.json"))
steps = d["rollout"]["trace"]["steps"]
for s in steps:
    blob = json.dumps(s)
    if "envs/testbed" in blob:
        print("STEP", s.get("step_id"))
        for tc in s.get("tool_calls") or []:
            print("  CMD:", (tc.get("arguments") or {}).get("command", "")[:300])
        for r in (s.get("observation") or {}).get("results") or []:
            c = r.get("content", "")
            idx = c.find("envs/testbed")
            if idx >= 0:
                print("  OBS ...", c[max(0, idx-300):idx+200].replace("\\n", "\n")[:600])
        print()
