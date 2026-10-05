import json, sys, os

TRAJ = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s2/work/cand_0004/trajectories"

def summarize(name):
    f = os.path.join(TRAJ, name)
    data = json.load(open(f))
    steps = data["rollout"]["output"]["steps"]
    print("=" * 100)
    print(name, "reward=", data["score"]["reward"], "steps=", len(steps))
    print("=" * 100)
    for s in steps:
        msg = s.get("message", "") or ""
        # print full message but cap at 4000 chars
        print(f"--- step {s.get('step_id')} [{s.get('source')}] ---")
        print(msg[:4000])
        if len(msg) > 4000:
            print(f"...[truncated, {len(msg)} chars total]")
        print()

if __name__ == "__main__":
    for name in sys.argv[1:]:
        summarize(name)
