"""Print the task input (issue text) and verifier output for tasks."""
import json
import sys

for path in sys.argv[1:]:
    d = json.load(open(path))
    r = d["rollout"]
    task = r.get("task_id")
    inp = d.get("input", "")
    if isinstance(inp, dict):
        inp = json.dumps(inp)
    print(f"########## {task} ##########")
    print("--- INPUT (issue) ---")
    print(str(inp)[:2200])
    meta = r.get("metadata") or {}
    print("--- verifier_stdout (tail) ---")
    print(str(meta.get("verifier_stdout"))[-1200:])
    print()
