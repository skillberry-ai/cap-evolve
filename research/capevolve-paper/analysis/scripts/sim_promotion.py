"""Simulation (g): the RECOMMENDED two-stage promotion rule for confirmatory runs, vs the one-stage k_se gate.

Rule P = screen with the paired gate (gate.decide, k_se=1, full unmasked delta vector), then CONFIRM with
independent fresh trials of BOTH candidate and parent on the same dev-val tasks: promote iff
    mean(delta_confirm) >= dmin   AND   mean(delta_confirm) / SE_paired(delta_confirm) >= z_c .
The promoted candidate's baseline for the next iteration is its CONFIRMATION measurement (selection-free),
and only confirmation numbers are ever reported as gains. (SE_paired = gate.py:253-262 formula, i.e. the sample SD of
the per-task deltas / sqrt(T).)

    python -I sim_promotion.py [--reps N] [--quick]
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_common import (OUT, apply_edit, draw_base, fmt_rate, md_table, mean, paired_decide, pool_map,  # noqa: E402
                        seeds, var)
from sim_gate import N_ITER, _candidate, _eval, noisy_edit  # noqa: E402

RULES = {"one-stage k=1": None,
         "P(z=1.645,dmin=0.02,n_conf=5)": (1.645, 0.02, 5),
         "P(z=1.645,dmin=0.02,n_conf=10)": (1.645, 0.02, 10),
         "P(z=2.0,dmin=0.02,n_conf=10)": (2.0, 0.02, 10),
         "P(z=1.645,dmin=0,n_conf=10)": (1.645, 0.0, 10)}


def confirm(par, cand, z, dmin, nconf=None):
    d = [c - p for c, p in zip(cand, par)]
    m = mean(d)
    se = math.sqrt(var(d) / len(d))
    return m >= dmin and se > 0 and m / se >= z


def null_run(a):
    seed, cfg = a
    rng = random.Random(seed)
    T, n, rule = cfg["T"], cfg["n"], RULES[cfg["rule"]]
    any_, tot, evals = 0, 0, 0
    for _ in range(cfg["reps"]):
        p = draw_base(rng, T, 0.55, 1.5)
        cur = _eval(rng, p, n, 0.0)
        got = 0
        for _ in range(N_ITER):
            cand = _eval(rng, p, n, 0.0)
            ok = paired_decide(cur, cand, k_se=1.0).accept
            if ok and rule is not None:
                evals += 2 * rule[2] / n          # candidate + parent re-measured, in units of one screening eval
                nc = rule[2]
                fc, fp = _eval(rng, p, nc, 0.0), _eval(rng, p, nc, 0.0)
                ok = confirm(fp, fc, *rule)
                cand = fc
            if ok:
                cur = cand; got += 1
        any_ += got > 0; tot += got
    return any_, tot, evals, cfg["reps"]


def power_run(a):
    seed, cfg = a
    rng = random.Random(seed)
    T, n, rule = cfg["T"], cfg["n"], RULES[cfg["rule"]]
    hits = 0
    for _ in range(cfg["reps"]):
        p = draw_base(rng, T, 0.55, 1.5)
        q = apply_edit(rng, p, cfg["delta"], cfg["sparse"])
        par, cand = _eval(rng, p, n, 0.0), _eval(rng, q, n, 0.0)
        ok = paired_decide(par, cand, k_se=1.0).accept
        if ok and rule is not None:
            ok = confirm(_eval(rng, p, rule[2], 0.0), _eval(rng, q, rule[2], 0.0), *rule)
        hits += ok
    return hits, cfg["reps"]


def mixed_run(a):
    seed, cfg = a
    rng = random.Random(seed)
    T, n, rule = cfg["T"], cfg["n"], RULES[cfg["rule"]]
    rows = []
    for _ in range(cfg["reps"]):
        p = draw_base(rng, T, 0.55, 1.5)
        pop = draw_base(rng, 600, 0.55, 1.5); pop0 = mean(pop)
        cur_true, cur_meas = list(p), _eval(rng, p, n, 0.0)
        seed_meas = list(cur_meas)
        acc = 0
        for _ in range(N_ITER):
            d, sp = _candidate(rng)
            qv, qp = noisy_edit(rng, cur_true, d, *sp), noisy_edit(rng, pop, d, *sp)
            cand = _eval(rng, qv, n, 0.0)
            ok = paired_decide(cur_meas, cand, k_se=1.0).accept
            if ok and rule is not None:
                fc, fp = _eval(rng, qv, rule[2], 0.0), _eval(rng, cur_true, rule[2], 0.0)
                ok = confirm(fp, fc, *rule)
                cand = fc
            if ok:
                acc += 1; cur_true, cur_meas, pop = qv, cand, qp
        rows.append((acc, mean(cur_meas) - mean(seed_meas), mean(cur_true) - mean(p), mean(pop) - pop0))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=3360)
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    reps = 112 if a.quick else a.reps
    chunks = 56
    per = max(1, reps // chunks)
    sd = iter(seeds(20261014, 10 ** 6))
    res = {"meta": {"reps": per * chunks}}
    base = dict(T=40, n=5)
    # null
    jobs, keys = [], []
    for T in (40, 100):
        for rule in RULES:
            for _ in range(chunks):
                jobs.append((next(sd), {**base, "T": T, "rule": rule, "reps": per})); keys.append((T, rule))
    ag = {}
    for k, o in zip(keys, pool_map(null_run, jobs)):
        x = ag.setdefault(k, [0, 0, 0, 0])
        for i in range(4):
            x[i] += o[i]
    res["null"] = {f"T={T} {r}": {"any_false_promote_in_10": v[0] / v[3], "mean_promotes": v[1] / v[3],
                                  "extra_confirm_evals_per_iter": v[2] / (v[3] * N_ITER), "n": v[3]}
                   for (T, r), v in ag.items()}
    # power
    jobs, keys = [], []
    for sparse in (None, 0.25):
        for rule in RULES:
            for dl in (0.02, 0.04, 0.06, 0.08, 0.10):
                for _ in range(chunks):
                    jobs.append((next(sd), {**base, "rule": rule, "delta": dl, "sparse": sparse, "reps": per}))
                    keys.append(("diffuse" if sparse is None else "sparse25", rule, dl))
    ag = {}
    for k, (h, r) in zip(keys, pool_map(power_run, jobs)):
        x = ag.setdefault(k, [0, 0]); x[0] += h; x[1] += r
    pw = {}
    for (kind, rule, dl), (h, r) in ag.items():
        pw.setdefault(f"{kind} {rule}", {})[str(dl)] = h / r
    res["power_T40_n5"] = pw
    # mixed
    jobs, keys = [], []
    for rule in RULES:
        for _ in range(chunks):
            jobs.append((next(sd), {**base, "rule": rule, "reps": max(1, per // 2)})); keys.append(rule)
    ag = {}
    for k, o in zip(keys, pool_map(mixed_run, jobs)):
        ag.setdefault(k, []).extend(o)
    res["mixed"] = {r: {"mean_promotes": mean([x[0] for x in rows]), "reported_gain": mean([x[1] for x in rows]),
                        "true_gain_val_tasks": mean([x[2] for x in rows]), "true_gain_new_tasks": mean([x[3] for x in rows]),
                        "n": len(rows)} for r, rows in ag.items()}
    (OUT / "sim_promotion.json").write_text(json.dumps(res, indent=1))
    md = ["# sim_promotion: one-stage gate vs two-stage promote-with-fresh-confirmation (rule P)\n",
          f"reps ~{per * chunks}/cell, n=5 trials, mu=0.55 kappa=1.5, 10 iterations. Screen = paired gate k_se=1.\n",
          "## False promotion of null edits\n",
          md_table(["setting", "P(>=1 false promote in 10)", "mean false promotes", "extra confirm cost per iteration (units of one screening eval)"],
                   [[k, f"{v['any_false_promote_in_10']:.3f}", f"{v['mean_promotes']:.2f}", f"{v['extra_confirm_evals_per_iter']:.2f}"]
                    for k, v in res["null"].items()]),
          "\n## Power (T=40, n=5)\n"]
    dl = ["0.02", "0.04", "0.06", "0.08", "0.1"]
    md.append(md_table(["scenario"] + [f"d={x}" for x in dl], [[k] + [f"{v[x]:.2f}" for x in dl] for k, v in pw.items()]))
    md += ["\n## Mixed search (60% null / 25% +1..6pt / 15% -1..6pt population-mean edits, idiosyncratic per-task effects)\n",
           md_table(["rule", "mean promotes", "reported gain (champion - seed measured)", "true gain, val tasks", "true gain, new tasks"],
                    [[k, f"{v['mean_promotes']:.2f}", f"{v['reported_gain']:+.4f}", f"{v['true_gain_val_tasks']:+.4f}",
                      f"{v['true_gain_new_tasks']:+.4f}"] for k, v in res["mixed"].items()])]
    (OUT / "sim_promotion.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
