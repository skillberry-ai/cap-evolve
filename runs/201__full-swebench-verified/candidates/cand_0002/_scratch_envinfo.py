"""Find interpreter/env hints in trajectories."""
import json, re
from pathlib import Path
from collections import Counter

envs = Counter()
for path in sorted(Path("trajectories").glob("*.json")):
    try:
        d = json.load(open(path))
    except Exception:
        continue
    tr = (d.get("rollout") or {}).get("trace") or {}
    for s in tr.get("steps") or []:
        obs = s.get("observation") or {}
        res = obs.get("results") or []
        content = res[0].get("content", "") if res else ""
        try:
            cj = json.loads(content)
            out = (cj.get("output") or "")
        except Exception:
            out = content
        for m in re.finditer(r"/opt/[^\s'\"]*python[^\s'\"]*", out):
            envs[m.group(0)] += 1
for e, c in envs.most_common(20):
    print(c, e)
