import json, sys, os

TRAJ = "trajectories"
FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667",
]
INFRA = ["django__django-13809","django__django-15280","django__django-15741","django__django-16485","sphinx-doc__sphinx-8638","sphinx-doc__sphinx-9367"]

for t in FAILING:
    fn = os.path.join(TRAJ, f"{t}__cand_0002__t0.json")
    d = json.load(open(fn))
    md = d["rollout"].get("metadata") or {}
    vs = md.get("verifier_stdout", "") or ""
    n_agent_steps = sum(1 for s in (d["rollout"]["trace"]["steps"]) if s.get("source") == "agent")
    total_steps = len(d["rollout"]["trace"]["steps"])
    fm = d["rollout"]["trace"].get("final_metrics", {})
    # summarize verifier output: count FAIL/PASSED, extract failing test names
    import re
    failed = re.findall(r"FAILED (\S+)", vs)
    errsummary = re.findall(r"^E+ .*$", vs, re.M)[:5]
    print("=" * 100)
    print(f"### {t}  steps={n_agent_steps}/{total_steps} cost={fm.get('total_cost_usd')}")
    print("verifier len:", len(vs))
    print("FAILED tests:", failed[:12])
    for e in errsummary:
        print("  E:", e[:160])
