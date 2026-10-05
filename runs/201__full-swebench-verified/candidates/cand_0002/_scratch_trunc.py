"""Check commands hitting some output limit. Look at outputs that end abruptly (truncated) and the configured limits in the agent config."""
import json
from pathlib import Path

d = json.load(open("trajectories/sympy__sympy-15599__seed__t0.json"))
ro = d.get("rollout") or {}
out = ro.get("output") or {}
cfg = out.get("agent") or {}
print(json.dumps(cfg, indent=1)[:2000])
