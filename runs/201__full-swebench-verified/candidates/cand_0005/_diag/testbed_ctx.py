import json

d = json.load(open("trajectories/django__django-10554__seed__t0.json"))
blob = open("trajectories/django__django-10554__seed__t0.json").read()
idx = blob.find("envs/testbed/lib/python3.6/unittest/case.py")
print(blob[max(0, idx-1500):idx+500])
