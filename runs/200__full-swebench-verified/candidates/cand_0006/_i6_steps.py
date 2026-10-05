import json, sys, os

TRAJ = './trajectories'

FAILING = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
]

def get_steps(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    ro = d.get("rollout") or {}
    return ((ro.get("trace") or {}).get("steps")) or []

def step_summary(s):
    src = s.get("source")
    msg = (s.get("message") or "")
    tcs = s.get("tool_calls") or []
    obs = s.get("observation")
    return src, msg, tcs, obs

for task in [sys.argv[1]]:
    steps = get_steps(task)
    print(f"TASK {task}: {len(steps)} steps")
    for i, s in enumerate(steps):
        src, msg, tcs, obs = step_summary(s)
        if src == "system":
            print(f"[{i}] SYSTEM: {msg[:150]!r}")
        elif src == "agent":
            for tc in tcs:
                args = tc.get("arguments") or {}
                cmd = args.get("command") or json.dumps(args)[:200]
                print(f"[{i}] AGENT TOOL: {cmd[:300]!r}")
            if msg.strip():
                print(f"[{i}] AGENT MSG: {msg[:400]!r}")
        elif src == "user":
            print(f"[{i}] USER: {msg[:200]!r}")
        else:
            # observation?
            if obs:
                try:
                    c = obs.get("results")[0].get("content")
                    j = json.loads(c)
                    out = j.get("output", "")
                    rc = j.get("returncode")
                    print(f"[{i}] OBS rc={rc}: {out[:300]!r}")
                except Exception as e:
                    print(f"[{i}] OBSRAW: {str(obs)[:300]!r}")
            else:
                print(f"[{i}] {src}: {str(s)[:200]!r}")
