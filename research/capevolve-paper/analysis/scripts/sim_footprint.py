"""Simulation (c) footprint masking and (d) min_coverage with outcome-dependent missingness.

(c) harness._paired_deltas(footprint=...) (harness.py:1024) zero-pads out-of-footprint tasks; the gate
    then sees a shorter-tailed delta vector AND (harness.py:3003) a paired_se_floor =
    sqrt(sum_{t in fp}(se_par^2 + se_cand^2))/n_total. We call the REAL _paired_deltas and gate.decide.
    Scenario: an edit gains on its footprint F and really regresses tasks R that the footprint misses
    with probability p_miss (the footprint is a text search over rollouts, footprint.py:180).

(d) The harness drops errored trials from a task's mean (harness.py:587 "VALID trial rewards only"), drops
    tasks with zero valid trials from the delta vector (harness.py:1063), and tests coverage only on the
    CANDIDATE side (coverage=cand_val.coverage vs min_coverage=0.6). If candidate-induced errors correlate
    with failure, dropping is a survivor bias.

    python -I sim_footprint.py [--reps N] [--quick]
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_common import (OUT, apply_edit, draw_base, draw_trials, md_table, mean, paired_decide,  # noqa: E402
                        pool_map, seeds, stats, task_means, task_ses)

from cap_evolve import harness  # noqa: E402

T, N = 40, 5
MODES = ("full", "masked_nofloor", "masked_floor")


def _split(means, ses, n):
    return SimpleNamespace(per_task=[
        {"task_id": f"t{i:03d}", "reward": float(m), "stderr": float(s), "raw": {"valid_trials": n}}
        for i, (m, s) in enumerate(zip(means, ses))])


def fp_run(a):
    seed, cfg = a
    rng = random.Random(seed)
    kk = cfg["ks"]
    cnt = {f"{m}|{k}": 0 for m in MODES for k in kk}
    dsum = {m: 0.0 for m in MODES}
    true_net = 0.0
    for _ in range(cfg["reps"]):
        p = draw_base(rng, T, 0.55, 1.5)
        q = list(p)
        order = list(range(T)); rng.shuffle(order)
        F = [i for i in order if p[i] < 0.9][:cfg["f"]]
        rest = [i for i in order if i not in F]
        R = [i for i in rest if p[i] > 0.5][:cfg["r"]]
        for i in F:
            q[i] = min(1.0, p[i] + cfg["gain"])
        for i in R:
            q[i] = max(0.0, p[i] - cfg["loss"])
        true_net += mean([b - x for b, x in zip(q, p)])
        extra = [i for i in rest if i not in R][:cfg["extra"]]
        fp = set(F) | set(extra) | {i for i in R if rng.random() >= cfg["p_miss"]}
        ptr, ctr = draw_trials(rng, p, N), draw_trials(rng, q, N)
        pm, cm, pse, cse = task_means(ptr), task_means(ctr), task_ses(ptr), task_ses(ctr)
        if cfg.get("outcome_dep"):       # worst case: footprint chosen after seeing the observed deltas
            fp = {i for i in range(T) if rng.random() < (0.8 if cm[i] - pm[i] > 0 else 0.15)}
        fpids = {f"t{i:03d}" for i in fp}
        cur, cand = _split(pm, pse, N), _split(cm, cse, N)
        full = harness._paired_deltas(cur, cand, None)
        msk = harness._paired_deltas(cur, cand, fpids)       # the REAL zero-padding
        floor = math.sqrt(sum(pse[i] ** 2 + cse[i] ** 2 for i in fp)) / T   # harness.paired_se_floor formula
        for k in kk:
            for m, dv, fl in (("full", full, 0.0), ("masked_nofloor", msk, 0.0), ("masked_floor", msk, floor)):
                cnt[f"{m}|{k}"] += paired_decide(pm, cm, k_se=k, deltas=dv, floor=fl).accept
        dsum["full"] += mean(full); dsum["masked_nofloor"] += mean(msk); dsum["masked_floor"] += mean(msk)
    return {"cnt": cnt, "n": cfg["reps"], "dsum": dsum, "true_net": true_net}


def cov_run(a):
    seed, cfg = a
    rng = random.Random(seed)
    kk, mech, g = cfg["ks"], cfg["mech"], cfg["gamma"]
    pols = ("drop_errors(current)", "errors_are_failures")
    acc = {f"{p}|{k}": 0 for p in pols for k in kk}
    indec = {p: 0 for p in pols}
    bias = {p: 0.0 for p in pols}
    cov_sum = 0.0
    for _ in range(cfg["reps"]):
        p = draw_base(rng, T, 0.55, 1.5)
        q = apply_edit(rng, p, cfg["delta"], None) if cfg["delta"] else p
        ptr, ctr = draw_trials(rng, p, N), draw_trials(rng, q, N)
        if mech == "trial_fail_triggered":      # failed trials error with prob g (timeouts/crashes on bad runs)
            err = [[(x == 0 and rng.random() < g) for x in row] for row in ctr]
        elif mech == "trial_mcar":              # outcome-independent infra errors, candidate side only
            err = [[rng.random() < g for _ in row] for row in ctr]
        elif mech == "task_hard":               # the whole task errors when the candidate is weak on it
            bad = [(q[i] < 0.3 and rng.random() < g) for i in range(T)]
            err = [[bad[i]] * N for i in range(T)]
        else:
            err = [[False] * N for _ in range(T)]
        pm = task_means(ptr)
        for pol in pols:
            cm, keep = [], []
            for i in range(T):
                if pol == pols[0]:
                    v = [x for x, e in zip(ctr[i], err[i]) if not e]      # valid trials only (harness.py:587)
                    if v:
                        cm.append(mean(v)); keep.append(i)
                else:
                    cm.append(mean(ctr[i]) if not any(err[i]) else mean([0.0 if e else x for x, e in zip(ctr[i], err[i])]))
                    keep.append(i)
            cov = len(keep) / T
            if not keep:
                continue
            pmk = [pm[i] for i in keep]
            d = [c - x for c, x in zip(cm, pmk)]
            if pol == pols[0]:
                cov_sum += cov
            if paired_decide(pmk, cm, k_se=1.0, deltas=d, coverage=cov).indecisive:
                indec[pol] += 1
            bias[pol] += mean(d) - mean([b - x for b, x in zip(q, p)])
            for k in kk:
                acc[f"{pol}|{k}"] += paired_decide(pmk, cm, k_se=k, deltas=d, coverage=cov).accept
    return {"acc": acc, "indec": indec, "n": cfg["reps"], "cov": cov_sum, "bias": bias}


def merge(outs, keys):
    d = {}
    for k, o in zip(keys, outs):
        x = d.setdefault(k, {"n": 0, "cnt": {}, "dsum": {}, "acc": {}, "indec": {}, "cov": 0.0, "bias": {}, "true_net": 0.0})
        x["n"] += o["n"]; x["cov"] += o.get("cov", 0.0); x["true_net"] += o.get("true_net", 0.0)
        for f in ("cnt", "dsum", "acc", "indec", "bias"):
            for kk, v in o.get(f, {}).items():
                x[f][kk] = x[f].get(kk, 0) + v
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=4000)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seed", type=int, default=20261013)
    a = ap.parse_args()
    reps = 224 if a.quick else a.reps
    chunks = 56
    per = max(1, reps // chunks)
    sd = iter(seeds(a.seed, 10 ** 6))
    ks = [0.2, 0.3, 1.0, 2.0]
    res = {"meta": {"reps": per * chunks, "T": T, "n_trials": N}}
    sc = {}
    for loss in (0.0, 0.30, 0.45):
        for pm in (0.0, 0.5, 1.0):
            sc[f"gain+0.25 on 8 / loss-{loss:.2f} on 8, P(miss R)={pm}"] = dict(f=8, r=8, gain=0.25, loss=loss, extra=4, p_miss=pm)
    sc["NULL edit, footprint=12 tasks (independent of outcomes)"] = dict(f=12, r=0, gain=0.0, loss=0.0, extra=0, p_miss=0.0)
    sc["NULL edit, OUTCOME-DEPENDENT footprint (selected on observed delta sign)"] = dict(f=0, r=0, gain=0.0, loss=0.0, extra=0, p_miss=0.0, outcome_dep=True)
    jobs, keys = [], []
    for name, s in sc.items():
        for _ in range(chunks):
            jobs.append((next(sd), {**s, "ks": ks, "reps": per})); keys.append(name)
    agg = merge(pool_map(fp_run, jobs), keys)
    c_tab = {}
    for name, v in agg.items():
        n = v["n"]
        c_tab[name] = {"n": n, "true_net_delta": v["true_net"] / n,
                       "mean_observed_delta": {m: v["dsum"][m] / n for m in v["dsum"]},
                       "accept": {key: c / n for key, c in v["cnt"].items()}}
    res["c_footprint"] = c_tab

    dsc = {}
    for g in (0.0, 0.25, 0.5, 0.75):
        dsc[f"trial_fail_triggered gamma={g}, edit true -0.03"] = dict(mech="trial_fail_triggered", gamma=g, delta=-0.03)
        dsc[f"trial_fail_triggered gamma={g}, NULL edit"] = dict(mech="trial_fail_triggered", gamma=g, delta=0.0)
    for g in (0.2, 0.5, 0.8):
        dsc[f"trial_mcar gamma={g}, NULL edit"] = dict(mech="trial_mcar", gamma=g, delta=0.0)
        dsc[f"task_hard gamma={g}, edit true -0.03"] = dict(mech="task_hard", gamma=g, delta=-0.03)
    jobs, keys = [], []
    for name, s in dsc.items():
        for _ in range(chunks):
            jobs.append((next(sd), {**s, "ks": ks, "reps": per})); keys.append(name)
    agg = merge(pool_map(cov_run, jobs), keys)
    d_tab = {}
    for name, v in agg.items():
        n = v["n"]
        d_tab[name] = {"n": n, "mean_candidate_coverage": v["cov"] / n,
                       "indecisive_k1": {p: c / n for p, c in v["indec"].items()},
                       "bias_in_delta": {p: c / n for p, c in v["bias"].items()},
                       "accept": {key: c / n for key, c in v["acc"].items()}}
    res["d_missingness"] = d_tab
    (OUT / "sim_footprint.json").write_text(json.dumps(res, indent=1))

    md = ["# sim_footprint results\n", f"reps/row ~{per * chunks}, T={T}, n_trials={N}, base mu=0.55 kappa=1.5.\n",
          "## (c) Footprint masking (accept rates; `full` = no footprint, `masked_floor` = what the harness does)\n"]
    for k in ks:
        md.append(f"### k_se = {k}\n")
        rows = [[name, f"{v['true_net_delta']:+.3f}", f"{v['mean_observed_delta']['full']:+.3f}",
                 f"{v['mean_observed_delta']['masked_floor']:+.3f}", f"{v['accept'][f'full|{k}']:.3f}",
                 f"{v['accept'][f'masked_nofloor|{k}']:.3f}", f"{v['accept'][f'masked_floor|{k}']:.3f}"]
                for name, v in c_tab.items()]
        md.append(md_table(["scenario", "true net delta", "mean obs delta (full)", "mean obs delta (masked)",
                            "accept full", "accept masked, no floor", "accept masked + floor (harness)"], rows) + "\n")
    md.append("## (d) Missingness and min_coverage=0.6 (k_se=1 for the indecisive column)\n")
    for k in ks:
        md.append(f"### accept rate at k_se = {k}\n")
        rows = [[name, f"{v['mean_candidate_coverage']:.2f}", f"{v['indecisive_k1']['drop_errors(current)']:.3f}",
                 f"{v['bias_in_delta']['drop_errors(current)']:+.3f}", f"{v['accept'][f'drop_errors(current)|{k}']:.3f}",
                 f"{v['accept'][f'errors_are_failures|{k}']:.3f}"] for name, v in d_tab.items()]
        md.append(md_table(["scenario", "mean coverage (cand)", "P(indecisive)", "bias of observed delta (current policy)",
                            "accept: drop errors (current)", "accept: errors=failure"], rows) + "\n")
    (OUT / "sim_footprint.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
