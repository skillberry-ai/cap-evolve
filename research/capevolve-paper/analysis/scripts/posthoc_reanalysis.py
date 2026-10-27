#!/usr/bin/env python3
"""POST HOC re-analysis of already scored data (amendment 12 addendum 21, part 0). No new data. Written and registered BEFORE it is run.
Every number this script prints is POST HOC: the methods were chosen after the registered results (Holm, m = 10) were seen, because they reject more.

 (A) tau2, MERGED window: CapEvolve (searches 1, 2, 3 = GATE-K2 s0, s1, s3) minus each of the ten comparators (eight published optimizers, ACE, HarnessLens), task-paired,
     artifact level. (i) the registered Holm (m = 10), reprinted; (ii) a sign-flip permutation maxT: the 20 task differences of each comparison are multiplied by random +-1
     (exact enumeration of the 2^20 sign vectors, the SAME vector for all ten comparisons), the statistic is the studentised mean |t_j|, and the adjusted p of comparison j is
     P(max_k |t*_k| >= |t_j|). Assumes the per-task differences are symmetric about 0 under the null; flips tasks, not searches.
 (B) tau2 pooled test: CapEvolve minus the equal-weight mean of the nine non-inert comparators (HarnessLens, whose champion is the unmodified agent, is excluded; a ten-comparator
     version is printed as a sensitivity), task-paired, CR1 t(19).
 (C) AppWorld one-session TEST_ALL: Holm over CapEvolve's ten comparisons (m = 10) instead of the session's 78 pairs, computed from the PUBLISHED raw p of aw_testall_vs_cape.csv
     (4 decimals; per-task AppWorld data are not available to the reviewer, so no AppWorld pooled test or permutation test is possible here). Where a published p is 0.0000 the
     adjusted p is reported as '<0.001'.
    /home/dev/projects2/campaign-scratch/venv/bin/python -I posthoc_reanalysis.py OUTDIR MERGED_ROOT AW_VS_CAPE_CSV        (needs numpy for the 2^20 enumeration; run with the campaign venv, which has numpy 2.5.4)
"""
import csv, json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import paired_cluster_bootstrap as pcb

OUT, MROOT, AWCSV = sys.argv[1:4]
OPT8 = ["evoskill", "gepa", "gepafull", "metaharness", "mipro", "skillopt", "trace2skill", "wikiskill"]
f = lambda x, d=3: f"{x:.{d}f}"; sg = lambda x, d=3: f"{x:+.{d}f}"
pf = lambda p: "<0.001" if p < 0.001 else f"{p:.3f}"
NAMES = {"evoskill": "EvoSkill", "gepa": "GEPA", "gepafull": "GEPA (full)", "metaharness": "Meta-Harness", "mipro": "MIPROv2", "skillopt": "SkillOpt", "trace2skill": "Trace2Skill", "wikiskill": "WikiSkill", "ace": "ACE", "hl-v0": "HarnessLens"}


