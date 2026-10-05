"""Extract final agent message (last assistant message) for failing tasks."""
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
    tr = (d.get("rollout") or {}).get("trace") or {}
    steps = tr.get("steps") or []
    # last agent message (with message content)
    last_msg = ""
    for s in steps:
        if s.get("source") == "agent" and (s.get("message") or "").strip():
            last_msg = s["message"]
    print(f"\n######## {tid} (reward={reward})")
    print(last_msg[:1200])
