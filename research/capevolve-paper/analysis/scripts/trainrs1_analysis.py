#!/usr/bin/env python3
"""TRAINRS1 transfer-ratio analysis (amendment 12 addendum 18). Written BEFORE the data exist. Descriptive; fit-set scores.

gamma = G_test / G_search per arm. G_test is FIXED from the already scored MERGED window (test-20, each arm's per-seed mean delta over the MERGED
seed, averaged over seeds). G_search is the NEW quantity: the arm's train-30 re-score (k = 5) in the TRAINRS1 window minus the TRAINRS1 seed (n = 20).
Pooled published gamma = sum of the eight arms' G_test / sum of their G_search (the estimator behind the paper's 0.28: pooled ratio of means over arms).
CapEvolve gamma = mean over searches 1, 2, 3 (GATE-K2-s0, s1, s3; s2 excluded by name) of G_test / the same for G_search, and per search.
Uncertainty: a bootstrap that resamples test tasks and train tasks (independently, clusters = tasks) and, for the published pool, the eight arms.
Arm-only bootstrap (the 0.22 to 0.33 style) printed beside. No test task is scored in TRAINRS1. Pure standard library.
    python3 -I trainrs1_analysis.py OUTDIR TRAINRS1_ROOT MERGED_ROOT
"""
import csv, json, os, random, sys
OUT, TR, MG = sys.argv[1:4]
COMP8 = ["gepafull", "gepa", "skillopt", "wikiskill", "metaharness", "evoskill", "mipro", "trace2skill"]
CE = ["GATE-K2-s0", "GATE-K2-s1", "GATE-K2-s3"]
B = 4000; f = lambda x, d=3: f"{x:.{d}f}"; sg = lambda x, d=3: f"{x:+.{d}f}"


def load(root, split):
    M = {}
    for r in csv.DictReader(open(os.path.join(root, "results_long.csv"))):
        if r["split"] == split and r["reward"] != "": M.setdefault((r["arm"], r["seed"]), {})[r["task"]] = float(r["reward"])
    return M


def gains(M, arms, seedarm, tasks, idx):
    """per-arm gain over the in-window seed for the task index sample idx, averaged over the arm's seeds."""
    s = [M[(seedarm, "0")][tasks[i]] for i in idx]; out = {}
    for a in arms:
        ks = sorted(k for (x, k) in M if x == a)
        out[a] = sum(sum(M[(a, k)][tasks[i]] - s[j] for j, i in enumerate(idx)) / len(idx) for k in ks) / len(ks)
    return out


def ratios(gt, gs):
    pub = sum(gt[a] for a in COMP8) / sum(gs[a] for a in COMP8)
    ce = sum(gt[a] for a in CE) / sum(gs[a] for a in CE)
    return pub, ce


def pct(v, q): v = sorted(v); return v[min(len(v) - 1, max(0, int(q * len(v))))]


