#!/usr/bin/env python3
"""GATE6N window analysis (amendment 12 erratum 99, replacing the NONE arm of gate6_analysis.py). Written BEFORE the data exist. Exploratory.
The no-gate arm (GATE-NONE-K2) is dropped by author decision: the window has NAIVE (3 searches) and the noise-aware gate K2 (3 searches); the primary family is m = 1.

Cells (results_long.csv key = arm/s<seed>, as the order builder writes them): GATE-NAIVE-K2/s0, /s1, /s3; GATE-NONE-K2/s0, /s1, /s3;
the noise-aware gate (K2) searches GATE-K2-s0/s0, GATE-K2-s1/s0, GATE-K2-s3/s0 (paper searches 1, 2, 3); seed; seed-check. Test-20, 30 trials per cell, one session.
PRIMARY (family m = 2, Holm), each at artifact level and at pipeline level:
  NAIVE 3-search mean minus K2 3-search mean; NONE 3-search mean minus K2 3-search mean.
  Artifact level: CR1 t(19) on the task-level difference of the two 3-search means.
  Pipeline level: SE^2 = SE_task^2 + s_a^2/3 + s_b^2/3, where s_a, s_b are the sample SDs of the three searches' overall test means; interval t(2) (conservative: 3 searches
  per side, Welch df lies between 2 and 4 and is not used).
SECONDARY (raw p): NAIVE minus NONE (same two levels); each arm's 3-search mean minus the in-window seed (same two levels); the per-search table (mean, delta over seed);
  within-arm search spread (SD of the three searches' means); seed-check minus seed; 5I drift (hour blocks, >2 SE, blocks under 5% of seed trials merged).
Nothing is pooled with earlier windows. Pure standard library.   python3 -I gate6n_analysis.py OUTDIR RESULTS_ROOT
"""
import csv, datetime as dt, json, math, os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paired_cluster_bootstrap as pcb

OUT, ROOT = sys.argv[1], sys.argv[2]
GROUPS = {"NAIVE": [f"GATE-NAIVE-K2/s{s}" for s in (0, 1, 3)], "K2": [f"GATE-K2-s{s}/s0" for s in (0, 1, 3)]}
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


def contrast(A, B, fam):
    """A, B: lists of search rows (B may be a single row). Artifact level on the task-level difference of the means; pipeline level adds the search spreads."""
    r = pcb.paired_cluster_bootstrap([avg(A)], [avg(B)], fam, B=20)
    o = {"theta": r["theta"], "ci": r["cr_ci"], "p": r["cr_p_two_sided"], "pipe": None, "pipe_p": None}
    sa = statistics.stdev([mean(x) for x in A]) if len(A) > 1 else None; sb = statistics.stdev([mean(x) for x in B]) if len(B) > 1 else None
    if sa is not None or sb is not None:
        var = r["cr_se"] ** 2 + (sa ** 2 / len(A) if sa is not None else 0) + (sb ** 2 / len(B) if sb is not None else 0)
        df = max(1, min(len(A) if sa is not None else 99, len(B) if sb is not None else 99) - 1)
        se = math.sqrt(var); q = pcb.t_ppf(0.975, df); o["pipe"] = (r["theta"] - q * se, r["theta"] + q * se)
        o["pipe_p"] = 2 * (1 - pcb._t_cdf(abs(r["theta"]) / se, df)) if se > 0 else 0.0; o["df"] = df
    return o


