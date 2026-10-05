import json, os

TRAJ = './trajectories'

def get_steps(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    ro = d.get("rollout") or {}
    return ((ro.get("trace") or {}).get("steps")) or []

def parse_obs(s):
    obs = s.get("observation")
    if not obs:
        return None
    try:
        c = obs.get("results")[0].get("content")
        j = json.loads(c)
        return j
    except Exception:
        return None

def analyze(task):
    steps = get_steps(task)
    events = []
    saw_django_test = False
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command") or ""
            j = parse_obs(s)
            rc = (j or {}).get("returncode")
            out = (j or {}).get("output") or (j or {}).get("output_head") or ""
            tail = out.strip().splitlines()[-1] if out.strip() else ""
            events.append((i, cmd, rc, tail[:150]))

    # key signals
    has_git_apply_fail = any(("git apply" in c) and rc not in (0, None) for _, c, rc, _ in events)
    has_pytest_127 = any(("pytest" in c.split(" ")[0] if c.split(" ") else False) and rc == 127 for _, c, rc, _ in events)
    n_test_cmds = sum(1 for _, c, rc, _ in events if any(m in c for m in ("pytest", "runtests.py", "python -m unittest", "python -m pytest")))
    last_test_idx = max((i for i, c, rc, _ in events if any(m in c for m in ("pytest", "runtests.py", "python -m unittest", "python -m pytest"))), default=-1)
    n_edit_after_test = sum(1 for i, c, rc, _ in events if i > last_test_idx and any(m in c for m in ("sed -i", "python - <<", "python3 - <<", "git apply")))
    bak_files = sum(1 for _, c, rc, _ in events if ".bak" in c)
    print(f"### {task}")
    print(f"  git_apply_fail={has_git_apply_fail} pytest_127={has_pytest_127} n_test_cmds={n_test_cmds} last_test_idx={last_test_idx} edits_after_last_test={n_edit_after_test} bak_refs={bak_files}")
    for i, c, rc, tail in events:
        if any(m in c for m in ("pytest", "runtests.py", "python -m unittest", "python -m pytest", "pip install")):
            print(f"    [{i}] rc={rc} {c[:110]!r} -> {tail!r}")

for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith(".json"):
        continue
    task = fn.replace("__cand_0002__t0.json", "")
    try:
        analyze(task)
    except Exception as e:
        print(f"### {task} ERROR {e}")
