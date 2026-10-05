"""Extract the agent's actual bash commands from a mini-swe-agent ATIF trajectory.

In the mini-swe-agent format, each agent 'step' message contains the thought and
the bash command; the observation comes back as a user/tool step. We look at the
agent steps and pull out code blocks / commands.
"""
import json
import re
import sys

d = json.load(open(sys.argv[1]))
steps = d["rollout"]["trace"]["steps"]
print(f"### {d['rollout']['task_id']}  reward={d['score'].get('reward')}")
for i, s in enumerate(steps):
    src = s.get("source")
    m = s.get("message", "")
    if not isinstance(m, str):
        continue
    if src == "agent":
        # mini-swe-agent: agent message usually contains ```bash blocks
        blocks = re.findall(r"```(?:bash|sh|shell)?\n(.*?)```", m, re.S)
        if blocks:
            for b in blocks:
                print(f"\n>>> STEP {i} CMD:\n{b[:700]}")
        else:
            print(f"\n>>> STEP {i} THOUGHT: {m[:350]}")
    elif src in ("user", "tool"):
        if "Please solve this issue" in m or i <= 1:
            continue
        print(f"<<< OBS {i}: {m[:400]}")
