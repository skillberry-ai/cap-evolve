#!/usr/bin/env python3
"""MERGED window analysis (amendment 12 addenda 12, 13, 14, 15; errata 41, 42, 48). Written BEFORE the data exist.

Cells (names in results_long.csv): GATE-K2-s0..s3 (run IDs; paper labels search 1 = s0, 2 = s1, 3 = s3), the eight published optimizers x 3 seeds,
ace x 3, hl-v0 (one artifact standing for 3 seeds), NC-LOOP, V2-A1a/A1b/A2a/A2b/A3a/A3b (seed-0 champions), seed (n = 20), seed-check (k = 10).

Outputs (merged.md, merged.json):
  PRIMARY  (m = 1): K2 over seeds {0, 1, 3} minus the in-window seed. Artifact level: CR1 t(19) on task-level deltas of the seed-averaged K2 score;
           pipeline level: t(S-1) with SE^2 = SE_task^2 + s_seed^2/S (5M-2). Plain and block-adjusted (5I) when the seed drift flags.
  SENSITIVITIES (always computed): 4 seeds {0,1,2,3}; seeds {0,1} ('no cut champion'); fresh seeds {1,2,3} and {1,3}.
  SECONDARY (own Holm, m = 11): K2 (primary seeds) vs each comparator, paired by task, artifact-level CR1; pipeline level printed for 3-seed comparators.
  ABLATION (exploratory, raw p, no family): each V2-A* champion vs K2 seed 0 and vs the in-window seed.
  Checks: seed-check minus seed, drift (hour blocks), infrastructure counts, flags where a sensitivity disagrees with the primary on CI exclusion of 0.
Pure standard library.   python3 -I merged_analysis.py OUTDIR [RESULTS_ROOT]
"""
import csv, datetime as dt, json, math, os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paired_cluster_bootstrap as pcb

OUT = sys.argv[1]
ROOT = sys.argv[2] if len(sys.argv) > 2 else "/home/dev/projects2/campaign-scratch/final_eval/MERGED/main"
PRIMARY = (0, 1, 3)
SENS = {"four seeds (0,1,2,3)": (0, 1, 2, 3), "seeds 0 and 1 only (no cut champion)": (0, 1),
        "fresh seeds 1,2,3 (with seed 2)": (1, 2, 3), "fresh seeds 1,3 (without seed 2)": (1, 3)}
OPT8 = ["evoskill", "gepa", "gepafull", "metaharness", "mipro", "skillopt", "trace2skill", "wikiskill"]
COMP = [(a, [f"{a}/s{s}" for s in range(3)]) for a in OPT8] + [("ace", [f"ace/s{s}" for s in range(3)]), ("hl-v0", ["hl-v0/s0"]), ("NC-LOOP", ["NC-LOOP/s0"])]
ARMS = ["V2-A1a", "V2-A1b", "V2-A2a", "V2-A2b", "V2-A3a", "V2-A3b"]
f = lambda x, d=3: "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}"
sg = lambda x, d=3: "n/a" if x is None else f"{x:+.{d}f}"
pf = lambda p: "n/a" if p is None else ("<0.001" if p < 0.001 else f"{p:.3f}")


def load(path):
    R = [r for r in csv.DictReader(open(path)) if r["split"] == "test"]
    tasks = sorted({r["task"] for r in R}, key=lambda t: (len(t), t)); ix = {t: i for i, t in enumerate(tasks)}
    fam = {r["task"]: r["family"] for r in R}
    M = {}
    for r in R:   # key: arm/seed as in the order, e.g. 'GATE-K2-s0/s0', 'gepa/s1', 'seed/s0'
        M.setdefault(f"{r['arm']}/s{r['seed']}", [None] * len(tasks))[ix[r["task"]]] = None if r["reward"] in ("", "nan") else float(r["reward"])
    return tasks, [fam[t] for t in tasks], M


def avg(vs):
    return [None if any(v[i] is None for v in vs) else sum(v[i] for v in vs) / len(vs) for i in range(len(vs[0]))]


