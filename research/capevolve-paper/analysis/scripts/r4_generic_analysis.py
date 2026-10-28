#!/usr/bin/env python3
"""R4 generic window analysis (amendment 12 addendum 23). Written BEFORE any R4 data exist. Exploratory.

One fresh session, tau2 airline test-20 (or another model for E4), every cell at the same trial count. Cells in results_long.csv are keyed arm/s<seed>.
A DESIGN.json, registered BEFORE the order is built, fixes everything the data could otherwise suggest:
  {"name": ..., "seed": "seed/s0", "seed_check": "seed-check/s0",
   "groups": {"A": ["cell", ...], "B": [...]},               # a group is a set of searches (or one artifact)
   "primary": [["A","B"], ...], "primary_holm": true|false,  # Holm over the listed primaries, separately at artifact and pipeline level, if true
   "secondary": [["A","seed"], ...], "sensitivity": [["A","B2"], ...],
   "chains": [["child_cell","parent_cell"], ...]}            # optional: single-artifact step deltas (E6)
Contrast A minus B (a group name or the seed): artifact level = CR1 t(19) on the task-level difference of the group means (describes THESE artifacts);
pipeline level = SE^2 = SE_task^2 + s_A^2/n_A + s_B^2/n_B, s = SD of the searches' overall test means, interval t(df) with df = min(n_A, n_B) - 1 over the groups that have
at least two searches (conservative: Welch df lies between that and n_A + n_B - 2). A group of one artifact has no pipeline term.
Chains: for each (child, parent) the single-artifact difference, CR1 t(19); the summary reports the mean, the count of positive and negative steps and an exact
binomial interval for the share positive; individual steps are NOT classified (a step's SE is about 0.04 at 10 trials).
Checks: seed-check minus seed; 5I drift (hour blocks, >2 SE; blocks under 5% of the seed trials merged). Pure standard library.
    python3 -I r4_generic_analysis.py OUTDIR RESULTS_ROOT DESIGN.json
"""
import csv, datetime as dt, json, math, os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paired_cluster_bootstrap as pcb

OUT, ROOT, DESIGN = sys.argv[1:4]
D = json.load(open(DESIGN))
f = lambda x, d=3: f"{x:.{d}f}"; sg = lambda x, d=3: f"{x:+.{d}f}"
pf = lambda p: "<0.001" if p < 0.001 else f"{p:.3f}"
mean = lambda v: sum(v) / len(v)


def load(path):
    R = [r for r in csv.DictReader(open(path)) if r["split"] == "test"]
    tasks = sorted({r["task"] for r in R}, key=lambda t: (len(t), t)); ix = {t: i for i, t in enumerate(tasks)}
    fam = {r["task"]: r["family"] for r in R}; M = {}
    for r in R: M.setdefault(f"{r['arm']}/s{r['seed']}", [None] * len(tasks))[ix[r["task"]]] = float(r["reward"])
    return tasks, [fam[t] for t in tasks], M


def avg(vs): return [sum(v[i] for v in vs) / len(vs) for i in range(len(vs[0]))]


def binom_ci(k, n):
    """Clopper-Pearson 95% interval for k of n, by bisection on the exact binomial tail."""
    def cdf(x, p): return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, x + 1))
    lo = 0.0 if k == 0 else None; hi = 1.0 if k == n else None
    if lo is None:
        a, b = 0.0, 1.0
        for _ in range(60):
            m = (a + b) / 2
            if 1 - cdf(k - 1, m) > 0.025: b = m
            else: a = m
        lo = (a + b) / 2
    if hi is None:
        a, b = 0.0, 1.0
        for _ in range(60):
            m = (a + b) / 2
            if cdf(k, m) < 0.025: b = m
            else: a = m
        hi = (a + b) / 2
    return lo, hi


