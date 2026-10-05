import json, os, sys, glob

TRAJ = "trajectories"

TASKS = sys.argv[1:] if len(sys.argv) > 1 else None

def load_all():
    out = {}
    for p in glob.glob(os.path.join(TRAJ, "*.json")):
        base = os.path.basename(p)
        task = base.split("__")[0] + "__" + base.split("__")[1]
        d = json.load(open(p))
        steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
        out[task] = (p, d, steps)
    return out

def obs_of(s):
    obs, rc = "", None
    if s.get("observation"):
        try:
            c = s["observation"]["results"][0]["content"]
            j = json.loads(c)
            obs = j.get("output", "")
            rc = j.get("returncode")
        except Exception:
            pass
    return obs, rc

def summarize(task, p, d, steps):
    n_agent = 0
    n_bash = 0
    test_runs = []       # (idx, cmd, rc, tail-of-output)
    edits = []           # idx of edit-like commands
    final_msg = ""
    last_cmds = []
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        n_agent += 1
        if s.get("message"):
            final_msg = s["message"]
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            n_bash += 1
            last_cmds.append(cmd)
            low = cmd.lower()
            is_test = any(m in cmd for m in ("pytest", "py.test", "runtests.py", "unittest", "trial", "tox"))
            if is_test:
                test_runs.append((idx, cmd[:120], rc, (obs or "")[-200:]))
            if cmd.startswith("sed -i") or cmd.startswith("python -") or "patch -p" in cmd or "git apply" in cmd:
                edits.append((idx, cmd[:80], rc))
    return dict(n_agent=n_agent, n_bash=n_bash, tests=test_runs, edits=edits,
                final_msg=final_msg[-600:], last_cmds=last_cmds[-6:], n_steps=len(steps))

if __name__ == "__main__":
    all_t = load_all()
    tasks = TASKS or sorted(all_t)
    for t in tasks:
        if t not in all_t:
            print(t, "MISSING"); continue
        p, d, s = all_t[t]
        su = summarize(t, p, d, s)
        print("=" * 90)
        print(t, "steps:", su["n_steps"], "agent_turns:", su["n_agent"], "test_runs:", len(su["tests"]), "edits:", len(su["edits"]))
        for (i, c, rc, tail) in su["tests"][:14]:
            print(f"  TEST @{i} rc={rc} :: {c}")
            if rc not in (0, None):
                print("       tail:", tail.replace("\n", " | ")[:180])
        print("  last cmds:")
        for c in su["last_cmds"]:
            print("    >", c[:140].replace("\n", " "))
