import json, os, re

TRAJ = './trajectories'

def get_meta(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    return ((d.get("rollout") or {}).get("metadata")) or {}

task = "django__django-16667"
meta = get_meta(task)
vs = meta.get("verifier_stdout") or ""
print(f"### {task} verifier_stdout FULL (first 6000 chars):")
print(vs[:6000])
print("...")
print("### LAST 1500:")
print(vs[-1500:])
