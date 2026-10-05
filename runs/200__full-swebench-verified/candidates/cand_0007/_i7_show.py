import json, os, sys

TRAJ = "trajectories"
task = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 999999

p = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
d = json.load(open(p))
steps = d["rollout"]["output"]["steps"]

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

for i, s in enumerate(steps):
    if i >= n:
        break
    src = s.get("source")
    msg = s.get("message") or ""
    if src == "agent":
        tcs = s.get("tool_calls") or []
        if msg.strip():
            print(f"--- [{i}] AGENT MSG: {msg[:400]}")
        for tc in tcs:
            cmd = (tc.get("arguments") or {}).get("command", "")
            print(f"--- [{i}] CMD: {cmd[:500]}")
        obs, rc = obs_of(s)
        if obs or rc is not None:
            print(f"    [obs rc={rc}] {(obs or '')[:600]}")
    elif src == "user":
        pass
