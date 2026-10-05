"""Compact per-trajectory digest: reward, commands run, key markers (optimizer scratch)."""
import json
import re
import sys

MARKERS = [
    "verify-fix",
    "git commit",
    "pytest: not found",
    "ModuleNotFoundError",
    "conda",
    "/opt/",
    "python -m pytest",
    "runtests.py",
    "COMPLETE_TASK",
    "git apply",
    "unrecognized input",
]

for path in sys.argv[1:]:
    with open(path) as f:
        d = json.load(f)
    score = d["score"]
    steps = d["rollout"]["trace"]["steps"]
    print(f"\n######## {score['task_id']}  reward={score['reward']}  n_steps={len(steps)}")
    for s in steps:
        extra = s.get("tool_calls") or []
        msg = s.get("message") or ""
        # mini-swe-agent: tool_calls in 'extra' steps as JSON string sometimes
        src = s.get("source")
        if src == "agent" and msg.strip() and not extra:
            print(f"  [{s.get('step_id')}] THOUGHT: {msg.strip()[:200]}")
        for tc in extra:
            try:
                fn = tc.get("function_name")
                args = tc.get("arguments") or {}
                cmd = args.get("command", "")
                if cmd:
                    marks = [m for m in MARKERS if m in cmd]
                    print(f"  [{s.get('step_id')}] CMD: {cmd[:160]}{'  <<' + ','.join(marks) + '>>' if marks else ''}")
                else:
                    print(f"  [{s.get('step_id')}] {fn}({json.dumps(args)[:120]})")
            except Exception as e:
                print(f"  [{s.get('step_id')}] ?{e}")
        # observation snippet for failures
        obs = s.get("observation")
        if obs and extra:
            pass
