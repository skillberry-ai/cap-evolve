import json, sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
steps = d["rollout"]["trace"]["steps"]
for s in steps:
    msg = s.get("message", "")
    print(f"### [{s.get('step_id')}] source={s.get('source')} msg_type={type(msg).__name__}")
    if isinstance(msg, dict):
        print("KEYS:", list(msg.keys()))
        for k, v in msg.items():
            vs = json.dumps(v) if not isinstance(v, str) else v
            print(f"  {k} ({type(v).__name__}, len={len(vs)}): {vs[:300]}")
    else:
        print(f"  len={len(msg)}: {msg[:300]!r}")
