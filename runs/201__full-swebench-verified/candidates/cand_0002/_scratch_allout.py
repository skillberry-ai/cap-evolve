"""Extract key test command outputs across ALL failing trajectories (correct observation location)."""
import json
from pathlib import Path

KEYS = ("pytest", "runtests", "bin/test", "python -m pytest", "python -c", "python - <<", "python /", "tox", "conda", "pip install", "PYTHONPATH", "python3", "verify-fix")

for path in sorted(Path("trajectories").glob("*.json")):
    try:
        d = json.load(open(path))
    except Exception:
        continue
    score = d["score"]
    if score["reward"] >= 0.5:
        continue
    tr = (d.get("rollout") or {}).get("trace") or {}
    steps = tr.get("steps") or []
    print(f"\n######## {score['task_id']}  reward={score['reward']}")
    for s in steps:
        obs = s.get("observation") or {}
        res = obs.get("results") or []
        content = res[0].get("content", "") if res else ""
        out = ""
        try:
            cj = json.loads(content)
            out = (cj.get("output") or "")
        except Exception:
            out = content
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command") or ""
            if not any(k in cmd for k in KEYS):
                continue
            cmd1 = " ".join(cmd.split())[:130]
            out1 = " ".join((out or "").split())[:240]
            print(f"  [{s.get('step_id')}] CMD: {cmd1}")
            if out1.strip():
                print(f"        OUT: {out1}")
