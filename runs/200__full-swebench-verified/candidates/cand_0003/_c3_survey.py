import json, os, re, sys

TRAJ = "trajectories"

# Failing tasks per INSTRUCTIONS (reward 0.00) + partial/other val tasks
FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667","pydata__xarray-6992","pylint-dev__pylint-4661",
    "pylint-dev__pylint-4970","pytest-dev__pytest-10356","pytest-dev__pytest-5787",
    "sphinx-doc__sphinx-9258","sympy__sympy-15599","sympy__sympy-17630","sympy__sympy-21612",
]
# NOTE: sympy-17139, sympy-18211, matplotlib-22871, django-13121/13401/15930 now PASS in cand_0002.

def load(task):
    fn = None
    for f in os.listdir(TRAJ):
        if f.startswith(task + "__"):
            fn = f
            break
    if not fn:
        return None
    d = json.load(open(os.path.join(TRAJ, fn)))
    return d

def analyze(task):
    d = load(task)
    if d is None:
        print(task, "NO TRAJECTORY")
        return
    reward = (d.get("score") or {}).get("reward")
    meta = ((d.get("rollout") or {}).get("metadata")) or {}
    vs = meta.get("verifier_stdout", "") or ""
    out = ((d.get("rollout") or {}).get("output")) or {}
    steps = out.get("steps") or []
    n_steps = len([s for s in steps if s.get("source") == "agent"])

    # Verifier markers
    has_apply = "git apply" in vs
    m = re.search(r"SWEBench results starts here(.*?)SWEBench results ends here", vs, re.S)
    verdict = (m.group(1).strip()[:300] if m else "NO-VERDICT-SECTION")
    # test outcome lines
    head = vs[:vs.find("SWEBench results starts here")] if "SWEBench results starts here" in vs else vs
    lines = head.splitlines()
    errlines = [l for l in lines if l.startswith("ERROR:") or l.startswith("FAIL:") or l.startswith("FAILED ")]
    ran = [l for l in lines if re.match(r"^Ran \d+ tests", l) or l.startswith("FAILED (") or l == "OK" or "passed" in l.lower() and "failed" not in l.lower() and l.strip().startswith(("PASSED", "OK"))]
    # Was there an empty model patch? The verifier output often prints 'Your patch is empty' or similar
    empty_patch = ("empty" in vs.lower() and "patch" in vs.lower())
    print("=" * 100)
    print(f"{task}  reward={reward}  agent_steps={n_steps}")
    print(f"  verdict: {verdict[:200]}")
    print(f"  git_apply_in_verifier={has_apply}  empty_patch_mention={empty_patch}")
    if errlines:
        print(f"  first errors: {errlines[:5]}")
    # last few agent commands
    cmds = []
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            if c:
                cmds.append(c)
    print(f"  total commands: {len(cmds)}")
    print(f"  LAST 6 COMMANDS:")
    for c in cmds[-6:]:
        print(f"    $ {c[:150]}")

for t in FAILING:
    analyze(t)
