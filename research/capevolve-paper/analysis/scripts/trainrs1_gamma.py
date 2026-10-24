#!/usr/bin/env python3
"""TRAINRS1 transfer ratio, exactly the estimator of the paper's 0.28 (amendment 12 addendum 18, superseding trainrs1_analysis.py). Written BEFORE the data exist.

Numerator (held-out gain, fixed, already scored): MERGED test-20, each arm's mean over its seeds minus the MERGED in-window seed mean (0.500), for ALL arms.
Denominator (search gain, NEW): the arm's TRAINRS1 train-30 mean over its seeds minus the TRAINRS1 in-window seed mean (k = 10). Fit-set scores.
  per-arm gamma = arm-mean held-out gain / arm-mean search gain
  pooled published gamma = sum over the 8 arms of held-out gain / sum of search gain (8 arm means)
  arm bootstrap: 10,000 resamples of the 8 arms, random.seed(0), 2.5 / 97.5 percentiles
  CapEvolve gamma = ratio of the means over its 3 searches (GATE-K2-s0, s1, s3 = TRAINRS1 GATE-K2-search1, 2, 3); per search beside it. s2 excluded by name.
Supplementary (not the paper's estimator): a task bootstrap (test tasks and train tasks resampled), and the seed-check minus seed on train-30.
Pure standard library.   python3 -I trainrs1_gamma.py OUTDIR TRAINRS1_ROOT MERGED_ROOT
"""
import csv, json, os, random, sys
OUT, TR, MG = sys.argv[1:4]
COMP8 = ["gepafull", "gepa", "skillopt", "wikiskill", "metaharness", "evoskill", "mipro", "trace2skill"]
CE_TR = ["GATE-K2-search1", "GATE-K2-search2", "GATE-K2-search3"]; CE_MG = ["GATE-K2-s0", "GATE-K2-s1", "GATE-K2-s3"]
f = lambda x, d=3: f"{x:.{d}f}"; sg = lambda x, d=3: f"{x:+.{d}f}"


def load(root, split):
    M = {}
    for r in csv.DictReader(open(os.path.join(root, "results_long.csv"))):
        if r["split"] == split and r["reward"] != "": M.setdefault(r["arm"], {}).setdefault(r["seed"], {})[r["task"]] = float(r["reward"])
    return M


def gain(M, arm, seedarm, tasks):
    s = sum(sum(v[t] for t in tasks) / len(tasks) for v in M[seedarm].values()) / len(M[seedarm])
    return sum(sum(v[t] for t in tasks) / len(tasks) for v in M[arm].values()) / len(M[arm]) - s


def pooled_boot(num, den, arms):
    rng = random.Random(0); v = []
    for _ in range(10000):
        a = [rng.choice(arms) for _ in arms]; d = sum(den[x] for x in a)
        if d != 0: v.append(sum(num[x] for x in a) / d)
    v.sort(); return v[int(.025 * len(v))], v[min(len(v) - 1, int(.975 * len(v)))]


def main():
    Te, Tr = load(MG, "test"), load(TR, "train")
    for need in COMP8 + CE_TR + ["seed", "seed-check"]:
        if need not in Tr: raise SystemExit(f"{need!r} missing from the TRAINRS1 results_long.csv (train split)")
    te = sorted({t for v in Te["seed"].values() for t in v}); tr = sorted({t for v in Tr["seed"].values() for t in v})
    num = {a: gain(Te, a, "seed", te) for a in COMP8}; num.update({a: gain(Te, m, "seed", te) for a, m in zip(CE_TR, CE_MG)})
    den = {a: gain(Tr, a, "seed", tr) for a in COMP8 + CE_TR}
    per = {a: num[a] / den[a] for a in num}
    pub = sum(num[a] for a in COMP8) / sum(den[a] for a in COMP8); lo, hi = pooled_boot(num, den, COMP8)
    ce = sum(num[a] for a in CE_TR) / sum(den[a] for a in CE_TR)
    seedm = sum(sum(v[t] for t in tr) / len(tr) for v in Tr["seed"].values()) / len(Tr["seed"])
    scm = sum(sum(v[t] for t in tr) / len(tr) for v in Tr["seed-check"].values()) / len(Tr["seed-check"])
    # supplementary task bootstrap
    rng = random.Random(20261025); P, C, Dd = [], [], []
    for _ in range(4000):
        a = [rng.choice(te) for _ in te]; b = [rng.choice(tr) for _ in tr]
        n2 = {x: gain(Te, x if x in Te else dict(zip(CE_TR, CE_MG))[x], "seed", a) for x in COMP8 + CE_TR}; d2 = {x: gain(Tr, x, "seed", b) for x in COMP8 + CE_TR}
        sp, sc_ = sum(d2[x] for x in COMP8), sum(d2[x] for x in CE_TR)
        if sp <= 0.02 or sc_ <= 0.02: continue
        p = sum(n2[x] for x in COMP8) / sp; c = sum(n2[x] for x in CE_TR) / sc_; P.append(p); C.append(c); Dd.append(c - p)
    q = lambda v, z: sorted(v)[min(len(v) - 1, int(z * len(v)))]; ci = lambda v: f"[{f(q(v, .025))}, {f(q(v, .975))}]"
    L = ["# TRAINRS1: transfer ratio from one fresh train-30 session (addendum 18; descriptive; FIT-SET search scores)", "",
         "Held-out gains are from MERGED (already scored; same for all arms); search gains are new, each arm against the TRAINRS1 seed. Train ids were every arm's search data: in-sample, a train-to-test gap, not generalisation. Fresh trials remove noise-selection, not task-selection. CapEvolve: three searches, one seed each; s2 excluded by name.", "",
         f"- TRAINRS1 train-30 seed mean {f(seedm)} (k = 10); seed-check {f(scm)} (k = 5); difference {sg(scm - seedm)}", "",
         "| arm | held-out gain (MERGED) | search gain (TRAINRS1) | gamma |", "|---|---|---|---|"]
    for a in COMP8 + CE_TR: L.append(f"| {a} | {sg(num[a])} | {sg(den[a])} | {f(per[a], 2)} |")
    L += ["", f"- POOLED PUBLISHED gamma (8 arms): {f(pub, 2)}; arm bootstrap (10,000, seed 0) [{f(lo, 2)}, {f(hi, 2)}]; per arm {f(min(per[a] for a in COMP8), 2)} to {f(max(per[a] for a in COMP8), 2)}",
          f"- CAPEVOLVE gamma (ratio of means over searches 1, 2, 3): {f(ce, 2)}; per search " + ", ".join(f"{f(per[a], 2)}" for a in CE_TR),
          f"- CapEvolve minus pooled published gamma: {sg(ce - pub, 2)} (descriptive)",
          f"- supplementary task bootstrap (test and train tasks resampled; {len(P)} of 4000 replicates kept): pooled published {ci(P)}; CapEvolve {ci(C)}; difference {ci(Dd)}",
          "- The earlier 0.28 (several sessions) and 0.41 (in-sample acceptance score) are not part of this table."]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "trainrs1.md"), "w").write("\n".join(L) + "\n")
    json.dump({"held_out": num, "search": den, "gamma": per, "pooled_published": pub, "arm_boot": [lo, hi], "capevolve": ce}, open(os.path.join(OUT, "trainrs1.json"), "w"), indent=1)
    print("\n".join(L))


if __name__ == "__main__":
    main()
