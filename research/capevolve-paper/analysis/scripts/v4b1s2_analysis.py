#!/usr/bin/env python3
"""V4B1S2 descriptive analysis (amendment 12 erratum 21): hcv4 s2 (cand_0002, best of 3 by train) on the test-20.
(1) hcv4s2 minus the in-window seed (n = 20) with the CR1 CI and the paired p; (2) the cross-window comparison with the V3 B1 main-window HC-stock,
expressed as delta against each window's own seed; (3) the 5I drift check of the in-window seed. Pure standard library.
    python3 -I v4b1s2_analysis.py OUTDIR
"""
import csv, datetime as dt, json, math, os, random, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paired_cluster_bootstrap as pcb
FE = "/home/dev/projects2/campaign-scratch/final_eval"; OUT = sys.argv[1]


def load(win):
    R = [r for r in csv.DictReader(open(f"{FE}/{win}/results_long.csv")) if r["split"] == "test"]
    tasks = sorted({r["task"] for r in R}, key=lambda t: (len(t), t)); ix = {t: i for i, t in enumerate(tasks)}
    M = {}
    for r in R:
        M.setdefault(r["arm"], [None] * len(tasks))[ix[r["task"]]] = float(r["reward"])
    return M, [r["family"] for r in sorted({(r["task"], r["family"]): r for r in R}.values(), key=lambda r: ix[r["task"]])]


def d_ci(v, ref, fam):
    r = pcb.paired_cluster_bootstrap([v], [ref], fam, B=20)
    return r["theta"], r["cr_ci"], r["cr_p_two_sided"], r["cr_se"]


def signflip(v, ref, B=100000, seed=1):
    d = [a - b for a, b in zip(v, ref)]; rng = random.Random(seed); obs = abs(sum(d))
    return (1 + sum(abs(sum(x if rng.random() < .5 else -x for x in d)) >= obs - 1e-12 for _ in range(B))) / (B + 1)


