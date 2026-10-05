import json, sys, os

def render(path, out_path, maxobs=1200):
    with open(path) as f:
        d = json.load(f)
    tr = d.get("rollout") or {}
    if not tr or not tr.get("trace"):
        with open(out_path, "w") as f:
            f.write(f"NO TRACE. rollout keys: {list(tr.keys()) if tr else 'none'}; error={tr.get('error')}")
        print(f"{path} -> NO TRACE")
        return
    steps = tr["trace"]["steps"]
    lines = []
    for s in steps:
        msg = s.get("message", "")
        tcs = s.get("tool_calls") or []
        obs = s.get("observation")
        sid = s.get("step_id")
        src = s.get("source")
        if isinstance(msg, str) and msg.strip():
            lines.append(f"### [{sid}] {src} MESSAGE:\n{msg[:2000]}\n")
        for tc in tcs:
            args = tc.get("arguments", {})
            cmd = args.get("command", json.dumps(args))
            lines.append(f"### [{sid}] {src} CMD:\n{cmd[:3000]}\n")
            o = (obs or {}).get("results", [])
            if o:
                c = o[0].get("content", "") if isinstance(o[0], dict) else str(o[0])
                lines.append(f"### [{sid}] OBS (tail {maxobs}):\n{c[-maxobs:]}\n")
    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    print(f"{path} -> {out_path}: {len(steps)} steps, {len(lines)} blocks")

if __name__ == "__main__":
    td = sys.argv[1] if len(sys.argv) > 1 else "trajectories"
    od = sys.argv[2] if len(sys.argv) > 2 else "_render"
    os.makedirs(od, exist_ok=True)
    for fn in sorted(os.listdir(td)):
        if fn.endswith(".json"):
            render(os.path.join(td, fn), os.path.join(od, fn.replace(".json", ".txt")))
