import json, os, re

TRAJ = "trajectories"
PASSING = [
    "astropy__astropy-13453","django__django-12039","django__django-12276","django__django-12708",
    "django__django-13410","django__django-13569","django__django-13809","django__django-14580",
    "django__django-15103","django__django-15380","django__django-15851","django__django-15863",
    "django__django-16485","matplotlib__matplotlib-24637","pydata__xarray-6461",
    "scikit-learn__scikit-learn-25232","sphinx-doc__sphinx-7910","sphinx-doc__sphinx-8035",
    "sphinx-doc__sphinx-8475","sphinx-doc__sphinx-8595","sphinx-doc__sphinx-9367","sympy__sympy-12096",
    "sympy__sympy-13480","sympy__sympy-24213",
]
FAILING = [
    "django__django-10554","django__django-11555","django__django-12325","django__django-13121",
    "django__django-13401","django__django-14007","django__django-14376","django__django-15629",
    "django__django-15930","django__django-16032","django__django-16667","matplotlib__matplotlib-22871",
    "pydata__xarray-6992","pylint-dev__pylint-4661","pylint-dev__pylint-4970","pytest-dev__pytest-10356",
    "pytest-dev__pytest-5787","sphinx-doc__sphinx-9258","sympy__sympy-15599","sympy__sympy-17139",
    "sympy__sympy-17630","sympy__sympy-18211","sympy__sympy-21612",
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

def cmds(task):
    d = json.load(open(os.path.join(TRAJ, f"{task}__seed__t0.json")))
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    out = []
    for s in steps:
        if s.get("source") != "agent":
            continue
        obs, rc = obs_of(s)
        for tc in (s.get("tool_calls") or []):
            out.append(((tc.get("arguments") or {}).get("command", ""), rc, obs))
    # final agent text message
    msgs = [s.get("message") for s in steps if s.get("source") == "agent" and s.get("message")]
    final = msgs[-1] if msgs else ""
    return out, final, d

print("=== PASSING-TASK SAFETY CHECKS (blast radius) ===")
no_commit, pasted_diff, stub_or_testedit, used_testbed = [], [], [], []
for t in PASSING:
    cs, final, d = cmds(t)
    committed = any("git commit" in c for c, rc, o in cs)
    if not committed:
        no_commit.append(t)
    # does the FINAL message contain a unified diff (i.e. did score depend on pasting it)?
    if re.search(r"^diff --git ", final, re.M) or final.count("\n@@ ") >= 1:
        pasted_diff.append(t)
    for c, rc, o in cs:
        if re.search(r"mkdir -p\s+\w+/\s*&&\s*cat", c) or "cat > mpmath" in c or "mkdir -p mpmath" in c:
            stub_or_testedit.append((t, "stub", c[:60]))
        if re.search(r"sed -i|Path\(", c or "") and "/tests/" in (c or "") and ".write_text" in (c or ""):
            m = re.findall(r"Path\('([^']+)'\)", c)
            if m and ("test" in m[0]):
                stub_or_testedit.append((t, "testfile-edit", m[0]))
        if "/opt/miniconda3/envs" in (c or ""):
            used_testbed.append(t)
print("passing tasks that did NOT commit:", no_commit or "NONE (all commit)")
print("passing tasks whose final message contains a pasted diff:", pasted_diff or "NONE")
print("passing tasks that created stubs or edited test files:", stub_or_testedit or "NONE")
print("passing tasks that already used the testbed env explicitly:", used_testbed or "NONE")

print()
print("=== ENV CONSTANT CHECK: /opt/miniconda3/envs/testbed in verifier output ===")
n_have, n_missing = 0, []
for f in sorted(os.listdir(TRAJ)):
    if not f.endswith(".json"):
        continue
    d = json.load(open(os.path.join(TRAJ, f)))
    vs = ((d["rollout"].get("metadata") or {}).get("verifier_stdout")) or ""
    if "/opt/miniconda3/envs/testbed" in vs or "envs/testbed" in vs:
        n_have += 1
    else:
        if len(((d["rollout"].get("trace") or {}).get("steps") or [])) > 0:
            n_missing.append(f.split("__")[0])
print(f"traces whose verifier ran under envs/testbed: {n_have}; without evidence: {n_missing}")

print()
print("=== FAILING-TASK TRIGGERS ===")
for t in FAILING:
    cs, final, d = cmds(t)
    pytest127 = sum(1 for c, rc, o in cs if "pytest" in (c or "").split()[:2] and rc == 127)
    modnotfound = sum(1 for c, rc, o in cs if isinstance(rc, int) and rc != 0 and "ModuleNotFoundError" in (o or ""))
    apply128 = sum(1 for c, rc, o in cs if "git apply" in (c or "") and rc == 128)
    tail_diffs = sum(1 for c, rc, o in cs[-6:] if "git diff" in (c or "") or "git --no-pager diff" in (c or ""))
    created_stub = any("mkdir -p mpmath" in (c or "") or "cat > mpmath" in (c or "") for c, rc, o in cs)
    print(f"{t:38s} pytest127={pytest127} modNF={modnotfound} apply128={apply128} taildiff={tail_diffs} stub={created_stub}")
