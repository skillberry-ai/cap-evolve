import subprocess, json

r = subprocess.run(['git', 'show', '8617c6b:baseline.json'], capture_output=True, text=True)
d = json.loads(r.stdout)
print('top keys:', list(d.keys())[:5])
# find train split
for k, v in d.items():
    if isinstance(v, dict):
        print(k, type(v), list(v.keys())[:5])
