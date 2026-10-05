"""Look at score details for failing tasks — what does the scorer feedback say exactly?"""
import json
from pathlib import Path

for path in sorted(Path("trajectories").glob("*.json")):
    try:
        d = json.load(open(path))
    except Exception:
        continue
    tid = d["score"]["task_id"]
    reward = d["score"]["reward"]
    if reward >= 0.5:
        continue
    print(f"\n### {tid} reward={reward}")
    print(json.dumps(d["score"], indent=1)[:800])
    break
