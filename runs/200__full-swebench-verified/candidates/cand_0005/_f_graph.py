import sys, json, subprocess
out = subprocess.run(["git", "show", "b30cf23:graph.jsonl"], capture_output=True, text=True).stdout
for l in out.splitlines():
    if l.strip():
        d = json.loads(l)
        print(json.dumps(d)[:600])
