"""Simulation (e): agent-optimize's decision rules under the null and under true effects.

Two rules are exercised with the REAL code:
  * posterior rule  posterior.Pair(...).verdict()  (posterior.py:67): accept iff P(D>0.02)>=0.95 and
    canary cover, with per-task parent-informed Beta priors (K_IMPACT=3 / K_CANARY=6). This is what
    act.py:judge uses when cost_gating is OFF; MC noise: M=400 draws, rng seed 0 as in judge().
  * reward_gated    objectives.decide_reward_gated(...)  (objectives.py:302): the DEFAULT promote gate.
    Reward-superior accept needs dR/SE > z_accept with z_accept = Phi^-1(1 - 0.05/(2*8)) = 2.73 and
    SE floored at NOISE_FLOOR=0.031 (objectives.py:176).

Sequential looks: promote/finalize are re-run as evidence grows, so we report the accept rate at each look
and the probability of accepting at ANY look (candidate trials per task cumulate 3 -> 5 -> 8 -> 10).

    python -I sim_posterior.py [--reps N] [--quick]
"""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_common import OUT, apply_edit, draw_base, draw_trials, fmt_rate, md_table, pool_map, seeds  # noqa: E402

from cap_evolve import objectives, posterior  # noqa: E402

LOOKS = [3, 5, 8, 10]


def _pair(par, cand):
    sp = [sum(r) for r in par]; npar = [len(r) for r in par]
    sc = [sum(r) for r in cand]; nc = [len(r) for r in cand]
    k = posterior.k_vector([(s + .5) / (n + 1) for s, n in zip(sp, npar)])
    return posterior.Pair(k, sp, npar, sc, nc)


def post_run(a):
    seed, cfg = a
    rng = random.Random(seed)
    T = cfg["T"]
    acc, prune = [], []
    for _ in range(cfg["reps"]):
        p = draw_base(rng, T, cfg["mu"], cfg["kappa"])
        q = apply_edit(rng, p, cfg["delta"], cfg.get("sparse")) if cfg["delta"] else p
        par = draw_trials(rng, p, cfg["n_par"])
        cand_all = draw_trials(rng, q, max(LOOKS))
        ra, rp = [], []
        for L in LOOKS:
            v = _pair(par, [r[:L] for r in cand_all]).verdict(random.Random(0), int(T * L))
            ra.append(v["decision"] == "accept"); rp.append(v["decision"] == "prune")
        acc.append(ra); prune.append(rp)
    return acc, prune


def _recs(trials, rng):
    return [objectives.TrialRec(f"t{i}", k, float(x), rng.lognormvariate(0, 0.3))
            for i, row in enumerate(trials) for k, x in enumerate(row)]


def rg_run(a):
    seed, cfg = a
    rng = random.Random(seed)
    T = cfg["T"]
    acc = []
    for _ in range(cfg["reps"]):
        p = draw_base(rng, T, cfg["mu"], cfg["kappa"])
        q = apply_edit(rng, p, cfg["delta"], cfg.get("sparse")) if cfg["delta"] else p
        par = draw_trials(rng, p, cfg["n_par"])
        cand_all = draw_trials(rng, q, max(LOOKS))
        P = _recs(par, rng)
        acc.append([objectives.decide_reward_gated(P, _recs([r[:L] for r in cand_all], rng)).outcome == "accept"
                    for L in LOOKS])
    return acc, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=960)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seed", type=int, default=20261012)
    a = ap.parse_args()
    reps = 56 if a.quick else a.reps
    chunks = 56
    per = max(1, reps // chunks)
    sd = iter(seeds(a.seed, 10 ** 6))
    base = dict(T=40, mu=0.55, kappa=1.5, n_par=5, delta=0.0, sparse=None)
    settings = {"null, parent n=5": base, "null, parent n=10": {**base, "n_par": 10},
                "null, kappa=5": {**base, "kappa": 5.0}, "null, mu=0.40": {**base, "mu": 0.40},
                "null, mu=0.80 (many canaries)": {**base, "mu": 0.80},
                "null, parent n=3": {**base, "n_par": 3},
                "null, mu=0.80, parent n=3": {**base, "mu": 0.80, "n_par": 3},
                "null, mu=0.80, parent n=10": {**base, "mu": 0.80, "n_par": 10},
                "null, mu=0.80, parent n=20": {**base, "mu": 0.80, "n_par": 20}}
    for dl in (0.02, 0.04, 0.06, 0.08, 0.10):
        settings[f"effect +{dl:.2f} diffuse"] = {**base, "delta": dl}
        settings[f"effect +{dl:.2f} sparse25"] = {**base, "delta": dl, "sparse": 0.25}
    settings["effect -0.03 diffuse (regression)"] = {**base, "delta": -0.03}
    cfgz = objectives.GateCfg()
    res = {"meta": {"reps": per * chunks, "looks_cands_per_task": LOOKS,
                    "posterior_params": {"DMIN": posterior.DMIN, "P_ACC": posterior.P_ACC, "M": posterior.M},
                    "reward_gated_z_accept": objectives.z_accept(cfgz), "noise_floor": objectives.NOISE_FLOOR}}
    for tag, fn in (("posterior", post_run), ("reward_gated", rg_run)):
        jobs, keys = [], []
        for name, s in settings.items():
            if tag == "reward_gated" and name in ("null, kappa=5", "null, mu=0.80 (many canaries)", "null, parent n=3") or (
                    tag == "reward_gated" and name.startswith("null, mu=0.80,")):
                continue
            for _ in range(chunks):
                jobs.append((next(sd), {**s, "reps": per})); keys.append(name)
        ag = {}
        for k, (acc, pr) in zip(keys, pool_map(fn, jobs)):
            x = ag.setdefault(k, [[], []]); x[0].extend(acc); x[1].extend(pr or [])
        tab = {}
        for name, (acc, pr) in ag.items():
            n = len(acc)
            tab[name] = {"n": n, "accept_at_look": {str(L): sum(r[j] for r in acc) / n for j, L in enumerate(LOOKS)},
                         "accept_any_look": sum(any(r) for r in acc) / n}
            if pr:
                tab[name]["prune_at_look"] = {str(L): sum(r[j] for r in pr) / n for j, L in enumerate(LOOKS)}
        res[tag] = tab
    (OUT / "sim_posterior.json").write_text(json.dumps(res, indent=1))
    zf = res["meta"]["reward_gated_z_accept"] * res["meta"]["noise_floor"]
    md = ["# sim_posterior results (real posterior.Pair and objectives.decide_reward_gated)\n",
          f"T=40 val tasks, mu=0.55, kappa=1.5; candidate trials/task at looks {LOOKS}; reps per row ~{per * chunks}. "
          f"reward_gated z_accept={res['meta']['reward_gated_z_accept']:.2f}, SE floor {res['meta']['noise_floor']} "
          f"=> reward-superior accept needs mean delta > {zf:.3f} whatever the sample size.\n"]
    for tag in ("posterior", "reward_gated"):
        md.append(f"## {tag}\n")
        rows = []
        for name, v in res[tag].items():
            n = v["n"]
            rows.append([name] + [fmt_rate(round(v["accept_at_look"][str(L)] * n), n) for L in LOOKS]
                        + [fmt_rate(round(v["accept_any_look"] * n), n)])
        md.append(md_table(["scenario"] + [f"accept @ n={L}" for L in LOOKS] + ["accept at ANY look"], rows) + "\n")
    (OUT / "sim_posterior.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
