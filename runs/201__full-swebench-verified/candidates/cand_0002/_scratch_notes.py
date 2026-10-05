"""Dump rollout.output notes + final_metrics + last steps (optimizer scratch)."""
import json
import sys

for path in sys.argv[1:]:
    with open(path) as f:
        d = json.load(f)
    score = d["score"]
    out = d["rollout"]["output"]
    notes = out.get("notes")
    fm = out.get("final_metrics")
    err = d["rollout"].get("error")
    print(f"\n######## {score['task_id']}  reward={score['reward']}")
    print("notes:", json.dumps(notes)[:800] if notes is not None else None)
    print("error:", json.dumps(err)[:800] if err is not None else None)
    print("final_metrics:", json.dumps(fm)[:800] if fm is not None else None)
    # last two steps messages
    steps = d["rollout"]["trace"]["steps"]
    for s in steps[-3:]:
        msg = (s.get("message") or "")[:300]
        tcs = s.get("tool_calls") or []
        print(f"  last step {s.get('step_id')} [{s.get('source')}]: msg={msg!r} tool_calls={len(tcs)}")
