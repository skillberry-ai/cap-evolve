import json, os

TRAJ = "trajectories"
# Determine what `python` on PATH is for the AGENT: look at steps where the agent ran
# `python -c "import sys; print(sys.version)"` or `python -V`, or where a traceback shows
# the interpreter path of the agent's own runs (e.g. /opt/miniconda3/lib/python3.11).
# Compare with the verifier's interpreter path.

for f in sorted(os.listdir(TRAJ)):
    if not f.endswith(".json"):
        continue
    d = json.load(open(os.path.join(TRAJ, f)))
    out = d["rollout"].get("output") or {}
    steps = out.get("steps") or []
    if not steps:
        continue
    task = f.replace("__cand_0002__t0.json", "")
    agent_interps = set()
    for s in steps:
        if s.get("source") != "agent":
            continue
        obs = ""
        if s.get("observation"):
            try:
                c = s["observation"]["results"][0]["content"]
                j = json.loads(c)
                obs = j.get("output", "") or ""
            except Exception:
                pass
        for line in obs.splitlines():
            if "File \"/opt/miniconda3" in line:
                # e.g. File "/opt/miniconda3/lib/python3.11/unittest/loader.py"
                parts = line.split("/")
                if len(parts) > 5:
                    agent_interps.add("/" + "/".join(parts[1:5]))
    if agent_interps:
        print(f"{task:45s} agent_interps={sorted(agent_interps)}")
