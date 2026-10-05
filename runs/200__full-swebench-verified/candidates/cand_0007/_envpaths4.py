import json, os

TRAJ = "trajectories"
# Confirm: agent's `python` interpreter vs verifier's — the agent runs /opt/miniconda3/bin/python (base, 3.11),
# verifier runs /opt/miniconda3/envs/testbed/bin/python. Find evidence of the base-interpreter path in agent cmds.
ev_base, ev_testbed = {}, {}
for f in sorted(os.listdir(TRAJ)):
    if not f.endswith(".json"):
        continue
    task = f.split("__")[0]
    d = json.load(open(os.path.join(TRAJ, f)))
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            c = ((tc.get("arguments") or {}).get("command") or "")
            if "/opt/miniconda3/bin/python" in c:
                ev_base.setdefault(task, []).append(c[:80])
    # traceback paths from failed agent python runs show which interpreter
    for s in steps:
        obs = s.get("observation") or {}
        for r in (obs.get("results") or []):
            try:
                j = json.loads(r.get("content", ""))
                o = j.get("output", "") or ""
                for ln in o.splitlines():
                    if "/opt/miniconda3/" in ln and "File" in ln:
                        p = ln.split('"')[1] if '"' in ln else ""
                        if p.startswith("/opt/miniconda3/bin"):
                            ev_base.setdefault(task + " (tb)", []).append(p)
                        elif p.startswith("/opt/miniconda3/envs/testbed"):
                            ev_testbed.setdefault(task, []).append(p)
            except Exception:
                pass
print("AGENT BASE INTERPRETER EVIDENCE:")
for k, v in list(ev_base.items())[:10]:
    print(" ", k, "->", v[0])
print()
print("AGENT TESTBED-ENV INTERPRETER EVIDENCE (tracebacks resolving under envs/testbed):")
for k, v in list(ev_testbed.items())[:10]:
    print(" ", k, "->", v[0])
