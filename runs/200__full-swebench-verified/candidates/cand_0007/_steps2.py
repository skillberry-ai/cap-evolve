import json, os, sys

TRAJ = "trajectories"

def obs_of(s):
    obs, rc = "", None
    if s.get("observation"):
        try:
            c = s["observation"]["results"][0]["content"]
            j = json.loads(c)
            obs = j.get("output", "")
            rc = j.get("returncode")
        except Exception:
            pass
    return obs, rc

t = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
steps = (d["rollout"].get("trace") or {}).get("steps") or []
print(f"### {t} reward={d['score']['reward']} steps={len(steps)}")
for idx, s in enumerate(steps):
    src = s.get("source")
    if src == "agent":
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            cmd1 = cmd.replace("\n", " ⏎ ")[:230]
            print(f"[{idx}] AGENT CMD: {cmd1}")
            if rc not in (0, None):
                oo = (obs or "").replace("\n", " | ")[:250]
                print(f"     rc={rc} OUT: {oo}")
    elif src != "system":
        m = (s.get("message") or "")[:150].replace("\n", " | ")
        print(f"[{idx}] {src}: {m}")
msgs = [s.get("message") for s in steps if s.get("source") == "agent" and s.get("message")]
if msgs:
    print("=== FINAL AGENT MESSAGE (last 1500) ===")
    print(msgs[-1][-1500:])
