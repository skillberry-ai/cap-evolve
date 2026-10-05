import json, os

TRAJ = "trajectories"

rows = []
for f in sorted(os.listdir(TRAJ)):
    if not f.endswith(".json"):
        continue
    d = json.load(open(os.path.join(TRAJ, f)))
    out = d["rollout"].get("output") or {}
    steps = out.get("steps") or []
    if not steps:
        continue
    vs = (d["rollout"].get("metadata") or {}).get("verifier_stdout", "") or ""
    ver_py = "envs/testbed" in vs
    task = f.replace("__cand_0002__t0.json", "")
    reward = d.get("score", {}).get("reward")
    rows.append((task, reward, ver_py))

for task, reward, ver_py in rows:
    print(f"{task:45s} r={reward} verifier_uses_envs_testbed={ver_py}")
