import json, os

TRAJ = "trajectories"
TASKS = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667", "pydata__xarray-6461", "pydata__xarray-6992",
    "pylint-dev__pylint-4661", "pylint-dev__pylint-4970",
    "pytest-dev__pytest-10356", "pytest-dev__pytest-5787",
    "sympy__sympy-15599", "sympy__sympy-17630", "sympy__sympy-21612",
    "sympy__sympy-24213",
]
for t in TASKS:
    p = os.path.join(TRAJ, f"{t}__cand_0002__t0.json")
    d = json.load(open(p))
    vs = d["rollout"]["metadata"].get("verifier_stdout", "") or ""
    print("=" * 90)
    print("##", t, " (verifier_stdout len", len(vs), ")")
    lines = vs.splitlines()
    for i, ln in enumerate(lines):
        low = ln.lower()
        if any(m in low for m in ("runtests", "pytest", "python ", "test.sh", "tox", "runtest", "git checkout", "git apply", "import ", "conda", "cd ", "export ")):
            if len(ln.strip()) > 3:
                print(f"  [{i:4d}] {ln[:230]}")
