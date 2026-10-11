"""Paired task-cluster bootstrap with search seeds as a separate level (pure standard library).

Data model: for each arm, a matrix Y[s][t] of task-level mean rewards (mean over execution trials) for search
seed s (an independent run of the optimizer; use one row for an un-optimized baseline) and task t. None/NaN =
missing cell (kept out of numerator AND denominator; the missingness policy in protocol/analysis_plan.md
section 6 must be applied BEFORE this step). `cluster[t]` is the task family / cluster id.

Scopes (analysis_plan.md section 2):
  level="task"       : the S optimized artifacts are held fixed; only TASK sampling uncertainty (whole clusters
                       resampled, jointly for every arm and seed). Answers: how well do we know the advantage
                       of THESE champions on the task population?
  level="task+seed"  : seeds are resampled too, as an independent crossed factor (Owen's "pigeonhole"
                       bootstrap; slightly conservative because the seed x task interaction is counted twice).
                       With S < ~8 seeds the percentile interval is unreliable; use `seed_t_ci` (t interval over
                       per-seed paired means, df = S-1) as the pipeline-level headline and report the bootstrap
                       as the task-uncertainty companion.

Few clusters: the percentile bootstrap under-covers when the number of clusters C is small (selftest: ~0.86 at
C=12). Headline intervals therefore use the cluster-robust t interval (`cr_ci`, CR1 linearisation, df = C-1) when
C < 30; the bootstrap is reported as a check and for non-linear statistics.

Vocabulary (never mix): SD = spread of individual units (tasks or seeds); SE = SD of the estimator (bootstrap SD
here); CI = percentile interval of the bootstrap distribution of the estimator.

    python -I paired_cluster_bootstrap.py --selftest
    python -I paired_cluster_bootstrap.py --long results.csv --arm-a opt --arm-b base \
        [--cluster-col family] [--level task+seed] [--B 10000] [--out out.json]
CSV columns: arm, seed, task, reward [, family]   (reward = task-level mean; one row per arm/seed/task)
"""
from __future__ import annotations

import argparse
import csv
import functools
import json
import math
import random
import sys

# two-sided 97.5% Student-t quantiles by df (df>=30 -> 1.96)
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        12: 2.179, 15: 2.131, 20: 2.086, 30: 2.042}


def t975(df):
    if df < 1:
        return float("nan")
    for k in sorted(T975):
        if df <= k:
            return T975[k]
    return 1.96


def _t_cdf(x, df):
    """Student t CDF by Simpson integration (df >= 1)."""
    c = math.exp(math.lgamma((df + 1) / 2) - math.lgamma(df / 2)) / math.sqrt(df * math.pi)
    n = 600
    h = abs(x) / n
    f = lambda u: c * (1 + u * u / df) ** (-(df + 1) / 2)  # noqa: E731
    s = f(0) + f(abs(x)) + sum((4 if i % 2 else 2) * f(i * h) for i in range(1, n))
    return 0.5 + math.copysign(s * h / 3, x)


