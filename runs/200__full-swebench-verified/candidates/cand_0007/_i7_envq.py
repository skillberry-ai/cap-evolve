import json, os

TRAJ = "trajectories"
# Critical question: does the SWE-bench testbed env exist at /opt/miniconda3/envs/testbed,
# and do the VERIFIER outputs run there while the agent's own `python` does NOT?
# Evidence: verifier_stdout contains interpreter paths like
# /opt/miniconda3/envs/testbed/lib/python3.6/... in tracebacks.

for f in sorted(os.listdir(TRAJ)):
    if not f.endswith(".json"):
        continue
    d = json.load(open(os.path.join(TRAJ, f)))
    steps = d["rollout"]["output"]["steps"]
    if not steps:
        continue
    vs = d["rollout"]["metadata"].get("verifier_stdout", "") or ""
    agent_py = "envs/testbed" in json.dumps(d["rollout"]["output"]["steps"][:50])
    ver_py = "envs/testbed" in vs
    task = f.replace("__cand_0002__t0.json", "")
    reward = d.get("score", {}).get("reward")
    # find python paths in verifier tracebacks
    paths = set()
    for line in vs.splitlines():
        if "envs/testbed" in line and "File" in line:
            paths.add(line.strip().split("File ")[1][:60])
    print(f"{task:45s} r={reward} agent_mentions_testbed={agent_py} verifier_uses_testbed={ver_py}")
