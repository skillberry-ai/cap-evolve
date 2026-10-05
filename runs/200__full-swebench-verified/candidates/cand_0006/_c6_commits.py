import json, glob, os, re

# What did the agent's final message contain? And what patch state?
# The key question: how does the harness compute the model patch from the agent's session?
# The agent COMMITS its changes (git add -A && git commit). If the model patch is
# computed as `git diff` (unstaged vs HEAD), a commit makes it EMPTY.
# But cand_0002 was ACCEPTED with 24 passing tasks, and the traces show the SAME
# commit behavior on passing tasks. So how do passing tasks work?

# Let's check: which passing tasks also committed? And is there anything in the
# rollout metadata about how the patch was extracted?

import json

tasks = {
    "PASSING": [
        "django__django-12039", "django__django-12276", "django__django-13121",
        "django__django-13401", "django__django-13410", "django__django-13569",
        "django__django-14580", "django__django-15103", "django__django-15380",
        "django__django-15851", "django__django-15863", "django__django-15930",
        "matplotlib__matplotlib-22871", "matplotlib__matplotlib-24637",
        "scikit-learn__scikit-learn-25232", "sphinx-doc__sphinx-7910",
        "sphinx-doc__sphinx-8035", "sphinx-doc__sphinx-8475", "sphinx-doc__sphinx-8595",
        "sphinx-doc__sphinx-9258", "sympy__sympy-12096", "sympy__sympy-13480",
        "sympy__sympy-17139", "sympy__sympy-18211",
    ],
    "FAILING": [
        "astropy__astropy-13453", "django__django-10554", "django__django-11555",
        "django__django-12325", "django__django-12708", "django__django-14007",
        "django__django-14376", "django__django-15629", "django__django-16032",
        "django__django-16667",
    ],
}

def analyze(task):
    d = json.load(open(f"trajectories/{task}__cand_0002__t0.json"))
    steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
    n_commit = 0
    n_gitadd = 0
    last_cmd = None
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command") or ""
            if "git commit" in cmd:
                n_commit += 1
            if "git add" in cmd:
                n_gitadd += 1
            last_cmd = cmd
    return n_commit, n_gitadd, (last_cmd or "")[:80]

for cls, lst in tasks.items():
    print(f"\n===== {cls} =====")
    for t in lst:
        nc, na, lc = analyze(t)
        print(f"{t:45s} commits={nc} git_add={na} last={lc!r}")