def drift(win, arm="seed"):
    rows = [(dt.datetime.strptime(r["t_start"], "%Y-%m-%dT%H:%M:%SZ").timestamp(), r["task"], float(r["reward"])) for r in csv.DictReader(open(f"{FE}/{win}/results_trials.csv")) if r["arm"] == arm and r["split"] == "test" and r["reward"] != ""]
    mu = {}
    for t, k, x in rows: mu.setdefault(k, []).append(x)
    mu = {k: sum(v) / len(v) for k, v in mu.items()}
    t0 = min(r[0] for r in rows); b = {}
    for t, k, x in rows: b.setdefault(int((t - t0) // 3600), []).append(x - mu[k])
    sd = statistics.pstdev([x for v in b.values() for x in v])
    ms = [(k, sum(v) / len(v), sd / math.sqrt(len(v)), len(v)) for k, v in sorted(b.items())]
    return ms, max(m[1] for m in ms) - min(m[1] for m in ms), math.sqrt(sum(m[2] ** 2 for m in ms) / len(ms) * 2)


f = lambda x, d=3: f"{x:.{d}f}"; sg = lambda x, d=3: f"{x:+.{d}f}"
M, fam = load("V4B1S2/main"); Mm, famm = load("V3B1/main")
L = ["# V4B1S2: hcv4 s2 (cand_0002; best of 3 by train score) on test-20 (descriptive; erratum 21)", "",
     "One champion, selected by the highest search-time train score of the 3 HC-v4 seeds: the held-out score is selection-conditioned and optimistic. No pipeline-level interval, no method claim. Unblinding released by the coordinator; b1-rerun's earlier numbers (results/V4_B1_rerun/test_s2.md) were computed before this release and are compared below.", ""]
for a in ("seed", "seed-check", "hcv4s2"):
    th, ci, p, se = d_ci(M[a], [0.0] * 20, fam)
    L.append(f"- {a}: mean {f(th)} 95% CI [{f(ci[0])}, {f(ci[1])}] (CR1, 20 task clusters)")
th, ci, p, se = d_ci(M["hcv4s2"], M["seed"], fam)
sf = signflip(M["hcv4s2"], M["seed"])
L += ["", "## Headline: hcv4 s2 minus the in-window seed (n = 20 trials per task; hcv4 s2 k = 10)", "",
      f"- delta {sg(th)}, 95% CI [{f(ci[0])}, {f(ci[1])}] (CR1 t, 19 df), SE {f(se)}, paired p {p:.4f} (cluster-robust t); sign-flip p {sf:.4f}",
      ]
th2, ci2, p2, _ = d_ci(M["hcv4s2"], M["seed-check"], fam)
L.append(f"- vs the seed-check (same artifact as the seed, k = 10): {sg(th2)} [{f(ci2[0])}, {f(ci2[1])}], p {p2:.4f}")
L += ["", "Cross-check with b1-rerun's method (task-level percentile bootstrap, exact sign-flip on the per-task deltas): see the note at the end; the registered estimator is the CR1 t above.", ""]
ms, rng_, se2 = drift("V4B1S2/main")
flag = rng_ > 2 * se2
L += ["", "## Drift check (5I, in-window seed, task-demeaned, hour blocks)", "", "blocks (index, mean, SE, n): " + "; ".join(f"{k}: {sg(m)} (SE {s:.3f}, n={n})" for k, m, s, n in ms) + f". Range {rng_:.3f}, SE of difference {se2:.3f}, flag (>2 SE): {flag}.", ""]
sc = d_ci(M["seed-check"], M["seed"], fam)
L.append(f"- seed-check minus seed: {sg(sc[0])} [{f(sc[1][0])}, {f(sc[1][1])}], p {sc[2]:.3f}")
if flag:
    rows = [(dt.datetime.strptime(r["t_start"], "%Y-%m-%dT%H:%M:%SZ").timestamp(), r["arm"], r["task"], float(r["reward"])) for r in csv.DictReader(open(f"{FE}/V4B1S2/main/results_trials.csv")) if r["split"] == "test" and r["reward"] != ""]
    t0 = min(r[0] for r in rows); seedr = [r for r in rows if r[1] == "seed"]
    mu = {}
    for t, a, k, x in seedr: mu.setdefault(k, []).append(x)
    mu = {k: sum(v) / len(v) for k, v in mu.items()}; eff = {}
    for t, a, k, x in seedr: eff.setdefault(int((t - t0) // 3600), []).append(x - mu[k])
    eff = {k: sum(v) / len(v) for k, v in eff.items()}
    acc = {}
    for t, a, k, x in rows: acc.setdefault((a, k), []).append(x - eff.get(int((t - t0) // 3600), 0.0))
    tasks = sorted({r[2] for r in rows}, key=lambda t: (len(t), t))
    vec = lambda a: [sum(acc[(a, t)]) / len(acc[(a, t)]) for t in tasks]
    thb, cib, pb, _ = d_ci(vec("hcv4s2"), vec("seed"), fam)
    L.append(f"- BLOCK-ADJUSTED hcv4 s2 minus seed (5I headline when drift flags): {sg(thb)} [{f(cib[0])}, {f(cib[1])}], p {pb:.4f}")
L += ["", "## Cross-window comparison with V3 B1 HC-stock (descriptive; each as a delta against its own window's seed; never raw means)", ""]
rows2 = [("HC-v4 s2 (this window, n = 20 seed)", M["hcv4s2"], M["seed"], fam)]
hc = [Mm["hcstock_s%d" % k] if "hcstock_s%d" % k in Mm else None for k in range(3)]
ms_ = {}
import glob
Rm = list(csv.DictReader(open(f"{FE}/V3B1/main/results_long.csv")))
tasks_m = sorted({r["task"] for r in Rm if r["split"] == "test"}, key=lambda t: (len(t), t)); ixm = {t: i for i, t in enumerate(tasks_m)}
per = {}
for r in Rm:
    if r["arm"] == "hcstock":
        per.setdefault(int(r["seed"]), [None] * len(tasks_m))[ixm[r["task"]]] = float(r["reward"])
for k in range(3):
    th_, ci_, p_, _ = d_ci(per[k], Mm["seed"], famm)
    rows2.append((f"V3 HC-stock s{k} (main window)", per[k], Mm["seed"], famm))
for name, v, ref, fm in rows2:
    th_, ci_, p_, _ = d_ci(v, ref, fm)
    L.append(f"- {name}: delta vs own window's seed {sg(th_)} [{f(ci_[0])}, {f(ci_[1])}]")
avg = [sum(per[k][i] for k in range(3)) / 3 for i in range(20)]
th_, ci_, p_, _ = d_ci(avg, Mm["seed"], famm)
L.append(f"- V3 HC-stock, 3-seed average (main window): {sg(th_)} [{f(ci_[0])}, {f(ci_[1])}]")
L += ["", f"Window-shift caveat: the same artifact moved by up to 0.06 between windows (erratum 14), and this HC-v4 champion is best-of-3 by train; the comparison with the V3 HC-stock mean is not a test. The V3 seeds were not selected best-of-3. The V3 HC-stock champion of seed 2 alone was {sg(d_ci(per[2], Mm['seed'], famm)[0])} in its window."]
import itertools
d_ = [a - b for a, b in zip(M["hcv4s2"], M["seed"])]; _r = random.Random(20261019)
_b = sorted(sum(_r.choice(d_) for _ in d_) / len(d_) for _ in range(20000)); _nz = [x for x in d_ if x != 0]; _obs = abs(sum(d_))
_ex = sum(abs(sum(a * b for a, b in zip(_nz, sg_))) >= _obs - 1e-12 for sg_ in itertools.product((1, -1), repeat=len(_nz))) / 2 ** len(_nz)
L += ["", "## Note: agreement with b1-rerun (results/V4_B1_rerun/test_s2.md, computed before the release)", "",
      f"- Task-level percentile bootstrap (20,000 resamples, seed 20261019): [{f(_b[500])}, {f(_b[19500])}]; exact two-sided sign-flip on the {len(_nz)} non-zero per-task deltas: p {_ex:.4f}; tasks better/worse/tied: {sum(x>0 for x in d_)}/{sum(x<0 for x in d_)}/{sum(x==0 for x in d_)}. These equal b1-rerun's +0.080 [0.017, 0.143], p 0.031, 12/2/6 to the printed digits.",
      f"- The registered estimator (CR1 t, 19 df) gives [{f(ci[0])}, {f(ci[1])}], p {p:.3f}: the same point estimate, a lower bound 0.006 lower (the percentile bootstrap under-covers with 20 clusters, section 3) and a p of 0.026 against 0.031 (different test: t versus exact sign-flip). Both exclude 0; neither is corrected for the best-of-3 train selection. The registered CI is the one to quote; b1-rerun's file reports the bootstrap and sign-flip numbers correctly labelled, so it needs no correction beyond adding the CR1 interval."]
os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "v4b1s2.md"), "w").write("\n".join(L) + "\n"); print("\n".join(L))