@functools.lru_cache(maxsize=256)
def t_ppf(p, df):
    lo, hi = 0.0, 500.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if _t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _nan(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def _as_matrix(Y):
    if Y and not isinstance(Y[0], (list, tuple)):
        Y = [Y]
    return [list(r) for r in Y]


def _align(Ya, Yb):
    Ya, Yb = _as_matrix(Ya), _as_matrix(Yb)
    if len(Yb) == 1 and len(Ya) > 1:
        Yb = [Yb[0] for _ in Ya]              # un-optimized baseline: one row broadcast over A's seeds
    if len(Ya) != len(Yb) or any(len(a) != len(b) for a, b in zip(Ya, Yb)):
        raise ValueError("arm matrices must align (seed x task)")
    return Ya, Yb


def _clusters(cluster, T):
    if cluster is None:
        return list(range(T)), T
    ids = {}
    cid = [ids.setdefault(c, len(ids)) for c in cluster]
    return cid, len(ids)


def _cell_sums(Ya, Yb, cid, C):
    S = len(Ya)
    sums = [[0.0] * C for _ in range(S)]
    cnt = [[0] * C for _ in range(S)]
    for s in range(S):
        for t, (a, b) in enumerate(zip(Ya[s], Yb[s])):
            if _nan(a) or _nan(b):
                continue
            sums[s][cid[t]] += a - b
            cnt[s][cid[t]] += 1
    return sums, cnt


def paired_cluster_bootstrap(Ya, Yb, cluster=None, *, level="task", B=10000, ci=0.95, seed=0):
    """Ya: S x T (or T), Yb: S' x T (S'==1 broadcasts). Returns theta, bootstrap SE, percentile CI, p-value, etc."""
    Ya, Yb = _align(Ya, Yb)
    S, T = len(Ya), len(Ya[0])
    cid, C = _clusters(cluster, T)
    sums, cnt = _cell_sums(Ya, Yb, cid, C)
    tot_n = sum(map(sum, cnt))
    if tot_n == 0:
        raise ValueError("no valid paired cells")
    theta = sum(map(sum, sums)) / tot_n
    per_seed = [sum(sums[s]) / max(sum(cnt[s]), 1) for s in range(S)]
    rng = random.Random(seed)
    col_sum = [sum(sums[s][c] for s in range(S)) for c in range(C)]
    col_cnt = [sum(cnt[s][c] for s in range(S)) for c in range(C)]
    boot = []
    for _ in range(B):
        wc = [0] * C
        for _ in range(C):
            wc[rng.randrange(C)] += 1                      # cluster multiplicities
        if level == "task":
            num = sum(w * x for w, x in zip(wc, col_sum)); den = sum(w * x for w, x in zip(wc, col_cnt))
        elif level == "task+seed":
            ws = [0] * S
            for _ in range(S):
                ws[rng.randrange(S)] += 1
            num = den = 0
            for s in range(S):
                if ws[s]:
                    num += ws[s] * sum(w * x for w, x in zip(wc, sums[s])); den += ws[s] * sum(w * x for w, x in zip(wc, cnt[s]))
        else:
            raise ValueError("level must be 'task' or 'task+seed'")
        if den > 0:
            boot.append(num / den)
    boot.sort()
    nb = len(boot)
    a = (1 - ci) / 2
    lo, hi = boot[int(a * nb)], boot[min(nb - 1, int((1 - a) * nb))]
    m = sum(boot) / nb
    se = math.sqrt(sum((x - m) ** 2 for x in boot) / (nb - 1))
    le, ge = sum(x <= 0 for x in boot), sum(x >= 0 for x in boot)
    p_two = min(1.0, (1 + 2 * min(le, ge)) / (nb + 1))
    seed_ci = seed_sd = None
    if S >= 2:
        mu = sum(per_seed) / S
        seed_sd = math.sqrt(sum((x - mu) ** 2 for x in per_seed) / (S - 1))
        h = t975(S - 1) * seed_sd / math.sqrt(S)
        seed_ci = (mu - h, mu + h)
    # cluster-robust (CR1) linearised SE with a t(C-1) reference: the recommended interval when C < ~30
    res_c = [col_sum[c] - theta * col_cnt[c] for c in range(C)]
    cr_var = (C / (C - 1)) * sum(e * e for e in res_c) / tot_n ** 2 if C > 1 else float("nan")
    cr_se = math.sqrt(cr_var) if C > 1 else float("nan")
    cr_ci = cr_p = None
    if C > 1:
        q = t_ppf(1 - (1 - ci) / 2, C - 1)
        cr_ci = (theta - q * cr_se, theta + q * cr_se)
        cr_p = 2 * (1 - _t_cdf(abs(theta) / cr_se, C - 1)) if cr_se > 0 else 0.0
    task_means = [(sum(sums[s][c] for s in range(S)), sum(cnt[s][c] for s in range(S))) for c in range(C)]
    cm = [x / n for x, n in task_means if n]
    mcm = sum(cm) / len(cm)
    cl_sd = math.sqrt(sum((x - mcm) ** 2 for x in cm) / (len(cm) - 1)) if len(cm) > 1 else float("nan")
    return {"theta": theta, "se": se, "ci": (lo, hi), "p_two_sided": p_two, "per_seed": per_seed, "seed_sd": seed_sd,
            "seed_t_ci": seed_ci, "cr_se": cr_se, "cr_ci": cr_ci, "cr_p_two_sided": cr_p, "cluster_sd_of_delta": cl_sd, "n_tasks": T, "n_clusters": C, "n_seeds": S,
            "level": level, "B": nb}


def signflip_pvalue(Ya, Yb, cluster=None, *, B=20000, seed=0):
    """Cluster-level sign-flip randomization test of H0: E[cluster delta] = 0."""
    Ya, Yb = _align(Ya, Yb)
    T = len(Ya[0])
    cid, C = _clusters(cluster, T)
    sums, cnt = _cell_sums(Ya, Yb, cid, C)
    cs = [sum(sums[s][c] for s in range(len(Ya))) for c in range(C)]
    n = sum(map(sum, cnt))
    obs = abs(sum(cs)) / n
    rng = random.Random(seed)
    ge = 0
    for _ in range(B):
        ge += abs(sum(x if rng.random() < 0.5 else -x for x in cs)) / n >= obs - 1e-12
    return (1 + ge) / (B + 1)


def holm(pvals):
    """Holm step-down adjusted p-values (FWER control); dict or list in, same shape out."""
    items = list(pvals.items()) if isinstance(pvals, dict) else list(enumerate(pvals))
    order = sorted(items, key=lambda kv: kv[1])
    m, adj, run = len(order), {}, 0.0
    for i, (k, p) in enumerate(order):
        run = max(run, min(1.0, (m - i) * p))
        adj[k] = run
    return adj if isinstance(pvals, dict) else [adj[i] for i in range(m)]


def load_long(path, arm_a, arm_b, cluster_col=None):
    rows = list(csv.DictReader(open(path, newline="")))
    tasks = sorted({r["task"] for r in rows})
    tix = {t: i for i, t in enumerate(tasks)}

    def mat(arm):
        seeds = sorted({r["seed"] for r in rows if r["arm"] == arm})
        six = {s: i for i, s in enumerate(seeds)}
        Y = [[None] * len(tasks) for _ in seeds]
        for r in rows:
            if r["arm"] == arm and r["reward"] not in ("", "nan", "NaN"):
                Y[six[r["seed"]]][tix[r["task"]]] = float(r["reward"])
        return Y

    cl = None
    if cluster_col:
        fam = {r["task"]: r[cluster_col] for r in rows}
        cl = [fam[t] for t in tasks]
    return mat(arm_a), mat(arm_b), cl, tasks


def _selftest():
    rng = random.Random(1)
    # 1. identities
    Ya = [[1.0, 0.0, 1.0, 1.0], [0.0, 0.0, 1.0, 1.0]]
    Yb = [0.0, 0.0, 1.0, 0.0]
    r = paired_cluster_bootstrap(Ya, Yb, cluster=["a", "a", "b", "b"], B=300)
    assert abs(r["theta"] - 0.375) < 1e-12 and r["n_clusters"] == 2 and r["n_seeds"] == 2, r
    Ya2 = [row[:] for row in Ya]; Ya2[0][3] = None
    r2 = paired_cluster_bootstrap(Ya2, Yb, B=100)
    exp = (sum(a - b for a, b in zip(Ya2[0], Yb) if a is not None) + sum(a - b for a, b in zip(Ya2[1], Yb))) / 7
    assert abs(r2["theta"] - exp) < 1e-12, (r2["theta"], exp)
    h = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert abs(h["a"] - 0.03) < 1e-12 and abs(h["b"] - 0.06) < 1e-12 and abs(h["c"] - 0.06) < 1e-12, h
    # 2. calibration on synthetic clustered data: T=60 tasks in 12 families, S=3 seeds
    T, F, S, true, reps = 60, 12, 3, 0.04, 120
    fam = [i // (T // F) for i in range(T)]
    cover = rej = cover_noclu = cover_cr = rej_cr = 0
    for i in range(reps):
        fe = [rng.gauss(0, 0.15) for _ in range(F)]
        d_task = [true + fe[fam[t]] + rng.gauss(0, 0.15) for t in range(T)]
        base = [rng.uniform(0.2, 0.8) for _ in range(T)]
        Yb = [x + rng.gauss(0, 0.05) for x in base]
        Ya = [[base[t] + d_task[t] + rng.gauss(0, 0.05) for t in range(T)] for _ in range(S)]
        r = paired_cluster_bootstrap(Ya, Yb, fam, B=400, seed=i)
        cover += r["ci"][0] <= true <= r["ci"][1]
        cover_cr += r["cr_ci"][0] <= true <= r["cr_ci"][1]
        r1 = paired_cluster_bootstrap(Ya, Yb, None, B=400, seed=i)            # ignoring clustering
        cover_noclu += r1["ci"][0] <= true <= r1["ci"][1]
        Ya0 = [[x - true for x in row] for row in Ya]                          # shift so the null is true
        r0 = paired_cluster_bootstrap(Ya0, Yb, fam, B=400, seed=i)
        rej += r0["p_two_sided"] < 0.05
        rej_cr += r0["cr_p_two_sided"] < 0.05
    cov, size, covn, covcr, sizecr = cover / reps, rej / reps, cover_noclu / reps, cover_cr / reps, rej_cr / reps
    print(f"selftest (C=12 clusters, T=60, S=3, {reps} reps): percentile-bootstrap coverage={cov:.2f}, size={size:.3f}; "
          f"cluster-robust t coverage={covcr:.2f}, size={sizecr:.3f}; ignoring clustering coverage={covn:.2f}")
    assert 0.90 <= covcr <= 0.995, covcr            # headline interval is calibrated
    assert sizecr <= 0.09, sizecr
    assert cov >= 0.80, cov                         # bootstrap is usable but known to under-cover at C=12
    assert covn < covcr - 0.05, (covn, covcr)       # ignoring the clustering is clearly worse
    # 3. seed level
    r = paired_cluster_bootstrap(Ya, Yb, fam, level="task+seed", B=300)
    assert r["seed_t_ci"] is not None and r["ci"][0] <= r["theta"] <= r["ci"][1], r
    print("selftest: PASS")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--long")
    ap.add_argument("--arm-a"); ap.add_argument("--arm-b")
    ap.add_argument("--cluster-col")
    ap.add_argument("--level", default="task", choices=["task", "task+seed"])
    ap.add_argument("--B", type=int, default=10000)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    if not (a.long and a.arm_a and a.arm_b):
        ap.error("--long, --arm-a, --arm-b required")
    Ya, Yb, cl, _ = load_long(a.long, a.arm_a, a.arm_b, a.cluster_col)
    res = paired_cluster_bootstrap(Ya, Yb, cl, level=a.level, B=a.B)
    res["p_signflip"] = signflip_pvalue(Ya, Yb, cl)
    print(json.dumps(res, indent=2))
    if a.out:
        open(a.out, "w").write(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
