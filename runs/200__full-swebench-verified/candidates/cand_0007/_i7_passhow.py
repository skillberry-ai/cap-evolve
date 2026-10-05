import json, os

TRAJ = "trajectories"
# So even PASSING tasks almost never run tests successfully in this env!
# They pass because their FIX is correct, not because they verified it.
# The differentiator between passing and failing is whether the fix is right.
#
# Key question for our edit: what makes failing-task fixes WRONG?
# From the verifier tails we saw the actual test failures. Let's map each failing task
# to: did the agent produce a patch at all (git diff non-empty at HEAD~1..HEAD), and
# what did the verifier say?
FAILING = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
]
def obs_of(s):
    obs, rc = "", None
    if s.get("observation"):
        try:
            c = s["observation"]["results"][0]["content"]
            j = json.loads(c)
            obs = j.get("output", "") or ""
            rc = j.get("returncode")
        except Exception:
            pass
    return obs, rc

for t in FAILING:
    d = json.load(open(os.path.join(TRAJ, f"{t}__cand_0002__t0.json")))
    steps = d["rollout"]["output"]["steps"]
    commit_msg = None
    committed_files = []
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        obs, rc = obs_of(s)
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            if "git commit" in cmd:
                commit_msg = cmd[:120]
    # diff stat of last commit
    last_diff_cmd = [tc.get("arguments", {}).get("command", "") for s in steps if s.get("source") == "agent" for tc in (s.get("tool_calls") or [])]
    has_diff = any("git --no-pager diff" in c for c in last_diff_cmd)
    print(f"{t:40s} commit={'yes' if commit_msg else 'NO':3s} viewed_diff={has_diff}")
