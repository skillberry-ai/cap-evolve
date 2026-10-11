"""Minimum detectable effect (MDE) for an optimized-vs-baseline contrast at 40 / 100 / 280 tasks, S search seeds.

Variance model for the arm-level paired contrast theta_hat (optimized pipeline minus baseline), crossed design,
tasks t=1..T (family-clustered) x search seeds s=1..S, n trials per (arm, seed, task):

    d[s,t] = theta + a_t + b_s + c_st + e_st
      a_t  ~ (0, tau^2)       task-specific true advantage (heterogeneity of the effect across tasks)
      b_s  ~ (0, sig_s^2)     search-seed (pipeline) variance of the optimized artifact's quality
      c_st ~ (0, tau_int^2)   seed x task interaction (different seeds help different tasks)
      e_st ~ (0, noise/n)     trial noise: [pc(1-pc)+pp(1-pp)]/n, 0.297/n at mu=.55,kappa=1.5 (sim_stderr)

    Var(theta_hat) = DEFF*tau^2/T + sig_s^2/S + DEFF*(tau_int^2 + noise/n)/(T S)
    DEFF = 1 + (m-1)*rho  is the task-family design effect (m = tasks per family, rho = ICC of the task advantage).

Two MDE flavours:
  conditional on the S artifacts (claim about THESE champions):  Var_cond = DEFF*(tau^2 + (tau_int^2+noise/n)/S)/T
        critical values normal (T/DEFF large)
  pipeline-level (claim about the optimizer): Var above; critical values t with df = S-1 for the seed-dominated
        component, conservative: MDE = (t_{1-a/2,S-1} + t_{power,S-1}) * sqrt(Var)  [Holm: a/m]

    python -I sim_mde.py [--mc]
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_common import OUT, md_table  # noqa: E402

from statistics import NormalDist

N01 = NormalDist()


def _t_cdf(x, df):
    """Student t CDF by Simpson integration of the pdf (df>=1); accurate to ~1e-8 for |x|<60."""
    c = math.exp(math.lgamma((df + 1) / 2) - math.lgamma(df / 2)) / math.sqrt(df * math.pi)
    f = lambda u: c * (1 + u * u / df) ** (-(df + 1) / 2)  # noqa: E731
    n = 4000
    h = abs(x) / n
    s = f(0) + f(abs(x)) + sum((4 if i % 2 else 2) * f(i * h) for i in range(1, n))
    half = s * h / 3
    return 0.5 + math.copysign(half, x)


def t_ppf(p, df):
    lo, hi = 0.0, 200.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if _t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def tq(df, m):
    """(critical value for two-sided alpha=0.05/m, quantile for power 0.8) of Student t with df d.f."""
    return t_ppf(1 - 0.025 / m, df), t_ppf(0.8, df)


def mde(T, S, n, *, tau=0.15, tau_int=0.10, sig_s=0.03, noise=0.297, m_fam=5, rho=0.10, m_cmp=1, flavour="pipeline"):
    deff = 1 + (m_fam - 1) * rho
    if flavour == "conditional":
        var = deff * (tau ** 2 + (tau_int ** 2 + noise / n) / S) / T
        z = N01.inv_cdf(1 - 0.05 / (2 * m_cmp)) + N01.inv_cdf(0.8)
    else:
        var = deff * tau ** 2 / T + sig_s ** 2 / S + deff * (tau_int ** 2 + noise / n) / (T * S)
        a, b = tq(S - 1, m_cmp)
        z = a + b
    return z * math.sqrt(var), math.sqrt(var)


def mc_check(T=100, S=5, n=5, reps=3000, seed=3, **kw):
    """Monte Carlo validation of the pipeline variance formula (Gaussian components, no clustering)."""
    import random
    p = dict(tau=0.15, tau_int=0.10, sig_s=0.03, noise=0.297)
    p.update(kw)
    rng = random.Random(seed)
    th = []
    for _ in range(reps):
        a = [rng.gauss(0, p["tau"]) for _ in range(T)]
        b = [rng.gauss(0, p["sig_s"]) for _ in range(S)]
        tot = 0.0
        for s_ in range(S):
            for t in range(T):
                tot += a[t] + b[s_] + rng.gauss(0, p["tau_int"]) + rng.gauss(0, math.sqrt(p["noise"] / n))
        th.append(tot / (S * T))
    m = sum(th) / len(th)
    v_mc = sum((x - m) ** 2 for x in th) / (len(th) - 1)
    return v_mc, p["tau"] ** 2 / T + p["sig_s"] ** 2 / S + (p["tau_int"] ** 2 + p["noise"] / n) / (T * S)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", action="store_true")
    a = ap.parse_args()
    res = {"assumptions": dict(tau=0.15, tau_int=0.10, sig_s=0.03, noise_per_trial_pair=0.297, m_fam=5, rho=0.10,
                               alpha=0.05, power=0.8)}
    rows_c, rows_p = [], []
    for T in (40, 100, 280):
        for n in (3, 5):
            for S in (3, 5, 10):
                mc1, se_c = mde(T, S, n, flavour="conditional")
                mc3, _ = mde(T, S, n, flavour="conditional", m_cmp=3)
                mp1, se_p = mde(T, S, n, flavour="pipeline")
                mp3, _ = mde(T, S, n, flavour="pipeline", m_cmp=3)
                rows_c.append([T, n, S, f"{se_c:.4f}", f"{mc1:.3f}", f"{mc3:.3f}"])
                rows_p.append([T, n, S, f"{se_p:.4f}", f"{mp1:.3f}", f"{mp3:.3f}"])
                res[f"T={T},n={n},S={S}"] = dict(se_cond=se_c, mde_cond=mc1, mde_cond_holm3=mc3, se_pipe=se_p,
                                                 mde_pipe=mp1, mde_pipe_holm3=mp3)
    # sensitivity of the headline cell to the unknown variance components
    sens = []
    for lab, kw in [("base", {}), ("tau=0.10", dict(tau=0.10)), ("tau=0.20", dict(tau=0.20)),
                    ("sig_s=0.015", dict(sig_s=0.015)), ("sig_s=0.05", dict(sig_s=0.05)),
                    ("m_fam=10,rho=0.2 (strong clustering)", dict(m_fam=10, rho=0.2)),
                    ("no clustering", dict(m_fam=1))]:
        sens.append([lab] + [f"{mde(T, 3, 5, flavour='pipeline', **kw)[0]:.3f}" for T in (40, 100, 280)]
                    + [f"{mde(T, 3, 5, flavour='conditional', **kw)[0]:.3f}" for T in (40, 100, 280)])
    md = ["# sim_mde: minimum detectable effect (alpha=0.05 two-sided, power 0.80)\n",
          "Assumptions (placeholders to be replaced by pilot estimates; see analysis_plan.md section 7): "
          "tau=0.15 SD of per-task true advantage, tau_int=0.10 seed x task interaction, sig_s=0.03 SD of search-seed artifact quality, "
          "trial noise 0.297/n for a pair at mu=.55/kappa=1.5, family size 5 with rho=0.10 (DEFF=1.4).\n",
          "## Conditional on the S artifacts (claim about the specific champions; normal critical values)\n",
          md_table(["tasks T", "trials n", "seeds S", "SE(theta)", "MDE (1 comparison)", "MDE (Holm, m=3 -> alpha/3)"], rows_c),
          "\n## Pipeline-level (claim about the optimizer; seed variance included, t with df=S-1)\n",
          md_table(["tasks T", "trials n", "seeds S", "SE(theta)", "MDE (1 comparison)", "MDE (Holm first step, m=3)"], rows_p),
          "\n## Sensitivity (S=3, n=5): MDE pipeline-level T=40/100/280 | conditional T=40/100/280\n",
          md_table(["variant", "pipe 40", "pipe 100", "pipe 280", "cond 40", "cond 100", "cond 280"], sens)]
    if a.mc:
        vm, vf = mc_check()
        res["mc_check"] = {"mc_var": vm, "formula_var": vf}
        md.append(f"\nMonte Carlo check (T=100,S=5,n=5, no clustering): var(theta_hat) MC={vm:.6f} vs formula={vf:.6f}\n")
    (OUT / "sim_mde.json").write_text(json.dumps(res, indent=1))
    (OUT / "sim_mde.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
