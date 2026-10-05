import json, sys

p = sys.argv[1]
maxlen = int(sys.argv[2]) if len(sys.argv) > 2 else 700
with open(p) as f:
    d = json.load(f)
steps = d["rollout"]["output"]["steps"]
print("N steps:", len(steps))
for s in steps:
    src = s.get("source", "?")
    msg = s.get("message", "")
    obs = s.get("observation", "") or s.get("output", "")
    print(f"--- step {s.get('step_id')} [{src}] ---")
    if src == "assistant":
        # show tool call command + reasoning
        print(msg[:maxlen])
        for k in s:
            if k not in ("step_id", "source", "message"):
                print(f"   ({k}):", str(s[k])[:300])
    else:
        m = msg
        print(m[:maxlen])
        for k in s:
            if k not in ("step_id", "source", "message"):
                print(f"   ({k}):", str(s[k])[:maxlen])
