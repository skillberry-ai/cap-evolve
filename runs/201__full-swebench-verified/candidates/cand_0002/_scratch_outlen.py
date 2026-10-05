"""Check output truncation: mini-swe-agent usually truncates long outputs. Look for outputs near a limit."""
import json
from pathlib import Path

d = json.load(open("trajectories/django__django-12325__seed__t0.json"))
tr = d["rollout"]["trace"]
lens = []
for s in tr.get("steps") or []:
    obs = s.get("observation") or {}
    res = obs.get("results") or []
    if not res:
        continue
    content = res[0].get("content", "")
    try:
        cj = json.loads(content)
        out = cj.get("output") or ""
    except Exception:
        out = content
    lens.append((len(out), s.get("step_id")))
lens.sort(reverse=True)
print("top output lengths:", lens[:10])
# check for truncation markers
for s in tr.get("steps") or []:
    obs = s.get("observation") or {}
    res = obs.get("results") or []
    if not res:
        continue
    content = res[0].get("content", "")
    if "truncated" in content.lower() or "output limit" in content.lower():
        print("TRUNCATION at step", s.get("step_id"), content[:300])
