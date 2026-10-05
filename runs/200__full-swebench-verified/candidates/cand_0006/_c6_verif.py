import json, sys

task = sys.argv[1] if len(sys.argv) > 1 else "django__django-16667"
d = json.load(open(f"trajectories/{task}__cand_0002__t0.json"))
ro = d.get("rollout") or {}
meta = ro.get("metadata") or {}
vs = meta.get("verifier_stdout", "") or ""
print("VERIFIER STDOUT (tail 5000):")
print(vs[-5000:] if vs else "NO VERIFIER STDOUT")
print("=== keys in metadata:", sorted(meta.keys()))
print("=== feedback ===", (d.get("score") or {}).get("feedback"))
