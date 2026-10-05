import json, os, re

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

def dump(task, only_tail=False):
    p = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(p))
    steps = d["rollout"]["output"]["steps"]
    print("#" * 90)
    print("##", task)
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        msg = (s.get("message") or "").strip()
        if msg:
            print(f"[{idx}] MSG: {msg[:300]}")
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            short = cmd[:200].replace("\n", " ⏎ ")
            print(f"[{idx}] CMD rc={rc}: {short}")
            if rc not in (0, None) and obs:
                print(f"      ERR: {(obs or '')[-250:].replace(chr(10), ' | ')}")

import sys
for t in sys.argv[1:]:
    dump(t)
