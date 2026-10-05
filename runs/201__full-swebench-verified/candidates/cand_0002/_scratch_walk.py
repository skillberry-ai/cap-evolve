"""Locate where command outputs live in ATIF v1.7 steps (optimizer scratch)."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
steps = d["rollout"]["trace"]["steps"]

def walk(obj, path_so_far="", depth=0):
    if depth > 6:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            walk(v, f"{path_so_far}.{k}", depth + 1)
    elif isinstance(obj, list):
        if obj and isinstance(obj[0], (dict, list)):
            walk(obj[0], f"{path_so_far}[0]", depth + 1)
        else:
            s = str(obj)[:100]
            print(f"{path_so_far} = {s!r}")
    else:
        s = str(obj)[:100]
        if s.strip():
            print(f"{path_so_far} = {s!r}")

# step 13 (pytest cmd), step 14 (runtests)
for sid in (13, 14):
    for s in steps:
        if s.get("step_id") == sid:
            print(f"\n=== step {sid} structure ===")
            walk(s)
