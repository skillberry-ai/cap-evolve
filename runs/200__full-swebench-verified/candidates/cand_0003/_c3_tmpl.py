import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# The verifier output for django-12039 shows the harness runs Django's own runtests.py
# style runner ("test_columns_list_sql (indexes.tests.SchemaIndexesTests) ... ok").
# For sphinx it uses pytest. For pylint: pytest. Question: how would the agent KNOW
# the right way to run tests? Check the FULL first user message + any system prompt
# info about environment (mini-swe-agent template "You can execute bash commands...").
task = "django__django-12039"
d = load(task)
out = ((d.get("rollout") or {}).get("output")) or {}
steps = out.get("steps") or []
u = [s["message"] for s in steps if s.get("source") == "user"][0]
# find the system template part
i = u.find("You can execute")
print(u[i-500:i+2500] if i >= 0 else "TEMPLATE MARKER NOT FOUND")
