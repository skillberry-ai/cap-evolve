import json, os, re, sys

TRAJ = "trajectories"

# ALL failing tasks from the CURRENT iteration's INSTRUCTIONS (cand_0002 rollouts)
FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667","pydata__xarray-6992","pylint-dev__pylint-4661",
    "pylint-dev__pylint-4970","pytest-dev__pytest-10356","pytest-dev__pytest-5787",
    "sympy__sympy-15599","sympy__sympy-17630","sympy__sympy-21612",
]
PASSING = [
    "django__django-12039","django__django-12276","django__django-13121","django__django-13401",
    "django__django-13410","django__django-13569","django__django-14580","django__django-15103",
    "django__django-15380","django__django-15851","django__django-15863","django__django-15930",
    "matplotlib__matplotlib-22871","matplotlib__matplotlib-24637","pydata__xarray-6461",
    "scikit-learn__scikit-learn-25232","sphinx-doc__sphinx-7910","sphinx-doc__sphinx-8035",
    "sphinx-doc__sphinx-8475","sphinx-doc__sphinx-8595","sphinx-doc__sphinx-9258","sympy__sympy-12096",
    "sympy__sympy-13480","sympy__sympy-17139","sympy__sympy-18211",
]

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

def summarize(task, show=True):
    d = load(task)
    if d is None:
        return None
    reward = (d.get("score") or {}).get("reward")
    meta = ((d.get("rollout") or {}).get("metadata")) or {}
    vs = meta.get("verifier_stdout", "") or ""
    out = ((d.get("rollout") or {}).get("output")) or {}
    steps = out.get("steps") or []

    info = dict(task=task, reward=reward, cmds=0, commit=0, pytest_rc_127=0,
                pytest_notfound_txt=0, test_pass_seen=False, test_fail_seen=False,
                apply_check_fail=0, edits_after_last_test=False, n_agent_steps=0,
                end_diff_loop=0, empty_patch=0, uncommitted_at_end=False,
                final_diff_empty=None, tail_cmds=[], edit_idx=-1, last_test_idx=-1)
    last_edit_idx = -1
    last_test_idx = -1
    cmds_all = []
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        info["n_agent_steps"] += 1
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            if not c:
                continue
            cmds_all.append(c)
            info["cmds"] += 1
            obs, rc = "", None
            if s.get("observation"):
                try:
                    j = json.loads(s["observation"]["results"][0]["content"])
                    obs = j.get("output", "") or ""
                    rc = j.get("returncode")
                except Exception:
                    pass
            low = c.lower()
            if c.startswith("git add") or "git commit" in c[:30]:
                info["commit"] += 1
                last_edit_idx = info["cmds"] - 1
            if re.search(r"\b(sed -i|python3? - <<|python3? -c|python3? <<|>> |tee |Path\().*", c) and "diff" not in c[:12]:
                if ("write_text" in c) or ("sed -i" in c) or (c.startswith("python") and "<<" in c) or (c.startswith("python3") and "<<" in c):
                    last_edit_idx = info["cmds"] - 1
            is_test = bool(re.search(r"(pytest|py\.test|runtests\.py|python -m unittest|python3 -m unittest|tox )", c))
            if is_test and not c.startswith(("grep", "cat", "sed", "ls")):
                if rc == 127:
                    info["pytest_rc_127"] += 1
                if "not found" in (obs or "").lower() or "no module named" in (obs or "").lower():
                    info["pytest_notfound_txt"] += 1
                if rc == 0 and re.search(r"(\d+ passed|OK$|^OK|Ran \d+ tests)", obs, re.M):
                    info["test_pass_seen"] = True
                    last_test_idx = info["cmds"] - 1
                if rc not in (0, None):
                    info["test_fail_seen"] = True
            if "git apply" in c and rc not in (0, None):
                info["apply_check_fail"] += 1
    # tail diff-loop
    tail = cmds_all[-8:]
    info["end_diff_loop"] = sum(1 for c in tail if "git diff" in c or "git --no-pager diff" in c or "git --no-pager show" in c)
    info["edited_after_last_test"] = last_edit_idx > last_test_idx >= 0
    info["tail_cmds"] = [c[:110] for c in cmds_all[-4:]]
    info["final_diff_empty"] = None
    if show:
        print(f"{task:42s} r={reward} steps={info['n_agent_steps']:3d} cmds={info['cmds']:3d} commits={info['commit']} "
              f"rc127={info['pytest_rc_127']} notfound={info['pytest_notfound_txt']} testOK={info['test_pass_seen']:d} "
              f"testFAIL={info['test_fail_seen']:d} taildiff={info['end_diff_loop']} edit>test={info['edited_after_last_test']:d}")
    return info

print("== FAILING ==")
for t in FAILING:
    summarize(t)
print()
print("== PASSING ==")
for t in PASSING:
    summarize(t)
