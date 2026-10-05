import json

d = json.load(open("trajectories/django__django-10554__cand_0002__t0.json"))
ro = d.get("rollout") or {}
meta = ro.get("metadata") or {}
vs = meta.get("verifier_stdout", "") or ""
print("\n".join(vs.splitlines()[:60]))
