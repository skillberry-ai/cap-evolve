import json, os, re, sys

TRAJ = 'trajectories'
task = sys.argv[1]
fn = [f for f in os.listdir(TRAJ) if f.startswith(task)][0]
d = json.load(open(os.path.join(TRAJ, fn)))
out = ((d.get('rollout') or {}).get('output')) or {}
steps = out.get('steps') or []
user_msg = steps[1]['message']
# Print just the issue text (before "You are an expert")
idx = user_msg.find('\n\nYou are an expert')
print(user_msg[:idx if idx > 0 else 3000])
