"""Extract agent_config.instance_template from rollout.output (optimizer scratch)."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
out = d["rollout"]["output"]
cfg = out["agent"]["extra"]["agent_config"]
print("config keys:", list(cfg.keys()))
tpl = cfg.get("instance_template", "")
print("=== instance_template ===")
print(tpl)
