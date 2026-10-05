"""Extract the agent's actual bash commands from a mini-swe-agent trajectory.

Each agent step message contains the thought and the bash command; the
observation comes back as a user step.
"""
import json
import re
import sys

d = json.load(open(sys.argv[1]))
steps = d["rollout"]["trace"]["steps"]
print(f"### {d['rollout']['task_id']}  reward={d['score'].get('reward')}")
maxlen = int(sys.argv[2]) if len(sys.argv) > 2 else 900
for i, s in enumerate(steps):
    src = s.get("source")
    m = s.get("message", "")
    if not isinstance(m, str):
        continue
    if src == "agent":
        blocks = re.findall(r"```(?:bash|sh|shell|python)?\n(.*?)```", m, re.S)
        if blocks:
            for b in blocks:
                print(f"\n>>> STEP {i} CMD:\n{b[:maxlen]}")
        else:
            print(f"\n>>> STEP {i} THOUGHT: {m[:400]}")
    elif src in ("user", "tool"):
        if "Please solve this issue" in m or i <= 1:
            continue
        print(f"<<< OBS {i}: {m[:600]}")
