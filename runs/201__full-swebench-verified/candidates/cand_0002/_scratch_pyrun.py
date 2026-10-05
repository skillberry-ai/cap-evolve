"""Extract python/test commands and their outputs across trajectories (optimizer scratch)."""
import json
from pathlib import Path

KEYS = ("pytest", "runtests", "bin/test", "python -m", "python -c", "python - <<", "python /", "tox", "conda", "pip install", "PYTHONPATH", "python3")

for path in sorted(Path("trajectories").glob("*.json")):
    try:
        with open(path) as f:
            d = json.load(f)
    except Exception:
        continue
    score = d["score"]
    tr = (d.get("rollout") or {}).get("trace") or {}
    steps = tr.get("steps") or []
    if not steps or score["reward"] >= 0.5:
        continue
    print(f"\n######## {score['task_id']}  reward={score['reward']}")
    for s in steps:
        for tc in s.get("tool_calls") or []:
            cmd = (tc.get("arguments") or {}).get("command") or ""
            if not any(k in cmd for k in KEYS):
                continue
            obs = tc.get("observation") or {}
            res = obs.get("results") or []
            content = res[0].get("content", "") if res else ""
            out = ""
            try:
                cj = json.loads(content)
                rc = cj.get("returncode")
                out = (cj.get("output") or "")[:300]
            except Exception:
                rc = "?"
                out = content[:300]
            cmd1 = " ".join(cmd.split())[:135]
            print(f"  [{s.get('step_id')}] rc={rc} CMD: {cmd1}")
            if out.strip():
                print(f"        OUT: {' '.join(out.split())[:260]}")