def main():
    tasks, fam, M = load(os.path.join(ROOT, "results_long.csv"))
    G = dict(D["groups"]); G.setdefault("seed", [D["seed"]])
    need = sorted({c for g in G.values() for c in g} | {D["seed_check"]} | {c for p in D.get("chains", []) for c in p})
    miss = [c for c in need if c not in M]
    if miss: raise SystemExit(f"cells missing from results_long.csv: {miss}; present: {sorted(M)}")
    tr = [(dt.datetime.strptime(r["t_start"], "%Y-%m-%dT%H:%M:%SZ").timestamp(), f"{r['arm']}/s{r['seed']}", r["task"], float(r["reward"]))
          for r in csv.DictReader(open(os.path.join(ROOT, "results_trials.csv"))) if r["split"] == "test" and r["reward"] != ""]
    t0 = min(x[0] for x in tr); seedt = [x for x in tr if x[1] == D["seed"]]; mu = {}
    for _, _, k, x in seedt: mu.setdefault(k, []).append(x)
    mu = {k: mean(v) for k, v in mu.items()}; blk = {}
    for t, _, k, x in seedt: blk.setdefault(int((t - t0) // 3600), []).append(x - mu[k])
    keys = sorted(blk); tot = sum(len(v) for v in blk.values()); bmap = {k: k for k in keys}; changed = True
    while changed and len(set(bmap.values())) > 1:
        changed = False; grp = {}
        for k in keys: grp.setdefault(bmap[k], []).append(k)
        order = sorted(grp)
        for i, g in enumerate(order):
            if sum(len(blk[k]) for k in grp[g]) < 0.05 * tot:
                tgt = order[i + 1] if i + 1 < len(order) else order[i - 1]
                for k in grp[g]: bmap[k] = tgt
                changed = True; break
    mb = {}
    for k in keys: mb.setdefault(bmap[k], []).extend(blk[k])
    sd = statistics.pstdev([x for v in mb.values() for x in v]); ms = [(k, mean(v), sd / math.sqrt(len(v)), len(v)) for k, v in sorted(mb.items())]
    rng = max(m[1] for m in ms) - min(m[1] for m in ms); se2 = math.sqrt(sum(m[2] ** 2 for m in ms) / len(ms) * 2); flag = len(ms) > 1 and rng > 2 * se2
    rep = json.load(open(os.path.join(ROOT, "per_arm_report.json")))
    tot_i = {x: sum(v.get(x, 0) for v in rep.values() if isinstance(v, dict)) for x in ("jobs", "done", "infra_attempts", "infra_final", "hangs", "candidate_errors", "retried_jobs", "empty_completion")}
    sel = lambda g: [M[c] for c in G[g]]

    def contrast(a, b):
        A, B = sel(a), sel(b)
        r = pcb.paired_cluster_bootstrap([avg(A)], [avg(B)], fam, B=20)
        o = {"theta": r["theta"], "ci": r["cr_ci"], "p": r["cr_p_two_sided"], "pipe": None, "pipe_p": None}
        sa = statistics.stdev([mean(x) for x in A]) if len(A) > 1 else None; sb = statistics.stdev([mean(x) for x in B]) if len(B) > 1 else None
        if sa is not None or sb is not None:
            var = r["cr_se"] ** 2 + (sa ** 2 / len(A) if sa is not None else 0) + (sb ** 2 / len(B) if sb is not None else 0)
            dfs = [len(x) - 1 for x, s in ((A, sa), (B, sb)) if s is not None]; df = max(1, min(dfs)); se = math.sqrt(var); q = pcb.t_ppf(0.975, df)
            o["pipe"] = (r["theta"] - q * se, r["theta"] + q * se); o["pipe_p"] = 2 * (1 - pcb._t_cdf(abs(r["theta"]) / se, df)) if se > 0 else 0.0; o["df"] = df
        return o
    J = {}
    L = [f"# R4 window {D['name']} (addendum 23; exploratory; one fresh session)", "",
         "Contrasts compare GROUPS of searches; the artifact-level interval describes these artifacts, the pipeline-level interval (t with min(n)-1 df) is the statement about the search procedure and is wide. Nothing is pooled with earlier windows. Raw p unless a Holm column is shown.", "",
         f"- infrastructure: {tot_i}",
         "- cell means: " + ", ".join(f"{c} {f(mean(M[c]))}" for c in need),
         "- group means: " + ", ".join(f"{g} {f(mean(avg(sel(g))))}" + (f" (search SD {f(statistics.stdev([mean(M[c]) for c in G[g]]))}, n={len(G[g])})" if len(G[g]) > 1 else "") for g in G),
         "- drift (5I, in-window seed, task-demeaned, hour blocks): " + "; ".join(f"{k}: {sg(m)} (SE {s:.3f}, n={n})" for k, m, s, n in ms) + f". Range {rng:.3f}, SE of difference {se2:.3f}, flag (>2 SE): {flag}." + ("" if len(ms) > 1 else " (one block: not assessable)"), ""]
    prim = [tuple(p) for p in D.get("primary", [])]; res = {f"{a} minus {b}": contrast(a, b) for a, b in prim}
    ha = pcb.holm({n: r["p"] for n, r in res.items()}) if D.get("primary_holm") and len(res) > 1 else {n: r["p"] for n, r in res.items()}
    hp = pcb.holm({n: (r["pipe_p"] if r["pipe_p"] is not None else 1.0) for n, r in res.items()}) if D.get("primary_holm") and len(res) > 1 else {n: (r["pipe_p"] if r["pipe_p"] is not None else 1.0) for n, r in res.items()}
    def table(title, rows, holm=None):
        L.extend(["## " + title, "", "| contrast | delta | artifact 95% CI (CR1 t19) | raw p | " + ("Holm p | " if holm else "") + "pipeline 95% CI | raw p | " + ("Holm p |" if holm else ""),
                  "|---|---|---|---|" + ("---|" if holm else "") + "---|---|" + ("---|" if holm else "")])
        for n, r in rows:
            J[n] = r; pp = f"[{f(r['pipe'][0])}, {f(r['pipe'][1])}] | {pf(r['pipe_p'])}" if r["pipe"] else "n/a | n/a"
            L.append(f"| {n} | {sg(r['theta'])} | [{f(r['ci'][0])}, {f(r['ci'][1])}] | {pf(r['p'])} | " + (f"{pf(holm[0][n])} | " if holm else "") + pp + (f" | {pf(holm[1][n])} |" if holm else " |"))
        L.append("")
    if prim: table("Primary" + (" (Holm over the listed primaries)" if D.get("primary_holm") and len(res) > 1 else " (each its own family, m = 1)"), list(res.items()), (ha, hp) if D.get("primary_holm") and len(res) > 1 else None)
    for key, title in (("secondary", "Secondary (raw p)"), ("sensitivity", "Sensitivity (raw p)")):
        rows = [(f"{a} minus {b}", contrast(a, b)) for a, b in D.get(key, [])]
        if rows: table(title, rows)
    sc = pcb.paired_cluster_bootstrap([M[D["seed_check"]]], [M[D["seed"]]], fam, B=20); J["seed-check minus seed"] = {"theta": sc["theta"], "ci": sc["cr_ci"], "p": sc["cr_p_two_sided"]}
    L += [f"Seed-check minus seed: {sg(sc['theta'])} [{f(sc['cr_ci'][0])}, {f(sc['cr_ci'][1])}], p {pf(sc['cr_p_two_sided'])}.", ""]
    if D.get("chains"):
        L += ["## Step deltas along the search chains (single artifact against its parent; exploratory; individual steps are not classified)", "", "| child | parent | child mean | parent mean | delta [95% CI, CR1 t19] | raw p |", "|---|---|---|---|---|---|"]
        ds = []
        for c, p in D["chains"]:
            r = pcb.paired_cluster_bootstrap([M[c]], [M[p]], fam, B=20); ds.append(r["theta"]); J[f"chain {c} minus {p}"] = {"theta": r["theta"], "ci": r["cr_ci"], "p": r["cr_p_two_sided"]}
            L.append(f"| {c} | {p} | {f(mean(M[c]))} | {f(mean(M[p]))} | {sg(r['theta'])} [{f(r['cr_ci'][0])}, {f(r['cr_ci'][1])}] | {pf(r['cr_p_two_sided'])} |")
        k = sum(1 for d in ds if d > 0); n = len(ds); lo, hi = binom_ci(k, n)
        L += ["", f"{n} steps: mean delta {sg(mean(ds))}, positive {k}, non-positive {n - k}; share positive {f(k / n, 2)} (exact 95% interval [{f(lo, 2)}, {f(hi, 2)}]). With no true effect about half of the steps are expected to be positive by trial noise alone."]
        J["chain summary"] = {"n": n, "mean": mean(ds), "positive": k, "binom_ci": [lo, hi]}
    L += ["", "Planning detectability (80% power, tau 0.15, within-variance 0.1236, tau_int 0.10, 20 tasks, 30 trials): about 0.133 between two single artifacts; for 3 searches against 3 the artifact-level figure is about 0.07 to 0.09 and the pipeline-level (t2) figure is above 0.25. Differences below these are inconclusive."]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "r4.md"), "w").write("\n".join(L) + "\n"); json.dump(J, open(os.path.join(OUT, "r4.json"), "w"), indent=1, default=str)
    print("\n".join(L))


if __name__ == "__main__":
    main()
