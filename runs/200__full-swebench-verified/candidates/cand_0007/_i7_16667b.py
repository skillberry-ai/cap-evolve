import json, os

TRAJ = "trajectories"

def obs_of(s):
    obs, rc = "", None
    if s.get("observation"):
        try:
            c = s["observation"]["results"][0]["content"]
            j = json.loads(c)
            obs = j.get("output", "")
            rc = j.get("returncode")
        except Exception:
            pass
    return obs, rc

# In django-16667, the LAST pytest run (rc=1) printed NOTHING.
# Look at what the verifier ran to compare: verifier_stdout for this task
task = "django__django-16667"
p = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
d = json.load(open(p))
vs = d["rollout"]["metadata"].get("verifier_stdout", "")
# find the part where tests run
i = vs.find("test_value_from_datadict")
print("VERIFIER len:", len(vs))
print(vs[:3500])
