import subprocess, json

r = subprocess.run(['git', 'show', '8617c6b:splits.json'], capture_output=True, text=True)
d = json.loads(r.stdout)
print(type(d))
if isinstance(d, dict):
    for k, v in d.items():
        print(k, len(v) if isinstance(v, list) else v)
        if isinstance(v, list):
            print('  sample:', v[:5])