def main():
    R = [r for r in csv.DictReader(open(os.path.join(MROOT, "results_long.csv"))) if r["split"] == "test"]
    tasks = sorted({r["task"] for r in R}, key=lambda t: (len(t), t)); ix = {t: i for i, t in enumerate(tasks)}; fam = {r["task"]: r["family"] for r in R}
    fl = [fam[t] for t in tasks]; M = {}
    for r in R: M.setdefault(f"{r['arm']}/s{r['seed']}", [None] * len(tasks))[ix[r["task"]]] = float(r["reward"])
    avg = lambda vs: [sum(v[i] for v in vs) / len(vs) for i in range(len(vs[0]))]
    ce = avg([M[f"GATE-K2-s{s}/s0"] for s in (0, 1, 3)])
    comp = {a: avg([M[f"{a}/s{s}"] for s in range(3)]) for a in OPT8 + ["ace"]}; comp["hl-v0"] = M["hl-v0/s0"]
    L = ["# POST HOC re-analysis (addendum 21 part 0; no new data; methods chosen after the registered results were seen)", ""]
    J = {}
    # (A)
    D = {a: np.array([x - y for x, y in zip(ce, c)]) for a, c in comp.items()}; names = list(D); X = np.stack([D[a] for a in names], axis=1)   # 20 x 10
    n = X.shape[0]
    tstat = lambda Z: Z.mean(axis=0) / (Z.std(axis=0, ddof=1) / math.sqrt(n))
    t_obs = tstat(X)
    signs = ((np.arange(2 ** n)[:, None] >> np.arange(n)) & 1).astype(np.int8) * 2 - 1      # 2^20 x 20
    mx = np.empty(signs.shape[0])
    for s in range(0, signs.shape[0], 1 << 17):
        S = signs[s:s + (1 << 17)].astype(np.float64)
        m = S @ X / n; sq = ((S * S) @ (X * X) / n); var = (sq - m * m) * n / (n - 1)
        with np.errstate(divide="ignore", invalid="ignore"):
            T = np.abs(m / np.sqrt(var / n))
        T = np.nan_to_num(T, nan=0.0, posinf=1e9); mx[s:s + (1 << 17)] = T.max(axis=1)
    reg = {}
    for a in names:
        r = pcb.paired_cluster_bootstrap([ce], [comp[a]], fl, B=20); reg[a] = r
    holm = pcb.holm({a: reg[a]["cr_p_two_sided"] for a in names})
    L += ["## (A) tau2: CapEvolve (3 searches) minus each of ten comparators, task-paired", "",
          "| comparator | delta [95% CI, CR1 t19] | raw p | Holm p, m = 10 (registered) | sign-flip maxT adjusted p (POST HOC) |", "|---|---|---|---|---|"]
    order = sorted(names, key=lambda a: reg[a]["cr_p_two_sided"])
    for a in order:
        padj = float((mx >= abs(t_obs[names.index(a)]) - 1e-12).mean()); J[a] = {"delta": reg[a]["theta"], "ci": reg[a]["cr_ci"], "raw_p": reg[a]["cr_p_two_sided"], "holm10": holm[a], "maxT_adj_p": padj}
        L.append(f"| {NAMES[a]} | {sg(reg[a]['theta'])} [{f(reg[a]['cr_ci'][0])}, {f(reg[a]['cr_ci'][1])}] | {pf(reg[a]['cr_p_two_sided'])} | {pf(holm[a])} | {pf(padj)} |")
    k_holm = sum(1 for a in names if holm[a] < 0.05); k_mx = sum(1 for a in names if J[a]["maxT_adj_p"] < 0.05)
    L += ["", f"Comparisons with adjusted p < 0.05: Holm {k_holm} of 10; sign-flip maxT {k_mx} of 10 (exact enumeration of {2 ** n:,} sign vectors; studentised statistic).", ""]
    # (B)
    nine = avg([comp[a] for a in OPT8 + ["ace"]]); ten = avg([comp[a] for a in OPT8 + ["ace", "hl-v0"]])
    L += ["## (B) tau2 pooled: CapEvolve minus the equal-weight mean of the comparators (POST HOC)", "", "| comparator set | delta [95% CI, CR1 t19] | raw p |", "|---|---|---|"]
    for nm, c in (("nine non-inert comparators (primary of this part)", nine), ("ten, with HarnessLens (sensitivity)", ten)):
        r = pcb.paired_cluster_bootstrap([ce], [c], fl, B=20); J["pooled " + nm[:4]] = {"delta": r["theta"], "ci": r["cr_ci"], "p": r["cr_p_two_sided"]}
        L.append(f"| {nm} | {sg(r['theta'])} [{f(r['cr_ci'][0])}, {f(r['cr_ci'][1])}] | {pf(r['cr_p_two_sided'])} |")
    # (C)
    rows = [r for r in csv.DictReader(open(AWCSV)) if r["other"] != "seed"]
    pv = {r["other"]: float(r["p"]) for r in rows}; h = pcb.holm(pv)
    L += ["", "## (C) AppWorld one session (test_normal, 5 trials, 168 tasks): Holm over CapEvolve's ten comparisons (POST HOC; from PUBLISHED raw p to four decimals)", "",
          "| comparator | published (other minus CapEvolve) TGC [CI] | raw p | Holm p, m = 10 | published Holm over 78 pairs |", "|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: float(r["p"])):
        a = r["other"]; adj = "<0.001" if pv[a] == 0.0 else pf(h[a]); J["aw " + a] = {"d_tgc": float(r["d_tgc"]), "raw_p": pv[a], "holm10": h[a]}
        L.append(f"| {a} | {r['d_tgc']} [{r['lo']}, {r['hi']}] | {r['p']} | {adj} | {r['holm78']} |")
    L += ["", f"AppWorld comparisons with Holm (m = 10) < 0.05: {sum(1 for a in pv if h[a] < 0.05 and pv[a] > 0)} computed from nonzero published p plus {sum(1 for a in pv if pv[a] == 0.0)} with published p 0.0000. A published p is a bootstrap value to four decimals; a Holm p near 0.05 is sensitive to that rounding.", "",
          "The AppWorld pooled test and an AppWorld permutation test need the per-task data and are not computed here."]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "posthoc.md"), "w").write("\n".join(L) + "\n"); json.dump(J, open(os.path.join(OUT, "posthoc.json"), "w"), indent=1, default=str)
    print("\n".join(L))


if __name__ == "__main__":
    main()
