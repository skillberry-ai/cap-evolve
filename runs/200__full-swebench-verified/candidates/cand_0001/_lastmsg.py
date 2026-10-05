import json, os, sys

TRAJ = "trajectories"

def final_agent_message(task):
    data = json.load(open(os.path.join(TRAJ, f"{task}__seed__t0.json")))
    out = data["rollout"]["output"]
    steps = out.get("steps") or []
    msgs = [s["message"] for s in steps if s.get("source") == "agent" and s.get("message")]
    return msgs[-1] if msgs else "(none)"

if __name__ == "__main__":
    for t in sys.argv[1:]:
        print(f"===== {t} =====")
        print(final_agent_message(t)[:2500])
        print()
