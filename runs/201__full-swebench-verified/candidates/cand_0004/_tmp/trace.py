import json, os, sys

TRAJ = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s2/work/cand_0004/trajectories"

def show(name, max_chars=1800, tail_chars=2000):
    f = os.path.join(TRAJ, name)
    data = json.load(open(f))
    steps = (data["rollout"].get("output") or {}).get("steps", [])
    print("#" * 110)
    print("##", name, "reward=", data["score"]["reward"], "steps=", len(steps))
    print("#" * 110)
    for s in steps:
        msg = s.get("message", "") or ""
        obs = s.get("observation")
        cmd = ""
        for tc in (s.get("tool_calls") or []):
            cmd += tc.get("arguments", {}).get("command", "") + "\n"
        obs_txt = ""
        if obs:
            try:
                res = obs.get("results", [])
                for r in res:
                    c = r.get("content", "")
                    try:
                        j = json.loads(c)
                        obs_txt = f"rc={j.get('returncode')}\n" + (j.get("output") or "")[:max_chars]
                    except Exception:
                        obs_txt = c[:max_chars]
            except Exception:
                obs_txt = str(obs)[:max_chars]
        block = ""
        if msg.strip():
            block += "MSG: " + msg[:1500] + "\n"
        if cmd.strip():
            block += "CMD: " + cmd[:1500] + "\n"
        if obs_txt.strip():
            block += "OBS: " + obs_txt + "\n"
        if block.strip():
            print(f"--- step {s.get('step_id')} [{s.get('source')}] ---")
            print(block)

if __name__ == "__main__":
    mc = int(sys.argv[2]) if len(sys.argv) > 2 else 1800
    show(sys.argv[1], max_chars=mc)
