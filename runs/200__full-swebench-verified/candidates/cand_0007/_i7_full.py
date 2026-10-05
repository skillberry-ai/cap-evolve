import json, sys

d = json.load(open(sys.argv[1]))
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


idx = int(sys.argv[2]) if len(sys.argv) > 2 else None
for i, s in enumerate(steps):
    if idx is not None and i != idx:
        continue
    if s.get("source") == "agent":
        for tc in s.get("tool_calls") or []:
            cmd = (tc.get("arguments") or {}).get("command", "")
            print("CMD:", cmd[:300])
        obs, rc = obs_of(s)
        print("RC:", rc)
        print("OBS (full):")
        print(obs[:4000])
