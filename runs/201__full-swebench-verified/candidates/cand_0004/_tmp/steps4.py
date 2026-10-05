"""Dump the step-by-step commands of one trajectory (compact)."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)

r = d["rollout"]
tr = r["trace"]
for i, st in enumerate(tr.get("steps", [])):
    # steps likely have keys like action/observation
    keys = list(st.keys())
    if i == 0:
        print("step keys:", keys)
    act = st.get("action") or st.get("command") or ""
    if isinstance(act, dict):
        act = json.dumps(act)
    act = str(act).replace("\n", "\\n")
    obs = st.get("observation") or st.get("output") or ""
    obs = str(obs).replace("\n", "\\n")
    print(f"[{i}] ACT: {act[:300]}")
    print(f"    OBS: {obs[:240]}")
