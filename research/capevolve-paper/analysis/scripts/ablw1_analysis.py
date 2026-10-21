#!/usr/bin/env python3
"""ABL-W1 analysis (amendment 12 addenda 6 and 7, erratum 25, 27): 12 ablation champions + the HC-stock s0 reference + seed (n = 20) + seed-check, test-20, k = 10.
Per arm: delta over the in-window seed (artifact-level CR1 t, 19 df, raw p); task-paired difference to HC-stock-s0-ref (CR1); 5I drift check with block-adjusted deltas
when it flags; infra counts. Exploratory: raw p only, no Holm decision, one search seed per arm. Pure standard library.
    python3 -I ablw1_analysis.py OUTDIR
"""
import csv, datetime as dt, json, math, os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paired_cluster_bootstrap as pcb
FE = "/home/dev/projects2/campaign-scratch/final_eval/ABLW1/main"; OUT = sys.argv[1]
R = [r for r in csv.DictReader(open(f"{FE}/results_long.csv")) if r["split"] == "test"]
tasks = sorted({r["task"] for r in R}, key=lambda t: (len(t), t)); ix = {t: i for i, t in enumerate(tasks)}
famd = {r["task"]: r["family"] for r in R}; fam = [famd[t] for t in tasks]
M = {}
for r in R:
    M.setdefault(r["arm"], [None] * len(tasks))[ix[r["task"]]] = float(r["reward"])
f = lambda x, d=3: f"{x:.{d}f}"; sg = lambda x, d=3: f"{x:+.{d}f}"
def dlt(v, ref):
    r = pcb.paired_cluster_bootstrap([v], [ref], fam, B=20); return r["theta"], r["cr_ci"], r["cr_p_two_sided"], r["cr_se"]
def mean(v): return sum(v) / len(v)
# drift
trials = [(dt.datetime.strptime(r["t_start"], "%Y-%m-%dT%H:%M:%SZ").timestamp(), r["arm"], r["task"], float(r["reward"])) for r in csv.DictReader(open(f"{FE}/results_trials.csv")) if r["split"] == "test" and r["reward"] != ""]
t0 = min(t[0] for t in trials); seedt = [t for t in trials if t[1] == "seed"]
mu = {}
for t, a, k, x in seedt: mu.setdefault(k, []).append(x)
mu = {k: mean(v) for k, v in mu.items()}; blk = {}
for t, a, k, x in seedt: blk.setdefault(int((t - t0) // 3600), []).append(x - mu[k])
sd = statistics.pstdev([x for v in blk.values() for x in v])
ms = [(k, mean(v), sd / math.sqrt(len(v)), len(v)) for k, v in sorted(blk.items())]
rng_ = max(m[1] for m in ms) - min(m[1] for m in ms); se2 = math.sqrt(sum(m[2] ** 2 for m in ms) / len(ms) * 2); flag = rng_ > 2 * se2
eff = {k: mean(v) for k, v in blk.items()}
acc = {}
for t, a, k, x in trials: acc.setdefault((a, k), []).append(x - (eff.get(int((t - t0) // 3600), 0.0) if flag else 0.0))
vadj = lambda a: [mean(acc[(a, t)]) for t in tasks]
arms = sorted(a for a in M if a not in ("seed", "seed-check", "HC-stock-s0-ref"))
rep = json.load(open(f"{FE}/per_arm_report.json"))
tot = {x: sum(v[x] for v in rep.values()) for x in ("jobs", "done", "infra_attempts", "infra_final", "hangs", "candidate_errors", "missing_hang", "empty_output", "raw_tool_text_last")}
L = ["# ABL-W1: 12 ablation champions on the held-out test-20 (exploratory; designed after the V3 B1 results were seen)", "",
     "Task set: 20 tasks, 20 families; k = 10 trials per task per champion; seed n = 20; seed-check k = 10; HC-stock-s0-ref = the main-window HC-stock seed-0 champion re-scored in this window. One search seed per arm: no pipeline-level interval, no claim about a component's general importance; raw p only, no family claim, no Holm decision (addendum 6).", "",
     f"Infrastructure (per_arm_report.json): {tot}", "",
     "## Window checks", ""]
sc = dlt(M["seed-check"], M["seed"])
L.append(f"- seed {f(mean(M['seed']))} (n = 20), seed-check {f(mean(M['seed-check']))} (k = 10); seed-check minus seed {sg(sc[0])} [{f(sc[1][0])}, {f(sc[1][1])}], p {sc[2]:.3f}")
L.append(f"- drift (5I, in-window seed, task-demeaned, hour blocks): " + "; ".join(f"{k}: {sg(m)} (SE {s:.3f}, n={n})" for k, m, s, n in ms) + f". Range {rng_:.3f}, SE of difference {se2:.3f}, flag (>2 SE): {flag}.")
if flag: L.append("- The drift FLAGS: the BLOCK-ADJUSTED deltas (the seed's block effects subtracted from every trial) are the headline columns below; the unadjusted ones are shown beside them.")
href = M["HC-stock-s0-ref"]
hr = dlt(href, M["seed"]); hra = dlt(vadj("HC-stock-s0-ref"), vadj("seed")) if flag else None
L += [f"- HC-stock-s0-ref: mean {f(mean(href))}; delta over the in-window seed {sg(hr[0])} [{f(hr[1][0])}, {f(hr[1][1])}], p {hr[2]:.4f}" + (f"; block-adjusted {sg(hra[0])} [{f(hra[1][0])}, {f(hra[1][1])}], p {hra[2]:.4f}" if hra else "") + " (main window: +0.131 over a seed of 0.498; the same artifact, a different time block)", ""]
L += ["## Per arm", "", "| arm | mean | delta over seed | 95% CI | raw p | " + ("block-adjusted delta [CI] p | " if flag else "") + "difference to HC-stock-s0-ref | 95% CI | raw p |", "|---|---|---|---|---|" + ("---|" if flag else "") + "---|---|---|"]
rows = []
for a in arms:
    d = dlt(M[a], M["seed"]); dh = dlt(M[a], href)
    s1 = ""; 
    if flag:
        da = dlt(vadj(a), vadj("seed")); dha = dlt(vadj(a), vadj("HC-stock-s0-ref"))
        s1 = f"{sg(da[0])} [{f(da[1][0])}, {f(da[1][1])}] p {da[2]:.3f} | "
        dh = dha if flag else dh
    rows.append((a, mean(M[a]), d, dh))
    L.append(f"| {a} | {f(mean(M[a]))} | {sg(d[0])} | [{f(d[1][0])}, {f(d[1][1])}] | {d[2]:.3f} | {s1}{sg(dh[0])} | [{f(dh[1][0])}, {f(dh[1][1])}] | {dh[2]:.3f} |")
L += ["", ("The 'difference to HC-stock-s0-ref' column uses the block-adjusted scores (drift flagged)." if flag else "The 'difference to HC-stock-s0-ref' column uses the plain scores (no drift flag)."), "",
      f"Count of arms with a positive delta over the seed: {sum(1 for r in rows if r[2][0] > 0)} of {len(rows)}; with the CI excluding 0 upward: {sum(1 for r in rows if r[2][1][0] > 0)}; arms whose delta exceeds HC-stock-s0-ref's: {sum(1 for r in rows if r[3][0] > 0)}; with the difference CI excluding 0: {sum(1 for r in rows if r[3][1][0] > 0 or r[3][1][1] < 0)}."]
os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "ablw1.md"), "w").write("\n".join(L) + "\n"); print("\n".join(L))
