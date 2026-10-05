import json, os

TRAJ = './trajectories'

def get_rollout(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    return d.get("rollout") or {}

# Critical: The eval environment. Django tests import OK in the verifier
# ("Testing against Django installed in '/testbed/django'") but in the agent's
# shell, `python -m unittest` FAILED with ModuleNotFoundError django/asgiref.
# The verifier uses a DIFFERENT python (miniconda3/envs/testbed, python3.9)
# while the agent's `python` is miniconda3 BASE python3.11 which lacks deps.
# Find the exact paths. In 11555 verifier traceback: /opt/miniconda3/envs/testbed/lib/python3.6
# In 16667 agent shell: /opt/miniconda3/lib/python3.11 (base env!)
# So: /opt/miniconda3/envs/testbed/bin/python is the right interpreter.

# Look for any command that used a full python path or `conda`:
for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith(".json"):
        continue
    task = fn.replace("__cand_0002__t0.json", "")
    ro = get_rollout(task)
    steps = ((ro.get("trace") or {}).get("steps")) or []
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command") or ""
            if "/envs/" in cmd or "conda" in cmd or "testbed/bin" in cmd:
                print(f"### {task} [{i}]: {cmd[:200]!r}")
