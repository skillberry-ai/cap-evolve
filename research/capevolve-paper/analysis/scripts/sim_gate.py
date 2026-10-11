"""Simulation study (a), (b), (f): the paired Δ > k·SE gate (gate.decide mode="paired").

(a) false-acceptance of a NULL edit, per step and over a 10-iteration hill-climb that re-uses the
    accepted candidate's own measurement as the next parent (as the loop does);
(b) power vs true delta 0.02-0.10 (diffuse and sparse edits);
(f) winner's curse: gap between the champion's measured val gain and its true / fresh gain.

    python -I sim_gate.py [--reps N] [--quick]

Writes analysis/out/sim_gate.json and analysis/out/sim_gate.md.
"""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_common import (OUT, apply_edit, draw_base, draw_trials, fmt_rate, md_table, mean,  # noqa: E402
                        paired_decide, pool_map, seeds, task_means, wilson)

KS = [0.0, 0.2, 0.3, 1.0, 2.0, 2.5, 3.0]
N_ITER = 10


def _eval(rng, p, n, icc):
    return task_means(draw_trials(rng, p, n, icc))


def _gate(par_m, cand_m, k):
    return paired_decide(par_m, cand_m, k_se=k).accept


def null_search(a):
    seed, cfg = a
    rng = random.Random(seed)
    T, n, icc = cfg["T"], cfg["n"], cfg["icc"]
    out = []
    for _ in range(cfg["reps"]):
        p = draw_base(rng, T, cfg["mu"], cfg["kappa"])
        cur = _eval(rng, p, n, icc)
        acc = []
        for _ in range(N_ITER):
            cand = _eval(rng, p, n, icc)             # null edit: same true rates, fresh trials
            ok = _gate(cur, cand, cfg["k"])
            acc.append(ok)
            if ok:
                cur = cand                           # loop re-uses the accepted candidate's measurement
        out.append(acc)
    return out


def power_run(a):
    seed, cfg = a
    rng = random.Random(seed)
    T, n, icc = cfg["T"], cfg["n"], cfg["icc"]
    hits = 0
    for _ in range(cfg["reps"]):
        p = draw_base(rng, T, cfg["mu"], cfg["kappa"])
        q = apply_edit(rng, p, cfg["delta"], cfg.get("sparse"))
        hits += _gate(_eval(rng, p, n, icc), _eval(rng, q, n, icc), cfg["k"])
    return hits, cfg["reps"]


def noisy_edit(rng, p, m, pi_aff, s):
    """Edit with population-mean effect ~m whose per-task realisation is idiosyncratic: each task is affected
    with prob pi_aff and moves by m/pi_aff + N(0, s) (clipped to [0,1]). Val-task luck (which tasks happen to
    move) does not carry over to new tasks, which is what makes selection on val optimistic for the population."""
    out = []
    for x in p:
        if rng.random() < pi_aff:
            x = min(1.0, max(0.0, x + m / pi_aff + rng.gauss(0.0, s)))
        out.append(x)
    return out


def _candidate(rng):
    u = rng.random()
    sparse = (1.0, 0.10) if rng.random() < 0.5 else (0.3, 0.25)
    if u < 0.60:
        return 0.0, sparse
    if u < 0.85:
        return rng.uniform(0.01, 0.06), sparse
    return -rng.uniform(0.01, 0.06), sparse


