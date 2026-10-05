import json, os, sys

TRAJ = "trajectories"
d = json.load(open(os.path.join(TRAJ, "django__django-10554__seed__t0.json")))
r = d["rollout"]
ac = ((r.get("output") or {}).get("agent") or {}).get("extra") or {}
cfg = ac.get("agent_config") or {}
print("ALL KEYS:", list(cfg.keys()))
# check whether prompt.md content is embedded anywhere in the rollout
blob = json.dumps(r)
import re
for needle in ["expert software engineer", "CRITICAL REQUIREMENTS", "Recommended Workflow", "COMPLETE_TASK_AND_SUBMIT"]:
    print(f"{needle!r} occurrences:", blob.count(needle))
# print the user message (step 1) fully
steps = (r.get("trace") or {}).get("steps") or []
print("=== USER MSG (first 3000) ===")
print(steps[1]["message"][:3000])
