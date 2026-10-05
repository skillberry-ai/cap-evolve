import json

d = json.load(open("trajectories/django__django-16667__cand_0002__t0.json"))
ro = d.get("rollout") or {}
meta = ro.get("metadata") or {}
vs = meta.get("verifier_stdout", "") or ""
lines = vs.splitlines()
print("\n".join(lines[:80]))
