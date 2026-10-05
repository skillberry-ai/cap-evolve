import json, os, glob, re

TRAJ = "trajectories"

# The 20 ALWAYS-failing tasks this iteration
FAILING = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
]
PASSING = [
    "django__django-12039", "django__django-12276", "django__django-13121",
    "django__django-13401", "django__django-13410", "django__django-13569",
    "django__django-14580", "django__django-15103", "django__django-15380",
    "django__django-15851", "django__django-15863", "django__django-15930",
    "matplotlib__matplotlib-22871", "matplotlib__matplotlib-24637",
    "scikit-learn__scikit-learn-25232", "sphinx-doc__sphinx-7910",
    "sphinx-doc__sphinx-8035", "sphinx-doc__sphinx-8475", "sphinx-doc__sphinx-8595",
    "sphinx-doc__sphinx-9258", "sympy__sympy-12096", "sympy__sympy-13480",
    "sympy__sympy-17139", "sympy__sympy-18211",
]

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

def analyze(task):
    p = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(p))
    steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
    info = dict(task=task, n_steps=len(steps), commits=0, nocommit=False,
                final_state="?", edited_files=[], has_runtests=False,
                test_verified=False, test_fail_seen=False, timeout_tail=False)
    last_diff_idx = None
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            if cmd.startswith("git add") or (cmd.startswith("git commit")):
                info["commits"] += 1
            if "runtests.py" in cmd:
                info["has_runtests"] = True
            if cmd.startswith("git --no-pager diff") or cmd.startswith("git diff"):
                last_diff_idx = idx
    # what is the very last meaningful command?
    last_cmds = []
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            last_cmds.append((tc.get("arguments") or {}).get("command", ""))
    info["last5"] = [c[:100] for c in last_cmds[-5:]]
    # final message (submission text)
    final_msg = ""
    for s in reversed(steps):
        if s.get("source") == "agent" and s.get("message"):
            final_msg = s["message"]
            break
    info["final_msg_len"] = len(final_msg)
    info["final_msg_head"] = final_msg[:300]
    return info

print("########## FAILING ##########")
for t in FAILING:
    i = analyze(t)
    print("-" * 80)
    print(t, "| steps:", i["n_steps"], "| commits:", i["commits"], "| runtests:", i["has_runtests"], "| final_msg_len:", i["final_msg_len"])
    print("  last5:")
    for c in i["last5"]:
        print("   >", c)
    print("  final_msg:", i["final_msg_head"].replace("\n", " | ")[:250])
