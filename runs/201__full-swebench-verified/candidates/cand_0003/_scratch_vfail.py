import json, sys, re

p = sys.argv[1]
with open(p) as f:
    d = json.load(f)
md = d["rollout"].get("metadata") or {}
vs = md.get("verifier_stdout") or ""
# print lines around FAIL / ERROR markers
keep = []
for i, ln in enumerate(vs.splitlines()):
    if re.search(r"(FAIL|ERROR|error|assert)", ln) and not ln.startswith("PASSED"):
        keep.append(ln)
print("\n".join(keep[:40]))
