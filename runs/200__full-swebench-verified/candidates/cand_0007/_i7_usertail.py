import json, sys

d = json.load(open(sys.argv[1]))
u = [s["message"] for s in d["rollout"]["output"]["steps"] if s.get("source") == "user"][0]
prompt = open("prompt.md").read().strip()
if prompt in u:
    i = u.find(prompt)
    tail = u[i + len(prompt):]
else:
    tail = "(prompt.md not found verbatim) " + u[-1500:]
print("TAIL LEN:", len(tail))
print(tail)
