"""Find tool result outputs by tool_call_id (outputs may live in the NEXT step or in output.steps) (optimizer scratch)."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
out = d["rollout"]["output"]
osteps = out.get("steps") or []
print("output.steps count:", len(osteps))
if osteps:
    print("first step keys:", list(osteps[0].keys()))
    print(json.dumps(osteps[0], indent=1)[:1500])
