import json, sys, os, re
from collections import Counter

TRAJ = "trajectories"

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

results = {}
for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith(".json"):
        continue
    task = fn.replace("__cand_0002__t0.json", "").replace(".json", "")
    d = json.load(open(os.path.join(TRAJ, fn)))
    reward = (d.get("score") or {}).get("reward")
    tr = (d["rollout"] or {}).get("trace") or {}
    steps = tr.get("steps") or []
    agent_steps = [s for s in steps if s.get("source") == "agent"]
    stats = dict(
        n=len(agent_steps),
        pytest_notfound=0,
        pip_install=0,
        gitapply_fail=0,
        py_edit_ok=0,
        commit=0,
        import_err=0,
        compile_only=0,
        no_test_run=True,
        submit_missing=False,
    )
    cmds = []
    for s in agent_steps:
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            cmds.append(cmd)
            obs, rc = obs_of(s)
            if "pytest" in cmd.split()[:3] or cmd.startswith("pytest"):
                if rc == 127:
                    stats["pytest_notfound"] += 1
                elif rc is not None:
                    stats["no_test_run"] = False
            if "runtests.py" in cmd and rc not in (None, 127) and "Traceback" not in (obs or ""):
                stats["no_test_run"] = False
            if "runtests.py" in cmd:
                stats["no_test_run"] = False if (rc == 0) else stats["no_test_run"]
            if "pip install" in cmd or "pip3 install" in cmd or "pip -q install" in cmd or "python -m pip" in cmd:
                stats["pip_install"] += 1
            if "git apply" in cmd:
                stats["gitapply_fail"] += 1 if rc not in (0, None) else 0
            if cmd.startswith("python") and "read_text" in cmd:
                stats["py_edit_ok"] += 1
            if "git add" in cmd and "commit" in cmd:
                stats["commit"] += 1
            if "Traceback" in (obs or "") and rc not in (0, None):
                stats["import_err"] += 1
    results[task] = (reward, stats)

print(f"{'task':44s} {'rew':>5s} {'steps':>5s} {'pytnf':>5s} {'pip':>4s} {'gafail':>6s} {'edit':>4s} {'comm':>4s} {'imperr':>6s} {'notest':>6s}")
for task, (reward, st) in sorted(results.items(), key=lambda kv: (kv[1][0] or 0)):
    print(f"{task:44s} {reward!s:>5s} {st['n']:>5d} {st['pytest_notfound']:>5d} {st['pip_install']:>4d} {st['gitapply_fail']:>6d} {st['py_edit_ok']:>4d} {st['commit']:>4d} {st['import_err']:>6d} {str(st['no_test_run']):>6s}")