def main():
    tasks, fam, M = load(os.path.join(ROOT, "results_long.csv"))
    need = [k for g in GROUPS.values() for k in g] + ["seed/s0", "seed-check/s0"]
    miss = [k for k in need if k not in M]
    if miss: raise SystemExit(f"cells missing from results_long.csv: {miss}; present: {sorted(M)}")
    tr = [(dt.datetime.strptime(r["t_start"], "%Y-%m-%dT%H:%M:%SZ").timestamp(), f"{r['arm']}/s{r['seed']}", r["task"], float(r["reward"]))
          for r in csv.DictReader(open(os.path.join(ROOT, "results_trials.csv"))) if r["split"] == "test" and r["reward"] != ""]
    t0 = min(x[0] for x in tr); seedt = [x for x in tr if x[1] == "seed/s0"]; mu = {}
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
    eff = {k: mean(v) for k, v in mb.items()}; acc = {}
    for t, a, k, x in tr:
        hb = int((t - t0) // 3600); acc.setdefault((a, k), []).append(x - (eff.get(bmap.get(hb, hb), 0.0) if flag else 0.0))
    Mb = {a: [mean(acc[(a, k)]) for k in tasks] for a in {a for a, _ in acc}}
    rep = json.load(open(os.path.join(ROOT, "per_arm_report.json")))
    tot_i = {x: sum(v.get(x, 0) for v in rep.values() if isinstance(v, dict)) for x in ("jobs", "done", "infra_attempts", "infra_final", "hangs", "candidate_errors", "retried_jobs", "empty_completion")}
    sel = lambda src, keys: [src[k] for k in keys]
    J = {}
    L = ["# GATE6N window (erratum 99; one fresh session, 30 trials per cell; tau2 airline test-20)", "",
         "Three searches per gate arm and three per the noise-aware gate (K2); the seed of a search is only a directory label, split_seed 42 and the 30 search tasks are identical for all of them. Nothing is pooled with earlier windows. Raw p; One primary contrast (m = 1): no multiplicity adjustment.", "",
         f"- infrastructure: {tot_i}",
         "- per-search means: " + "; ".join(f"{g}: " + ", ".join(f"{k.split('/')[0].replace('GATE-','').replace('-K2','')}{k.split('/')[-1] if g!='K2' else ''} {f(mean(M[k]))}" for k in ks) for g, ks in GROUPS.items()) + f"; seed {f(mean(M['seed/s0']))}, seed-check {f(mean(M['seed-check/s0']))}",
         "- 3-search means: " + ", ".join(f"{g} {f(mean(avg(sel(M, ks))))} (search SD {f(statistics.stdev([mean(M[k]) for k in ks]))})" for g, ks in GROUPS.items()),
         "- drift (5I, in-window seed, task-demeaned, hour blocks): " + "; ".join(f"{k}: {sg(m)} (SE {s:.3f}, n={n})" for k, m, s, n in ms) + f". Range {rng:.3f}, SE of difference {se2:.3f}, flag (>2 SE): {flag}.", ""]
    prim = [("NAIVE minus K2 (noise-aware gate)", GROUPS["NAIVE"], GROUPS["K2"])]
    res = {}
    for nm, a, b in prim:
        res[nm] = contrast(sel(M, a), sel(M, b), fam); J[nm] = res[nm]
        if flag: J[nm]["block_adjusted"] = contrast(sel(Mb, a), sel(Mb, b), fam)
    ha = pcb.holm({n: r["p"] for n, r in res.items()}); hp = pcb.holm({n: r["pipe_p"] for n, r in res.items()})
    L += ["## Primary (m = 1): 3-search mean of a gate arm minus 3-search mean of the noise-aware gate", "",
          "| contrast | delta | artifact 95% CI (CR1 t19) | raw p | Holm p | pipeline 95% CI (t2) | raw p | Holm p | " + ("block-adjusted delta [artifact CI] |" if flag else ""),
          "|---|---|---|---|---|---|---|---|" + ("---|" if flag else "")]
    for nm, a, b in prim:
        r = res[nm]; ex = ""
        if flag: bb = J[nm]["block_adjusted"]; ex = f" {sg(bb['theta'])} [{f(bb['ci'][0])}, {f(bb['ci'][1])}] |"
        L.append(f"| {nm} | {sg(r['theta'])} | [{f(r['ci'][0])}, {f(r['ci'][1])}] | {pf(r['p'])} | {pf(ha[nm])} | [{f(r['pipe'][0])}, {f(r['pipe'][1])}] | {pf(r['pipe_p'])} | {pf(hp[nm])} |{ex}")
    L += ["", "## Secondary (raw p, no family)", "", "| contrast | delta | artifact 95% CI | raw p | pipeline 95% CI (t2) | raw p |", "|---|---|---|---|---|---|"]
    sec = [("NAIVE minus seed", GROUPS["NAIVE"], ["seed/s0"]), ("K2 minus seed", GROUPS["K2"], ["seed/s0"])]
    for nm, a, b in sec:
        r = contrast(sel(M, a), sel(M, b), fam); J[nm] = r
        pp = f"[{f(r['pipe'][0])}, {f(r['pipe'][1])}] | {pf(r['pipe_p'])}" if r["pipe"] else "n/a | n/a"
        L.append(f"| {nm} | {sg(r['theta'])} | [{f(r['ci'][0])}, {f(r['ci'][1])}] | {pf(r['p'])} | {pp} |")
    sc = contrast([M["seed-check/s0"]], [M["seed/s0"]], fam); J["seed-check minus seed"] = sc
    L.append(f"| seed-check minus seed | {sg(sc['theta'])} | [{f(sc['ci'][0])}, {f(sc['ci'][1])}] | {pf(sc['p'])} | n/a | n/a |")
    L += ["", "## Per search (delta over the in-window seed, artifact level)", "", "| search | mean | delta over seed [95% CI] |", "|---|---|---|"]
    for g, ks in GROUPS.items():
        for k in ks:
            r = contrast([M[k]], [M["seed/s0"]], fam); J["search " + k] = r
            L.append(f"| {k} | {f(mean(M[k]))} | {sg(r['theta'])} [{f(r['ci'][0])}, {f(r['ci'][1])}] |")
    L += ["", "Planning note: with three searches per side the pipeline-level interval has 2 df and is wide; the registered detectable difference for two single champions is about 0.133 at 30 trials. Per-search spread (the SD above) is the quantity that limits the pipeline-level contrast."]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "gate6n.md"), "w").write("\n".join(L) + "\n"); json.dump(J, open(os.path.join(OUT, "gate6n.json"), "w"), indent=1, default=str)
    print("\n".join(L))


if __name__ == "__main__":
    main()
