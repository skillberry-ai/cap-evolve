import json, os, sys

TRAJ = 'trajectories'
# Where does prompt.md appear? Check the 'input' field and step 2 user message of a trace.
fn = 'trajectories/django__django-12325__cand_0002__t0.json'
d = json.load(open(fn))
print("INPUT field:", repr(d.get('input'))[:200])
out = d['rollout']['output']
steps = out['steps']
u = [s for s in steps if s.get('source') == 'user'][0]
msg = u['message']
print("USER MSG LEN:", len(msg))
# print the tail after the issue text
idx = msg.find('You are an expert software engineer')
print("--- from 'You are an expert software engineer' ---")
print(msg[idx:idx+6000] if idx >= 0 else "NOT FOUND")
