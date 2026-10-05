"""What python resolves to in each task + look for env-listing commands."""
import json
from pathlib import Path

for path in sorted(Path("trajectories").glob("*.json")):
    try:
        d = json.load(open(path))
    except Exception:
        continue
    tid = d["score"]["task_id"]
    reward = d["score"]["reward"]
    tr = (d.get("rollout") or {}).get("trace") or {}
    found = []
    for s in tr.get("steps") or []:
        obs = s.get("observation") or {}
        res = obs.get("results") or []
        content = res[0].get("content", "") if res else ""
        try:
            cj = json.loads(content)
            out = (cj.get("output") or "")
        except Exception:
            out = content
        for line in out.splitlines():
            if "which python" in str((s.get("tool_calls") or [{}])[0].get("arguments", {}).get("command", "")):
                found.append(line.strip()[:100])
            if "/envs/" in line or "conda" in line.lower() and len(line) < 150:
                found.append(line.strip()[:150])
    if found:
        print(f"\n### {tid} (reward={reward}):")
        for f in found[:8]:
            print("   ", f)
