"""MDE recomputed from OBSERVED per-task variance of the unmodified seed artifact (search-split data only, no final data).

Sources (campaign scratch store, read-only):
  Suite A  runs/E10/{hill-climb,agent-optimize}/s*/.capevolve/run_*/eval_index.jsonl  (tag=seed, split=val; 40 tasks, 1 trial per search run)
  Suite B  runs/E10B/{hc,ao,ctl-oneshot}/s*/.capevolve/run_*/eval_index.jsonl (opt 49, 1 trial per run) + runs/E10B/ctl-seed/s*/eval_{opt,sel}.json (2 trials per seed)
  Suite C  runs/E10C/{hc,ao,ctl-oneshot}/s*/.capevolve/run_*/eval_index.jsonl (opt 20) [+ ctl-seed eval_*.json when present]
Every evaluation re-measures the SAME seed artifact, so repeated trials per task give within-task (execution) variance and,
after removing it, the between-task variance of the true pass rate p_i (fitted to Beta(mu, kappa)).

    python -I mde_observed.py [--runs /home/dev/projects2/campaign-scratch/runs]
Writes analysis/out/mde_observed.{md,json}.
"""
import argparse
import glob
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_common import OUT, md_table, mean, var  # noqa: E402
from sim_mde import t_ppf  # noqa: E402


def load_index(paths):
    """task -> list of rewards, one per (file, trial_idx), tag=seed split=val, errored rows skipped."""
    d, evals = {}, []
    for p in paths:
        rows = {}
        for line in open(p):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("tag") == "seed" and r.get("split") == "val":
                rows[(str(r["task"]), r.get("trial_idx", 0))] = float(r["reward"])
        for (t, k), v in rows.items():
            d.setdefault(t, []).append(v)
        evals.append({t: v for (t, k), v in rows.items() if k == 0})
    return d, evals


def load_ctl(paths):
    d = {}
    for p in paths:
        j = json.load(open(p))
        for r in j["rows"]:
            if r.get("error") is None and r.get("reward") is not None:
                d.setdefault(str(r["id"]), []).append(float(r["reward"]))
    return d


def merge(*ds):
    out = {}
    for d in ds:
        for t, v in d.items():
            out.setdefault(t, []).extend(v)
    return out


def estimate(d):
    ks = [len(v) for v in d.values()]
    ph = [mean(v) for v in d.values()]
    s2 = [var(v) for v in d.values() if len(v) >= 2]
    mu = mean(ph)
    w = mean(s2)                                              # E[within-task variance of a single trial]
    var_ph = var(ph)
    var_p = max(var_ph - mean([var(v) / len(v) for v in d.values() if len(v) >= 2]), 1e-4)
    kappa = max(mu * (1 - mu) / var_p - 1, 0.2)
    allv = [x for v in d.values() for x in v]
    return {"n_tasks": len(d), "trials_per_task_min_mean_max": [min(ks), round(mean(ks), 1), max(ks)], "mu": mu,
            "within_var_per_trial": w, "var_true_p": var_p, "kappa": kappa, "sd_true_p": math.sqrt(var_p),
            "binomial_check": mean([p * (1 - p) for p in ph]), "frac_nonbinary": sum(1 for x in allv if 0 < x < 1) / len(allv)}


def paired_null_sd(evals):
    """SD across tasks of (trial from eval i) - (trial from eval j) for the same artifact, pooled over eval pairs: the tau=0 floor."""
    sds = []
    for i in range(len(evals)):
        for j in range(i + 1, len(evals)):
            ts = set(evals[i]) & set(evals[j])
            if len(ts) > 5:
                sds.append(math.sqrt(var([evals[i][t] - evals[j][t] for t in ts])))
    return mean(sds) if sds else None


def eval_mean_sd(evals, T):
    ms = [mean(list(e.values())) for e in evals if len(e) >= 0.9 * T]
    return (mean(ms), math.sqrt(var(ms)), len(ms)) if len(ms) > 1 else (None, None, len(ms))


