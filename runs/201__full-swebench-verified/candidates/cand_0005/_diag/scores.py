"""Summarize all trajectories: task, score, error, last commands."""
import json
import glob
import os

for p in sorted(glob.glob("trajectories/*.json")):
    d = json.load(open(p))
    r = d["rollout"]
    task = r.get("task_id") or os.path.basename(p).split("__")[0]
    score = d.get("score")
    if isinstance(score, dict):
        score = score.get("reward", score)
    err = r.get("error")
    meta = r.get("metadata") or {}
    rew = meta.get("harbor_reward")
    trace = r.get("trace") or {}
    steps = trace.get("steps") or []
    nsteps = len(steps)
    last_msgs = [s.get("message", "") for s in steps
                 if s.get("source") == "agent" and s.get("message")]
    last = (last_msgs[-1] if last_msgs else "")[:110].replace("\n", " ")
    print(f"{task:45s} score={score} rew={rew} err={str(err)[:35]:35s} steps={nsteps:3d} | {last}")
