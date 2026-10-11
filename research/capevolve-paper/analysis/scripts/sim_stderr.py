"""Task 2: does stats.combined_stderr (stats.py:35) double count? Check against the candidate estimands.

Estimands for the mean reward over T tasks with n binary trials per task (true task rates p_i):
  A  FIXED task set, NEW executions   Var_A = (1/T^2) sum_i p_i(1-p_i)/n
  B  NEW random tasks, new executions Var_B = [Var(p) + E p(1-p)/n] / T      (the task is the sampling unit)
combined_stderr^2 = var(task means)/T  +  sum(se_i^2)/T^2   (stats.py:51-54).
Algebra: E[var(task means)] = Var(p) + E[p(1-p)]/n -> the first term already estimates T*Var_B and CONTAINS the
within-task noise; the second term adds ~E[p(1-p)]/(nT) = Var_A again. So combined^2 ~ Var_B + Var_A.

Also compares the PAIRED gate SE (gate.py:253-262: sample variance of per-task delta means / T) and the unpaired
`significant` SE sqrt(se_c^2 + se_p^2) built from combined_stderr (gate.py:300).

    python -I sim_stderr.py [--reps N]
"""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_common import (OUT, apply_edit, draw_base, draw_trials, md_table, mean, pool_map, seeds, stats,  # noqa: E402
                        task_means, task_ses, var)


def run(a):
    seed, cfg = a
    rng = random.Random(seed)
    T, n, mu, kap = cfg["T"], cfg["n"], cfg["mu"], cfg["kappa"]
    fixed_p = draw_base(rng, T, mu, kap)
    acc = {}
    add = lambda k, v: acc.setdefault(k, []).append(v)  # noqa: E731
    for _ in range(cfg["reps"]):
        for mode in ("fixed", "new"):
            p = fixed_p if mode == "fixed" else draw_base(rng, T, mu, kap)
            tr = draw_trials(rng, p, n)
            m, se = task_means(tr), task_ses(tr)
            comb = stats.combined_stderr(m, se)
            btw = stats.stderr(m)
            wth = sum(s * s for s in se) ** 0.5 / T
            if mode == "fixed":
                truth = mean(p)
                add("varA_true", sum(x * (1 - x) for x in p) / n / T ** 2)
                add("comb2", comb ** 2); add("between2", btw ** 2); add("within2", wth ** 2)
                add("cover_comb_A", abs(mean(m) - truth) <= 1.96 * comb)
                add("cover_wth_A", abs(mean(m) - truth) <= 1.96 * wth)
            else:
                add("cover_comb_B", abs(mean(m) - mu) <= 1.96 * comb)
                add("cover_btw_B", abs(mean(m) - mu) <= 1.96 * btw)
        p = draw_base(rng, T, mu, kap)
        q = apply_edit(rng, p, cfg["delta"], 0.3)
        ptr, ctr = draw_trials(rng, p, n), draw_trials(rng, q, n)
        pm, cm = task_means(ptr), task_means(ctr)
        d = [c - x for c, x in zip(cm, pm)]
        add("pair2", var(d) / T)
        add("sig2", stats.combined_stderr(cm, task_ses(ctr)) ** 2 + stats.combined_stderr(pm, task_ses(ptr)) ** 2)
        add("varPairA", sum((x * (1 - x) + y * (1 - y)) / n for x, y in zip(p, q)) / T ** 2)
        add("varPairB", acc["varPairA"][-1] + var([y - x for x, y in zip(p, q)]) / T)
    return {k: mean([float(x) for x in v]) for k, v in acc.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=60)
    a = ap.parse_args()
    sd = iter(seeds(77, 10 ** 5))
    cfgs, jobs = [], []
    for kap in (1.5, 5.0):
        for T in (40, 280):
            for n in (1, 3, 5, 10):
                for _ in range(56):
                    c = dict(T=T, n=n, mu=0.55, kappa=kap, delta=0.05, reps=max(1, a.reps // (1 if T == 40 else 5)))
                    cfgs.append(c); jobs.append((next(sd), c))
    outs = pool_map(run, jobs)
    grp = {}
    for c, o in zip(cfgs, outs):
        grp.setdefault((c["kappa"], c["T"], c["n"]), []).append(o)
    rows, prow, res = [], [], {}
    for (kap, T, n), lst in grp.items():
        m = {k: mean([o[k] for o in lst]) for k in lst[0]}
        mu = 0.55
        varB = (mu * (1 - mu) / (kap + 1) + mu * (1 - mu) * kap / (kap + 1) / n) / T
        rows.append([kap, T, n, f"{m['varA_true']:.5f}", f"{varB:.5f}", f"{m['comb2']:.5f}", f"{m['comb2'] / m['varA_true']:.2f}",
                     f"{m['comb2'] / varB:.2f}", f"{m['between2'] / varB:.2f}", f"{m['cover_comb_A']:.3f}",
                     f"{m['cover_comb_B']:.3f}", f"{m['cover_btw_B']:.3f}", f"{m['cover_wth_A']:.3f}"])
        prow.append([kap, T, n, f"{m['pair2']:.5f}", f"{m['varPairA']:.5f}", f"{m['varPairB']:.5f}",
                     f"{m['pair2'] / m['varPairB']:.2f}", f"{m['sig2'] / m['pair2']:.2f}"])
        res[f"kappa={kap},T={T},n={n}"] = {**m, "varB_analytic": varB}
    md = ["# sim_stderr: stats.combined_stderr vs the estimands\n",
          "`Var_A` = true fixed-task execution variance (average over simulated task sets). `Var_B` = analytic "
          "[Var(p)+E p(1-p)/n]/T. If combined_stderr were right for B, `combined^2/Var_B` would be 1; if right for A, "
          "`combined^2/Var_A` would be 1. Coverage = fraction of nominal-95% intervals (mean +- 1.96*SE) containing the target.\n",
          md_table(["kappa", "T", "n", "Var_A", "Var_B", "combined^2", "combined^2/Var_A", "combined^2/Var_B",
                    "between-only^2/Var_B", "cover: combined, target A", "cover: combined, target B",
                    "cover: between-only, target B", "cover: within-only, target A"], rows),
          "\n## Paired difference (edit +0.05 on a random 30% of tasks)\n",
          "`paired^2` = sample variance of per-task delta means / T (gate.py:253-262). `Var_A(pair)` = fixed-task execution variance of "
          "the difference; `Var_B(pair)` adds the across-task variance of the true per-task effects. "
          "`significant^2/paired^2` = unpaired variance (combined_stderr of each arm) over the paired variance: the power the "
          "unpaired mode discards.\n",
          md_table(["kappa", "T", "n", "paired SE^2", "Var_A(pair)", "Var_B(pair)", "paired^2/Var_B(pair)", "significant^2/paired^2"], prow)]
    (OUT / "sim_stderr.json").write_text(json.dumps(res, indent=1))
    (OUT / "sim_stderr.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