def mixed_search(a):
    seed, cfg = a
    rng = random.Random(seed)
    T, n, icc, k = cfg["T"], cfg["n"], cfg["icc"], cfg["k"]
    rows = []
    for _ in range(cfg["reps"]):
        p = draw_base(rng, T, cfg["mu"], cfg["kappa"])
        pop = draw_base(rng, 600, cfg["mu"], cfg["kappa"])
        pop0 = mean(pop)
        seed_true = mean(p)
        cur_true = list(p)
        cur_meas = _eval(rng, p, n, icc)
        seed_meas = list(cur_meas)
        n_acc = n_bad = 0
        for _ in range(N_ITER):
            d, sp = _candidate(rng)
            q_val = noisy_edit(rng, cur_true, d, *sp)
            q_pop = noisy_edit(rng, pop, d, *sp)
            cand = _eval(rng, q_val, n, icc)
            if _gate(cur_meas, cand, k):
                n_acc += 1
                n_bad += (mean(q_pop) - mean(pop)) <= 0
                cur_true, cur_meas, pop = q_val, cand, q_pop
        fresh = mean(_eval(rng, cur_true, n, icc))      # fresh trials of the champion, same val tasks
        fresh_seed = mean(_eval(rng, p, n, icc))
        rows.append((n_acc, n_bad, mean(cur_meas) - mean(seed_meas), fresh - fresh_seed,
                     mean(cur_true) - seed_true, mean(pop) - pop0))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=4000)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seed", type=int, default=20261011)
    a = ap.parse_args()
    reps = 240 if a.quick else a.reps
    chunks = 48
    per = max(1, reps // chunks)
    sd = iter(seeds(a.seed, 10 ** 6))
    res = {"meta": {"reps": per * chunks, "n_iter": N_ITER, "ks": KS,
                    "gate": "gate.decide(mode='paired', min_coverage=0.6, paired_se_floor=0)"}}
    base = dict(T=40, n=5, mu=0.55, kappa=1.5, icc=0.0)
    settings = {
        "base n=1": {**base, "n": 1}, "base n=3": {**base, "n": 3}, "base n=5": base, "base n=10": {**base, "n": 10},
        "mu=0.40 n=5": {**base, "mu": 0.40}, "mu=0.70 n=5": {**base, "mu": 0.70},
        "kappa=0.8 (very bimodal) n=5": {**base, "kappa": 0.8}, "kappa=5 (mild) n=5": {**base, "kappa": 5.0},
        "icc=0.3 n=5": {**base, "icc": 0.3}, "T=100 n=5": {**base, "T": 100}, "T=15 n=5": {**base, "T": 15},
    }
    # ---- (a)
    jobs, keys = [], []
    for name, s in settings.items():
        for k in KS:
            for _ in range(chunks):
                jobs.append((next(sd), {**s, "k": k, "reps": per})); keys.append((name, k))
    agg = {}
    for key, o in zip(keys, pool_map(null_search, jobs)):
        agg.setdefault(key, []).extend(o)
    a_tab = {}
    for (name, k), m in agg.items():
        n = len(m)
        a_tab.setdefault(name, {})[str(k)] = {
            "first_step": sum(r[0] for r in m) / n, "mean_step": sum(sum(r) for r in m) / (n * N_ITER),
            "any_in_10": sum(any(r) for r in m) / n, "mean_accepts": sum(sum(r) for r in m) / n, "n": n}
    res["a_null_false_accept"] = a_tab
    # ---- (b)
    deltas = [0.02, 0.04, 0.06, 0.08, 0.10]
    jobs, keys = [], []
    for n in (3, 5, 10):
        for T in (40, 100):
            for sparse in (None, 0.25):
                for k in KS:
                    for dl in deltas:
                        for _ in range(12):
                            jobs.append((next(sd), {**base, "n": n, "T": T, "k": k, "delta": dl, "sparse": sparse,
                                                    "reps": max(1, reps // 12)}))
                            keys.append((n, T, "diffuse" if sparse is None else "sparse25", k, dl))
    ag = {}
    for key, (h, r) in zip(keys, pool_map(power_run, jobs)):
        x = ag.setdefault(key, [0, 0]); x[0] += h; x[1] += r
    b_tab = {}
    for (n, T, sp, k, dl), (h, r) in ag.items():
        b_tab.setdefault(f"n={n} T={T} {sp}", {}).setdefault(str(k), {})[str(dl)] = h / r
    res["b_power"] = b_tab
    # ---- (f)
    jobs, keys = [], []
    for n in (3, 5, 10):
        for k in KS:
            for _ in range(chunks):
                jobs.append((next(sd), {**base, "n": n, "k": k, "reps": max(1, per // 2)})); keys.append((n, k))
    ag = {}
    for key, o in zip(keys, pool_map(mixed_search, jobs)):
        ag.setdefault(key, []).extend(o)
    f_tab = {}
    for (n, k), m in ag.items():
        N = len(m)
        cond = [r for r in m if r[0] > 0] or m
        col = lambda rows, j: sum(r[j] for r in rows) / len(rows)  # noqa: E731
        f_tab.setdefault(f"n={n}", {})[str(k)] = {
            "mean_accepts": col(m, 0), "frac_with_accept": sum(r[0] > 0 for r in m) / N,
            "frac_accepts_truly_nonpositive_on_pop": sum(r[1] for r in m) / max(sum(r[0] for r in m), 1),
            "measured_gain": col(m, 2), "fresh_trial_gain": col(m, 3), "true_val_gain": col(m, 4), "true_pop_gain": col(m, 5),
            "cond_measured_gain": col(cond, 2), "cond_true_val_gain": col(cond, 4), "cond_true_pop_gain": col(cond, 5),
            "winners_curse_vs_val": col(m, 2) - col(m, 4), "winners_curse_vs_pop": col(m, 2) - col(m, 5), "n": N}
    res["f_winners_curse"] = f_tab
    (OUT / "sim_gate.json").write_text(json.dumps(res, indent=1))

    md = ["# sim_gate results (paired gate, real gate.decide)\n",
          f"reps per cell ~{per * chunks} searches; 10 iterations/search; T=40, mu=0.55, kappa=1.5 unless stated. "
          "Analytic large-sample reference for one step: 1-Phi(k) = 0.500 (k=0), 0.421 (0.2), 0.382 (0.3), 0.159 (1), 0.023 (2).\n",
          "## (a) False acceptance of a null edit\n"]
    for name, d in a_tab.items():
        md.append(f"### {name}\n")
        rows = []
        for k, v in d.items():
            n = v["n"]
            rows.append([k, fmt_rate(round(v["first_step"] * n), n), f"{v['mean_step']:.3f}",
                         fmt_rate(round(v["any_in_10"] * n), n), f"{v['mean_accepts']:.2f}"])
        md.append(md_table(["k_se", "first step [95% CI]", "mean per step (chained)",
                            "P(>=1 false accept in 10) [CI]", "mean #accepts/10"], rows) + "\n")
    md.append("## (b) Power (accept probability) vs true mean delta\n")
    for name, d in b_tab.items():
        md.append(f"### {name}\n")
        dl = sorted({x for v in d.values() for x in v}, key=float)
        md.append(md_table(["k_se"] + [f"d={x}" for x in dl], [[k] + [f"{v[x]:.2f}" for x in dl] for k, v in d.items()]) + "\n")
    md.append("## (f) Winner's curse over a 10-iteration mixed search "
              "(60% null / 25% +1..6pt / 15% -1..6pt edits; half diffuse, half sparse). Gains are champion minus seed.\n")
    for name, d in f_tab.items():
        md.append(f"### {name}\n")
        rows = [[k, f"{v['frac_with_accept']:.2f}", f"{v['mean_accepts']:.2f}", f"{v['measured_gain']:+.4f}",
                 f"{v['fresh_trial_gain']:+.4f}", f"{v['true_val_gain']:+.4f}", f"{v['true_pop_gain']:+.4f}",
                 f"{v['winners_curse_vs_val']:+.4f}", f"{v['winners_curse_vs_pop']:+.4f}",
                 f"{v['frac_accepts_truly_nonpositive_on_pop']:.2f}"] for k, v in d.items()]
        md.append(md_table(["k_se", "P(any accept)", "mean accepts", "measured gain", "fresh-trial gain",
                            "true gain val tasks", "true gain new tasks", "curse vs val", "curse vs new tasks",
                            "frac accepts w/ true pop delta<=0"], rows) + "\n")
    (OUT / "sim_gate.md").write_text("\n".join(md))
    print("\n".join(md[:70]))


if __name__ == "__main__":
    main()
