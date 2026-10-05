import json, os

BASE = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s1/work/cand_0004"
TRAJ = os.path.join(BASE, "trajectories")

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

d = load("astropy__astropy-13453")
steps = d["rollout"]["output"]["steps"]
# What were the last ~12 agent steps? What did the agent do at the end?
agent_steps = [s for s in steps if s.get("source") == "agent"]
print("n agent steps:", len(agent_steps))
for s in agent_steps[-12:]:
    m = s.get("message")
    tcs = s.get("tool_calls") or []
    obs = s.get("observation") or {}
    print("=" * 100)
    print("MSG:", (m or "")[:400])
    for tc in tcs:
        print("CMD:", (tc.get("arguments") or {}).get("command", "")[:500])
    if obs:
        try:
            c = obs["results"][0]["content"]
            j = json.loads(c)
            print("RC:", j.get("returncode"))
            out = j.get("output") or j.get("output_head") or ""
            print("OUT tail:", out[-700:])
        except Exception as e:
            print("obs parse err", e)