def main():
    Te, Tr = load(MG, "test"), load(TR, "train")
    te = sorted({t for d in Te.values() for t in d}, key=lambda t: (len(t), t)); tr = sorted({t for d in Tr.values() for t in d}, key=lambda t: (len(t), t))
    for need in COMP8 + CE + ["seed", "seed-check"]:
        if not any(x == need for x, _ in Tr): raise SystemExit(f"{need!r} missing from the TRAINRS1 results_long.csv (train split)")
    # in the MERGED window the seed arm has seeds 0 only; comparators keep their own seeds
    Tr_seed = {("seed", "0"): {t: sum(Tr[(a, k)][t] for (a, k) in Tr if a == "seed") / sum(1 for (a, k) in Tr if a == "seed") for t in tr}}
    Tr = {k: v for k, v in Tr.items() if k[0] != "seed"}; Tr.update(Tr_seed)
    ie, ir = list(range(len(te))), list(range(len(tr)))
    gt = gains(Te, COMP8 + CE, "seed", te, ie); gs = gains(Tr, COMP8 + CE, "seed", tr, ir)
    pub, ce = ratios(gt, gs); per = {a: gt[a] / gs[a] for a in COMP8 + CE}
    rng = random.Random(20261025); P, C, D, PA = [], [], [], []; skipped = 0
    for _ in range(B):
        ae = [rng.choice(ie) for _ in ie]; ar = [rng.choice(ir) for _ in ir]
        g1 = gains(Te, COMP8 + CE, "seed", te, ae); g2 = gains(Tr, COMP8 + CE, "seed", tr, ar)
        arms = [rng.choice(COMP8) for _ in COMP8]
        dp, dc = sum(g2[a] for a in arms), sum(g2[a] for a in CE)
        if dp <= 0.02 or dc <= 0.02: skipped += 1; continue   # unstable denominator; counted and printed
        p = sum(g1[a] for a in arms) / dp; c = sum(g1[a] for a in CE) / dc
        P.append(p); C.append(c); D.append(c - p)
        PA.append(sum(gt[a] for a in arms) / sum(gs[a] for a in arms))
    # train-session noise check: seed-check minus seed on train
    sc = sum(Tr[("seed-check", k)][t] for (a, k) in Tr if a == "seed-check" for t in tr) / (len(tr) * sum(1 for (a, k) in Tr if a == "seed-check"))
    sd = sum(Tr[("seed", "0")][t] for t in tr) / len(tr)
    ci = lambda v: f"[{f(pct(v, .025))}, {f(pct(v, .975))}]"
    L = ["# TRAINRS1: transfer ratio from a fresh train-30 re-score of every arm in ONE session (addendum 18; descriptive; fit-set scores)", "",
         "G_test is from the MERGED window (already scored before TRAINRS1); G_search is new. Train ids were every arm's search data, so the re-score is in-sample: gamma is a train-to-test gap, not generalisation to new tasks. Fresh trials remove noise-selection, not task-selection. One search per CapEvolve entry; no pipeline-level interval. s2 excluded by name.", "",
         f"- seed train-30 mean {f(sd)} (n = 20 trials/task); seed-check mean {f(sc)} (k = 5): difference {sg(sc - sd)}", "",
         "| arm | G_test (MERGED) | G_search (TRAINRS1) | gamma |", "|---|---|---|---|"]
    for a in COMP8 + CE: L.append(f"| {a} | {sg(gt[a])} | {sg(gs[a])} | {f(per[a], 2)} |")
    L += ["", f"- POOLED PUBLISHED gamma (8 arms; ratio of sums): {f(pub, 2)}; bootstrap over test tasks, train tasks and arms {ci(P)}; arms only {ci(PA)}",
          f"- CAPEVOLVE gamma (searches 1, 2, 3; ratio of sums): {f(ce, 2)}; bootstrap over test and train tasks {ci(C)}; per search: " + ", ".join(f"{a} {f(per[a], 2)}" for a in CE),
          f"- CapEvolve minus pooled published gamma: {sg(ce - pub, 2)}; bootstrap {ci(D)} (descriptive; the interval does not carry search-seed variance beyond the three searches)",
          f"- bootstrap replicates skipped for a summed G_search below 0.02: {skipped} of {B}",
          "- For reference only: the paper's earlier 0.28 used search re-scores from several earlier sessions; the 0.41 used the in-sample acceptance score. Neither enters this table."]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "trainrs1.md"), "w").write("\n".join(L) + "\n")
    json.dump({"G_test": gt, "G_search": gs, "gamma": per, "pooled_published": pub, "capevolve": ce, "ci_pub": [pct(P, .025), pct(P, .975)],
               "ci_ce": [pct(C, .025), pct(C, .975)], "ci_diff": [pct(D, .025), pct(D, .975)]}, open(os.path.join(OUT, "trainrs1.json"), "w"), indent=1)
    print("\n".join(L))


if __name__ == "__main__":
    main()