def mde(T, S, n, w, *, n_seed=None, tau, tau_int=0.10, sig_s=0.03, deff=1.0, m_cmp=1, flavour, sig_b=0.0):
    noise = w * (1 + n / n_seed) if n_seed else 2 * w              # arm at n trials vs seed at n_seed trials (noise/n below)
    if flavour == "conditional":
        v = deff * (tau ** 2 + (tau_int ** 2 + noise / n) / S) / T
        v += sig_b ** 2 * (1 + 1 / S)                         # evaluation-batch shift: S champions in own batches vs one baseline batch
        z = t_ppf(1 - 0.025 / m_cmp, max(T - 1, 1)) + t_ppf(0.8, max(T - 1, 1))
    else:
        v = deff * tau ** 2 / T + sig_s ** 2 / S + deff * (tau_int ** 2 + noise / n) / (T * S)
        v += sig_b ** 2 * (1 + 1 / S)
        z = t_ppf(1 - 0.025 / m_cmp, S - 1) + t_ppf(0.8, S - 1)
    return z * math.sqrt(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="/home/dev/projects2/campaign-scratch/runs")
    a = ap.parse_args()
    R = a.runs
    skip = ("smoke", "pilot", "superseded")
    ok = lambda ps: [p for p in ps if not any(s in p for s in skip)]  # noqa: E731
    src = {}
    dA, evA = load_index(ok(glob.glob(f"{R}/E10/hill-climb/s*/.capevolve/run_*/eval_index.jsonl") + glob.glob(f"{R}/E10/agent-optimize/s*/.capevolve/run_*/eval_index.jsonl")))
    dBi, evB = load_index(ok(sum((glob.glob(f"{R}/E10B/{x}/s*/.capevolve/run_*/eval_index.jsonl") for x in ("hc", "ao", "ctl-oneshot")), [])))
    dBo = merge(dBi, load_ctl(glob.glob(f"{R}/E10B/ctl-seed/s*/eval_opt.json")))
    dBs = load_ctl(glob.glob(f"{R}/E10B/ctl-seed/s*/eval_sel.json"))
    dCi, evC = load_index(ok(sum((glob.glob(f"{R}/E10C/{x}/s*/.capevolve/run_*/eval_index.jsonl") for x in ("hc", "ao", "ctl-oneshot")), [])))
    dCo = merge(dCi, load_ctl(glob.glob(f"{R}/E10C/ctl-seed/s*/eval_opt.json")))
    dCs = load_ctl(glob.glob(f"{R}/E10C/ctl-seed/s*/eval_sel.json"))
    sets = {"A val-40": (dA, evA, 40), "B opt-49": (dBo, evB, 49), "B sel-25": (dBs, [], 25), "C opt-20": (dCo, evC, 20)}
    if dCs:
        sets["C sel-10"] = (dCs, [], 10)
    est, rows = {}, []
    for k, (d, ev, T) in sets.items():
        e = estimate(d)
        e["observed_sd_paired_null_1trial"] = paired_null_sd(ev)
        m, sd, ne = eval_mean_sd(ev, T)
        e["sd_of_split_mean_across_evals"] = sd
        e["n_evals_for_sd"] = ne
        e["predicted_sd_of_split_mean"] = math.sqrt(e["within_var_per_trial"] / T)
        est[k] = e
        rows.append([k, e["n_tasks"], e["trials_per_task_min_mean_max"], f"{e['mu']:.3f}", f"{e['within_var_per_trial']:.3f}",
                     f"{e['sd_true_p']:.3f}", f"{e['kappa']:.2f}", f"{e['frac_nonbinary']:.2f}",
                     "n/a" if e["observed_sd_paired_null_1trial"] is None else f"{e['observed_sd_paired_null_1trial']:.3f} vs {math.sqrt(2*e['within_var_per_trial']):.3f}",
                     "n/a" if sd is None else f"{sd:.3f} vs {e['predicted_sd_of_split_mean']:.3f} ({ne})"])
    # MDE: final sets
    finals = [("A", "A val-40", [60, 70, 80], [1], 12, 1.4), ("B", "B opt-49", [40], [1, 2, 3], 8, 1.0), ("C", "C opt-20", [20], [1, 2, 3], 6, 1.0)]
    mrows, out = [], {}
    for suite, key, Ts, ns, mfam, deff in finals:
        w = est[key]["within_var_per_trial"]
        for T in Ts:
            for n in ns:
                for tau in (0.0, 0.10, 0.15, 0.25):
                    r = {"suite": suite, "T": T, "n": n, "tau": tau, "S": 3, "holm_m": mfam}
                    for fl in ("conditional", "pipeline"):
                        r[fl] = mde(T, 3, n, w, tau=tau, deff=deff, flavour=fl)
                        r[fl + "_holm"] = mde(T, 3, n, w, tau=tau, deff=deff, m_cmp=mfam, flavour=fl)
                    out.setdefault(suite, []).append(r)
                    mrows.append([suite, T, n, tau, f"{r['conditional']:.3f}", f"{r['conditional_holm']:.3f}", f"{r['pipeline']:.3f}", f"{r['pipeline_holm']:.3f}"])
    sig_b = max(math.sqrt(max(est["A val-40"]["sd_of_split_mean_across_evals"] ** 2 - est["A val-40"]["predicted_sd_of_split_mean"] ** 2, 0)), 0.0)
    brow = []
    for tau in (0.10, 0.15, 0.25):
        for fl in ("conditional", "pipeline"):
            brow.append(["A", 70, 1, tau, fl, f"{mde(70, 3, 1, est['A val-40']['within_var_per_trial'], tau=tau, deff=1.4, flavour=fl):.3f}",
                         f"{mde(70, 3, 1, est['A val-40']['within_var_per_trial'], tau=tau, deff=1.4, flavour=fl, sig_b=sig_b):.3f}"])
    out["A_batch_effect"] = {"sig_b": sig_b}
    PLAN = {"A": dict(T=70, n=1, n_seed=2, key="A val-40", deff=1.4, holm_m=12), "B": dict(T=40, n=3, n_seed=3, key="B opt-49", deff=1.0, holm_m=8),
            "C": dict(T=20, n=3, n_seed=3, key="C opt-20", deff=1.0, holm_m=6)}
    planned, prow = {}, []
    for suite, c in PLAN.items():
        w = est[c["key"]]["within_var_per_trial"]
        planned[suite] = {k: c[k] for k in ("T", "n", "n_seed", "holm_m")}
        planned[suite]["mde"] = {}
        for tau in (0.0, 0.10, 0.15, 0.25):
            r = {fl: mde(c["T"], 3, c["n"], w, n_seed=c["n_seed"], tau=tau, deff=c["deff"], flavour=fl) for fl in ("conditional", "pipeline")}
            r.update({fl + "_holm": mde(c["T"], 3, c["n"], w, n_seed=c["n_seed"], tau=tau, deff=c["deff"], m_cmp=c["holm_m"], flavour=fl) for fl in ("conditional", "pipeline")})
            planned[suite]["mde"][str(tau)] = r
            prow.append([suite, c["T"], c["n"], c["n_seed"], tau] + [f"{r[k]:.3f}" for k in ("conditional", "conditional_holm", "pipeline", "pipeline_holm")])
    out["planned"] = planned
    (OUT / "mde_observed.json").write_text(json.dumps({"estimates": est, "mde": out}, indent=1))
    md = ["# mde_observed: MDE from the observed per-task variance of the unmodified seed artifact\n",
          "Data: search-split evaluations of the seed artifact only (no final-set data). Each row pools every re-measurement of the same seed "
          "artifact on that split. Binary-reward check: `within var` is the mean per-task unbiased trial variance (for 0/1 rewards it equals E[p(1-p)]); "
          "`SD p` and `kappa` are the true between-task SD of the pass rate and the matched Beta concentration after removing trial noise "
          "(the earlier plan assumed mu=.55, kappa=1.5, trial-pair noise 0.297/n, i.e. within var 0.149).\n",
          md_table(["split", "tasks", "trials/task (min, mean, max)", "mu", "within var/trial", "SD of true p", "kappa", "frac non-binary rewards",
                    "SD of paired delta between 2 evals: observed vs sqrt(2*within)", "SD of split mean across evals: observed vs sqrt(within/T) (n evals)"], rows),
          "\n## MDE (absolute reward points), alpha .05 two-sided, power .80, S=3 search seeds\n",
          "Variance model as in sim_mde.py, but trial noise = 2 x observed within var / n. `tau` is the SD across tasks of the true per-task "
          "advantage; tau=0 is the noise-only FLOOR on the MDE (no real effect heterogeneity), 0.10-0.25 are plausible ranges that CANNOT be "
          "estimated from baselines alone. tau_int=.10, sigma_s=.03 as before (still placeholders, not identifiable from seed-only data). "
          "Suites B and C have no task families: clusters are tasks, DEFF=1, conditional MDE uses t(T-1). Suite A keeps DEFF=1.4 (family size 5, "
          "ICC .10; not re-estimated). `Holm m` = number of contrasts in the primary family (A 12, B 8, C 6); the Holm column is the first-step "
          "(smallest p) critical level alpha/m.\n",
          md_table(["suite", "final tasks T", "trials n", "tau", "MDE conditional (the 3 champions)", "same, Holm first step", "MDE pipeline-level t(2)", "same, Holm first step"], mrows),
          f"\n## Suite A evaluation-batch effect\n\nThe six seed-artifact evaluations on Suite A val-40 (3 hill-climb, 3 agent-optimize runs, same artifact) have split means 0.579, 0.590, 0.568, 0.462, 0.447, 0.684: SD {est['A val-40']['sd_of_split_mean_across_evals']:.3f} against a binomial prediction of {est['A val-40']['predicted_sd_of_split_mean']:.3f}. The excess is an evaluation-batch SD of about {sig_b:.3f} (5 df, very imprecise; likely gateway load / time of day on the single Gemma deployment). Suites B and C show no excess (observed at or below prediction). If arms are scored in different batches, the contrast variance gains sig_b^2 (1 + 1/S); interleaving all arms in randomized order within one window cancels it, so the protocol requires it. MDE at T=70, n=1, S=3 with and without the batch term:\n",
          md_table(["suite", "T", "n", "tau", "flavour", "MDE no batch effect", f"MDE with sig_b={sig_b:.3f}"], brow),
          "\n## Planned final sizes (pinned in decisions.md 22:30): A T=70 n=1 (seed n=2), B T=40 n=3, C T=20 n=3\n\nContrast vs the seed artifact: noise = within var x (1/n_arm + 1/n_seed). Same variance model; S=3; Holm m = 12 / 8 / 6.\n",
          md_table(["suite", "T", "n arm", "n seed", "tau", "MDE conditional", "same, Holm first step", "MDE pipeline t(2)", "same, Holm first step"], prow)]
    (OUT / "mde_observed.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
