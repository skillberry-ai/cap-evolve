"""Check verifier metadata structure + final git diff state (optimizer scratch)."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
md = d.get("metadata") or {}
print("metadata keys:", list(md.keys()))
for k, v in md.items():
    if isinstance(v, str):
        print(f"\n--- {k} (len {len(v)}) ---")
        print(v[:3000])
    else:
        print(f"\n--- {k} ---")
        print(json.dumps(v)[:2000])