def contrast(Ya, Yb, fam):
    """Ya: list of seed rows (arm), Yb: list of rows (comparator). Seed-averaged within each side; artifact-level CR1 on task deltas; pipeline-level t(S-1)."""
    r = pcb.paired_cluster_bootstrap(Ya, [avg(Yb)], fam, B=20)
    out = {"theta": r["theta"], "ci": r["cr_ci"], "p": r["cr_p_two_sided"], "se": r["cr_se"], "per_seed": r["per_seed"], "S": len(Ya), "pipe": None}
    if len(Ya) >= 2 and r["seed_sd"] is not None:
        se2 = math.sqrt(r["cr_se"] ** 2 + r["seed_sd"] ** 2 / len(Ya)); q = pcb.t_ppf(0.975, len(Ya) - 1)
        out["pipe"] = (r["theta"] - q * se2, r["theta"] + q * se2)
    return out


def excl(ci):
    return ci[0] > 0 or ci[1] < 0


def main():
    tasks, fam, M = load(os.path.join(ROOT, "results_long.csv"))
    trials = [(dt.datetime.strptime(r["t_start"], "%Y-%m-%dT%H:%M:%SZ").timestamp(), r["arm"], int(r["seed"]), r["task"], float(r["reward"]))
              for r in csv.DictReader(open(os.path.join(ROOT, "results_trials.csv"))) if r["split"] == "test" and r["reward"] != ""]
    # drift of the in-window seed
    t0 = min(t[0] for t in trials); seedt = [t for t in trials if t[1] == "seed"]
    mu = {}
    for _, _, _, k, x in seedt: mu.setdefault(k, []).append(x)
    mu = {k: sum(v) / len(v) for k, v in mu.items()}; blk = {}
    for t, _, _, k, x in seedt: blk.setdefault(int((t - t0) // 3600), []).append(x - mu[k])
    # 5I: blocks with fewer than 5% of the in-window seed trials are merged into the neighbouring block (the later one; the last block into the previous one)
    keys = sorted(blk); tot_n = sum(len(v) for v in blk.values()); bmap = {k: k for k in keys}
    changed = True
    while changed and len(set(bmap.values())) > 1:
        changed = False
        grp = {}
        for k in keys: grp.setdefault(bmap[k], []).append(k)
        order = sorted(grp)
        for i, g in enumerate(order):
            if sum(len(blk[k]) for k in grp[g]) < 0.05 * tot_n:
                tgt = order[i + 1] if i + 1 < len(order) else order[i - 1]
                for k in grp[g]: bmap[k] = tgt
                changed = True; break
    merged = {}
    for k in keys: merged.setdefault(bmap[k], []).extend(blk[k])
    blk_raw, blk = blk, merged
    sd = statistics.pstdev([x for v in blk.values() for x in v])
    ms = [(k, sum(v) / len(v), sd / math.sqrt(len(v)), len(v)) for k, v in sorted(blk.items())]
    rng_ = max(m[1] for m in ms) - min(m[1] for m in ms); se2 = math.sqrt(sum(m[2] ** 2 for m in ms) / len(ms) * 2); flag = rng_ > 2 * se2
    eff = {k: sum(v) / len(v) for k, v in blk.items()}
    acc = {}
    for t, a, s, k, x in trials:
        hb = int((t - t0) // 3600); acc.setdefault((a, s, k), []).append(x - (eff.get(bmap.get(hb, hb), 0.0) if flag else 0.0))
    adj = {}
    for (a, s, k), v in acc.items(): adj.setdefault(f"{a}/s{s}", {})[k] = sum(v) / len(v)
    Mb = {key: [d.get(t) for t in tasks] for key, d in adj.items()}
    rep = json.load(open(os.path.join(ROOT, "per_arm_report.json")))
    tot = {x: sum(v[x] for v in rep.values()) for x in ("jobs", "done", "infra_attempts", "infra_final", "hangs", "candidate_errors", "missing_hang", "empty_output")}
    K2 = lambda src, seeds: [src[f"GATE-K2-s{s}/s0"] for s in seeds]
    J = {}
    L = ["# MERGED window (addenda 12, 13, 14, 15; exploratory except where a family is stated)", "",
         "Task set: 20 test tasks / 20 families; k = 10 trials per task per champion; seed n = 20; seed-check k = 10. Paper labels: search 1 = GATE-K2 s0, search 2 = s1, search 3 = s3 (seed 2 is a run ID with no paper label). Run IDs are used below.", "",
         f"Infrastructure (per_arm_report.json): {tot}", "", "## Window checks", ""]
    sc = contrast([M["seed-check/s0"]], [M["seed/s0"]], fam)
    L.append(f"- seed {f(sum(x for x in M['seed/s0']) / len(tasks))} (n = 20), seed-check {f(sum(x for x in M['seed-check/s0']) / len(tasks))} (k = 10); seed-check minus seed {sg(sc['theta'])} [{f(sc['ci'][0])}, {f(sc['ci'][1])}], p {pf(sc['p'])}")
    L.append("- drift (5I, in-window seed, task-demeaned, hour blocks): " + "; ".join(f"{k}: {sg(m)} (SE {s:.3f}, n={n})" for k, m, s, n in ms) + f". Range {rng_:.3f}, SE of difference {se2:.3f}, flag (>2 SE): {flag}.")
    if flag: L.append("- The drift FLAGS: block-adjusted estimates are printed beside the plain ones; where the two disagree on CI exclusion of 0 for the primary, both are reported and the block-adjusted one is the headline (5I).")
    L += ["", "## Primary (m = 1): GATE-K2 seeds 0, 1, 3 (paper searches 1 to 3) minus the in-window seed", ""]
    def line(name, seeds):
        pl = contrast(K2(M, seeds), [M["seed/s0"]], fam)
        ad = contrast(K2(Mb, seeds), [Mb["seed/s0"]], fam) if flag else None
        return name, seeds, pl, ad
    prim = line("PRIMARY", PRIMARY)
    L += ["| estimate | seeds | delta | 95% CI (artifact, CR1 t19) | raw p | 95% CI (pipeline, t S-1) | per-seed delta | block-adjusted delta [CI] |", "|---|---|---|---|---|---|---|---|"]
    rows = [prim] + [line(n, s) for n, s in SENS.items()]
    flags = []
    for name, seeds, pl, ad in rows:
        pipe = f"[{f(pl['pipe'][0])}, {f(pl['pipe'][1])}]" if pl["pipe"] else "n/a"
        adt = f"{sg(ad['theta'])} [{f(ad['ci'][0])}, {f(ad['ci'][1])}]" if ad else "-"
        L.append(f"| {name} | {','.join(map(str, seeds))} | {sg(pl['theta'])} | [{f(pl['ci'][0])}, {f(pl['ci'][1])}] | {pf(pl['p'])} | {pipe} | {', '.join(sg(x, 2) for x in pl['per_seed'])} | {adt} |")
        if name != "PRIMARY":
            if excl(pl["ci"]) != excl(prim[2]["ci"]): flags.append(f"{name}: plain CI {'excludes' if excl(pl['ci']) else 'includes'} 0 while the primary {'excludes' if excl(prim[2]['ci']) else 'includes'} 0")
            if ad and prim[3] and excl(ad["ci"]) != excl(prim[3]["ci"]): flags.append(f"{name}: block-adjusted CI disagrees with the block-adjusted primary on exclusion of 0")
    if flag and prim[3] and excl(prim[2]["ci"]) != excl(prim[3]["ci"]): flags.append("PRIMARY: plain and block-adjusted CI disagree on exclusion of 0 (block-adjusted is the headline)")
    L += ["", "**FLAGS (sensitivity disagrees with the primary on CI exclusion of 0): " + ("; ".join(flags) if flags else "none") + "**", ""]
    J["primary"] = {"theta": prim[2]["theta"], "ci": prim[2]["ci"], "p": prim[2]["p"]}; J["flags"] = flags
    # K2 per-seed absolute scores
    L += ["Per-seed K2 means (plain): " + ", ".join(f"s{s} {f(sum(M[f'GATE-K2-s{s}/s0']) / len(tasks))}" for s in range(4)), ""]
    # secondary
    L += ["## Secondary (own Holm, m = 11): GATE-K2 (seeds 0, 1, 3) minus each comparator, paired by task", "",
          "| comparator | delta | 95% CI (artifact) | raw p | Holm p | 95% CI (pipeline; 3-seed comparators only) | verdict | " + ("block-adjusted delta [CI] p |" if flag else "") , "|---|---|---|---|---|---|---|" + ("---|" if flag else "")]
    res = []
    for name, keys in COMP:
        rows_b = [M[k] for k in keys]
        c = contrast(K2(M, PRIMARY), rows_b, fam)
        ca = contrast(K2(Mb, PRIMARY), [Mb[k] for k in keys], fam) if flag else None
        res.append((name, c, ca, len(keys)))
    hp = pcb.holm([c["p"] for _, c, _, _ in res])
    for (name, c, ca, nk), h in zip(res, hp):
        pipe = f"[{f(c['pipe'][0])}, {f(c['pipe'][1])}]" if (c["pipe"] and nk == 3) else "n/a (one artifact or single seed)"
        verdict = ("K2 higher" if c["theta"] > 0 else "K2 lower") if h < 0.05 else "inconclusive"
        adt = f" {sg(ca['theta'])} [{f(ca['ci'][0])}, {f(ca['ci'][1])}] p {pf(ca['p'])} |" if ca else ""
        L.append(f"| {name} | {sg(c['theta'])} | [{f(c['ci'][0])}, {f(c['ci'][1])}] | {pf(c['p'])} | {pf(h)} | {pipe} | {verdict} |{adt}")
    L += ["", "Each comparator with three seeds is averaged over its seeds; hl-v0 and NC-LOOP are single artifacts (artifact-level only). K2 vs a comparator compares whole methods (templates, code versions, budgets and protocols differ): not an effect of any component.", ""]
    J["secondary"] = [{"comparator": n, "theta": c["theta"], "ci": c["ci"], "p": c["p"], "holm": h} for (n, c, _, _), h in zip(res, hp)]
    # means table
    L += ["## Cell means (plain; seeds averaged)", "", "| cell | mean | seeds | per-seed means |", "|---|---|---|---|"]
    for name, keys in [("seed (n=20)", ["seed/s0"]), ("seed-check", ["seed-check/s0"])] + [(n, k) for n, k in COMP] + [(a, [f"{a}/s0"]) for a in ARMS]:
        vs = [M[k] for k in keys]; L.append(f"| {name} | {f(sum(sum(v) / len(v) for v in vs) / len(vs))} | {len(keys)} | {', '.join(f(sum(v) / len(v)) for v in vs)} |")
    # ablation
    L += ["", "## Ablation arms (exploratory; raw p; no family; one search seed each): seed-0 champion", "",
          "| arm | mean | delta vs in-window seed [95% CI] raw p | delta vs K2 s0 (same-window) [95% CI] raw p | " + ("block-adjusted vs seed | block-adjusted vs K2 s0 |" if flag else ""), "|---|---|---|---|" + ("---|---|" if flag else "")]
    for a in ARMS:
        cs = contrast([M[f"{a}/s0"]], [M["seed/s0"]], fam); ck = contrast([M[f"{a}/s0"]], [M["GATE-K2-s0/s0"]], fam)
        ex = ""
        if flag:
            ds = contrast([Mb[f"{a}/s0"]], [Mb["seed/s0"]], fam); dk = contrast([Mb[f"{a}/s0"]], [Mb["GATE-K2-s0/s0"]], fam)
            ex = f" {sg(ds['theta'])} [{f(ds['ci'][0])}, {f(ds['ci'][1])}] p {pf(ds['p'])} | {sg(dk['theta'])} [{f(dk['ci'][0])}, {f(dk['ci'][1])}] p {pf(dk['p'])} |"
        L.append(f"| {a} | {f(sum(M[f'{a}/s0']) / len(tasks))} | {sg(cs['theta'])} [{f(cs['ci'][0])}, {f(cs['ci'][1])}] p {pf(cs['p'])} | {sg(ck['theta'])} [{f(ck['ci'][0])}, {f(ck['ci'][1])}] p {pf(ck['p'])} |{ex}")
    L += ["", "With ten-ish raw p-values, one or two below 0.05 are expected by chance; planning MDE for a single champion against a single champion is 0.158. A1a and A1b differ from K2 in more than one way (single Claude Code session, no loop or gate). A2a is stricter than K2 on docstrings (surface and lint together)."]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "merged.md"), "w").write("\n".join(L) + "\n"); json.dump(J, open(os.path.join(OUT, "merged.json"), "w"), indent=1, default=str)
    print("\n".join(L))


if __name__ == "__main__":
    main()
