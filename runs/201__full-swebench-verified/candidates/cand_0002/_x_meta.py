import json, sys, os

# Print the git diff the agent's session produced (extracted from the harness
# evaluation metadata if present), else infer from the final git commands.
d = json.load(open(sys.argv[1]))
r = d['rollout']
meta = r.get('metadata') or {}
for k in meta:
    if 'diff' in k.lower() or 'patch' in k.lower() or 'model_patch' in k.lower():
        print('KEY:', k)
        print(str(meta[k])[:5000])
print('metadata keys:', list(meta.keys()))
