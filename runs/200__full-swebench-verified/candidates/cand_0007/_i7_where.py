import json, os

TRAJ = "trajectories"
p = os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")
d = json.load(open(p))
out = d["rollout"]["output"]
extra = out.get("agent", {}).get("extra", {})
cfg = extra.get("agent_config", {})
print("CONFIG KEYS:", list(cfg.keys()))
# search for SKILL.md content marker in whole rollout JSON
s = json.dumps(d)
for marker in ["expert software engineer", "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT",
               "Critical rules", "NEVER modify or delete existing test files"]:
    print(marker, "->", marker in s)
