import json, os, sys

TRAJ = "trajectories"

FAILING = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555", "django__django-12325",
    "django__django-12708", "django__django-14007", "django__django-14376", "django__django-15629",
    "django__django-16032", "django__django-16667",
    # additional tasks with reward 0 not in the "always failing" header list
]
INFRA = {"django__django-13809", "django__django-15280", "django__django-15741", "django__django-16485",
         "sphinx-doc__sphinx-8638", "sphinx-doc__sphinx-9367"}

def load(task_prefix, tag="cand_0002"):
    fn = os.path.join(TRAJ, f"{task_prefix}__{tag}__t0.json")
    if os.path.exists(fn):
        return json.load(open(fn))
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task_prefix + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

rows = []
for f in sorted(os.listdir(TRAJ)):
    if not f.endswith(".json"):
        continue
    task = f.split("__")[0] + "__" + f.split("__")[1]
    d = json.load(open(os.path.join(TRAJ, f)))
    reward = (d.get("score") or {}).get("reward")
    err = (d.get("rollout") or {}).get("error")
    rows.append((task, reward, err))

print(f"{'task':44s} {'reward':>6s} err")
for t, r, e in sorted(rows, key=lambda x: (x[1] or 0)):
    print(f"{t:44s} {str(r):>6s} {str(e)[:60]}")
