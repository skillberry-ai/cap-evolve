#!/usr/bin/env python3
"""K30 window analysis (amendment 12 addendum 21). Written BEFORE the data exist.

One fresh session, tau2 airline, test-20, aws route; every champion cell at 30 trials per task, the seed at 30, the seed-check at the arms' trial count.
Cells in results_long.csv / results_trials.csv (names as in the MERGED artifact manifest, the paper's labels in brackets):
  GATE-K2-s0 [search 1], GATE-K2-s1 [search 2], GATE-K2-s3 [search 3], GATE-NAIVE-K2, GATE-NONE-K2,
  V2-A3a [trace and reward], V2-A3b [grader output only], V2-A2a [tools only], V2-A2b [policy only], V2-A1a [naive Claude Code], seed, seed-check.
PRIMARY contrasts (artifact-level CR1 t(19) on task-level deltas, task-paired, raw p, Holm within the stated family):
  GATE family (m = 2): GATE-NAIVE-K2 minus search 1; GATE-NONE-K2 minus search 1.
  ABLATION family (m = 5): each of the five ablation arms minus search 1.
  CAPEVOLVE (m = 1): the mean of searches 1, 2, 3 minus the in-window seed; artifact-level, and pipeline-level t(S-1) with SE^2 = SE_task^2 + s_search^2/S.
SECONDARY (raw p, no family): each gate and ablation arm minus the in-window seed; search 2 and search 3 minus search 1 (the spread between searches); NAIVE minus NONE.
CHECKS: seed-check minus seed; the 5I drift check (hour blocks, >2 SE flag, blocks under 5% of seed trials merged) with block-adjusted deltas beside the plain ones when it flags; infra counts.
Nothing from other windows is pooled. Pure standard library.   python3 -I k30_analysis.py OUTDIR RESULTS_ROOT
"""
import csv, datetime as dt, json, math, os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paired_cluster_bootstrap as pcb

OUT, ROOT = sys.argv[1], sys.argv[2]
MROOT = sys.argv[3] if len(sys.argv) > 3 else None
S1, S2, S3 = "GATE-K2-s0", "GATE-K2-s1", "GATE-K2-s3"; NAIVE, NONE = "GATE-NAIVE-K2", "GATE-NONE-K2"
ABL = [("trace and reward", "V2-A3a"), ("grader output only", "V2-A3b"), ("tools only", "V2-A2a"), ("policy only", "V2-A2b"), ("naive Claude Code", "V2-A1a")]
f = lambda x, d=3: f"{x:.{d}f}"; sg = lambda x, d=3: f"{x:+.{d}f}"
pf = lambda p: "<0.001" if p < 0.001 else f"{p:.3f}"
mean = lambda v: sum(v) / len(v)


def load(path):
    R = [r for r in csv.DictReader(open(path)) if r["split"] == "test"]
    tasks = sorted({r["task"] for r in R}, key=lambda t: (len(t), t)); ix = {t: i for i, t in enumerate(tasks)}
    fam = {r["task"]: r["family"] for r in R}; M = {}
    for r in R: M.setdefault(r["arm"], [None] * len(tasks))[ix[r["task"]]] = float(r["reward"])
    return tasks, [fam[t] for t in tasks], M


def con(Ya, Yb, fam):
    """Ya: list of search rows, Yb: list of rows averaged on the other side."""
    avg = lambda vs: [sum(v[i] for v in vs) / len(vs) for i in range(len(vs[0]))]
    r = pcb.paired_cluster_bootstrap(Ya, [avg(Yb)], fam, B=20)
    o = {"theta": r["theta"], "ci": r["cr_ci"], "p": r["cr_p_two_sided"], "pipe": None, "per_search": r["per_seed"]}
    if len(Ya) >= 2 and r["seed_sd"] is not None:
        se2 = math.sqrt(r["cr_se"] ** 2 + r["seed_sd"] ** 2 / len(Ya)); q = pcb.t_ppf(0.975, len(Ya) - 1); o["pipe"] = (r["theta"] - q * se2, r["theta"] + q * se2)
    return o


def main():
    tasks, fam, M = load(os.path.join(ROOT, "results_long.csv"))
    need = [S1, S2, S3, NAIVE, NONE] + [a for _, a in ABL] + ["seed", "seed-check"]
    miss = [n for n in need if n not in M]
    if miss: raise SystemExit(f"cells missing from results_long.csv: {miss}; present: {sorted(M)}")
    tr = [(dt.datetime.strptime(r["t_start"], "%Y-%m-%dT%H:%M:%SZ").timestamp(), r["arm"], r["task"], float(r["reward"]))
          for r in csv.DictReader(open(os.path.join(ROOT, "results_trials.csv"))) if r["split"] == "test" and r["reward"] != ""]
    t0 = min(x[0] for x in tr); seedt = [x for x in tr if x[1] == "seed"]; mu = {}
    for _, _, k, x in seedt: mu.setdefault(k, []).append(x)
    mu = {k: mean(v) for k, v in mu.items()}; blk = {}
    for t, _, k, x in seedt: blk.setdefault(int((t - t0) // 3600), []).append(x - mu[k])
    keys = sorted(blk); tot = sum(len(v) for v in blk.values()); bmap = {k: k for k in keys}; changed = True
    while changed and len(set(bmap.values())) > 1:   # 5I: blocks with under 5% of the seed trials merge into the neighbouring block
        changed = False; grp = {}
        for k in keys: grp.setdefault(bmap[k], []).append(k)
        order = sorted(grp)
        for i, g in enumerate(order):
            if sum(len(blk[k]) for k in grp[g]) < 0.05 * tot:
                tgt = order[i + 1] if i + 1 < len(order) else order[i - 1]
                for k in grp[g]: bmap[k] = tgt
                changed = True; break
    mb = {}
    for k in keys: mb.setdefault(bmap[k], []).extend(blk[k])
    sd = statistics.pstdev([x for v in mb.values() for x in v]); ms = [(k, mean(v), sd / math.sqrt(len(v)), len(v)) for k, v in sorted(mb.items())]
    rng = max(m[1] for m in ms) - min(m[1] for m in ms); se2 = math.sqrt(sum(m[2] ** 2 for m in ms) / len(ms) * 2); flag = len(ms) > 1 and rng > 2 * se2
    eff = {k: mean(v) for k, v in mb.items()}; acc = {}
    for t, a, k, x in tr:
        hb = int((t - t0) // 3600); acc.setdefault((a, k), []).append(x - (eff.get(bmap.get(hb, hb), 0.0) if flag else 0.0))
    Mb = {a: [mean(acc[(a, k)]) for k in tasks] for a in {a for a, _ in acc}}
    rep = json.load(open(os.path.join(ROOT, "per_arm_report.json")))
    tot_i = {x: sum(v.get(x, 0) for v in rep.values() if isinstance(v, dict)) for x in ("jobs", "done", "infra_attempts", "infra_final", "hangs", "candidate_errors", "retried_jobs", "empty_completion")}
    J = {}
    L = ["# K30 window (addendum 21; one fresh session, 30 trials per champion cell; tau2 airline test-20)", "",
         "Fresh trials reduce trial noise only. The 20 tasks are the same as in every earlier window, each gate and ablation arm is ONE search, and the earlier windows' results for these artifacts are known; nothing is pooled with them. Raw p; Holm only within the stated families.", "",
         f"- infrastructure: {tot_i}",
         "- means: " + ", ".join(f"{n} {f(mean(M[n]))}" for n in [S1, S2, S3, NAIVE, NONE] + [a for _, a in ABL]) + f"; seed {f(mean(M['seed']))}, seed-check {f(mean(M['seed-check']))}",
         "- drift (5I, in-window seed, task-demeaned, hour blocks): " + "; ".join(f"{k}: {sg(m)} (SE {s:.3f}, n={n})" for k, m, s, n in ms) + f". Range {rng:.3f}, SE of difference {se2:.3f}, flag (>2 SE): {flag}." + ("" if len(ms) > 1 else " (one block: not assessable)"), ""]

    def row(name, a, b, fam_tag="", holm=None):
        r = con([M[x] for x in a], [M[x] for x in b], fam)
        J[name] = {"theta": r["theta"], "ci": r["ci"], "p": r["p"], "pipe": r["pipe"], "per_search": r["per_search"], "family": fam_tag}
        ex = ""
        if flag:
            rb = con([Mb[x] for x in a], [Mb[x] for x in b], fam); J[name]["block_adjusted"] = {"theta": rb["theta"], "ci": rb["ci"], "p": rb["p"]}
            ex = f" {sg(rb['theta'])} [{f(rb['ci'][0])}, {f(rb['ci'][1])}] p {pf(rb['p'])} |"
        return name, r, ex
    hdr = "| contrast | delta | 95% CI (artifact, CR1 t19) | raw p | Holm p (family) | " + ("block-adjusted delta [CI] p |" if flag else "")
    sep = "|---|---|---|---|---|" + ("---|" if flag else "")
    fams = [("GATE family (m = 2), vs search 1", [(f"{n} minus search 1", [n], [S1]) for n in (NAIVE, NONE)]),
            ("ABLATION family (m = 5), vs search 1", [(f"{lab} ({a}) minus search 1", [a], [S1]) for lab, a in ABL])]
    allres = {}
    for title, rows in fams:
        for n, a, b in rows: allres[n] = row(n, a, b, title)
    joint = pcb.holm({n: v[1]["p"] for n, v in allres.items()})
    hdr_j = hdr.replace("Holm p (family) |", "Holm p (family) | Holm p (joint, all 7 vs search 1) |"); sep_j = sep.replace("|---|---|---|---|---|", "|---|---|---|---|---|---|", 1)
    for title, rows in fams:
        L += [f"## {title}", "", hdr_j, sep_j]
        adj = pcb.holm({n: allres[n][1]["p"] for n, a, b in rows})
        for n, a, b in rows:
            _, r, ex = allres[n]; J[n]["holm"] = adj[n]; J[n]["holm_joint7"] = joint[n]
            L.append(f"| {n} | {sg(r['theta'])} | [{f(r['ci'][0])}, {f(r['ci'][1])}] | {pf(r['p'])} | {pf(adj[n])} | {pf(joint[n])} |{ex}")
        L.append("")
    L += ["## CapEvolve (m = 1): mean of searches 1, 2, 3 minus the in-window seed", "", hdr + " 95% CI (pipeline, t2) |", sep + "---|"]
    n, r, ex = row("CapEvolve searches 1-3 minus seed", [S1, S2, S3], ["seed"], "CapEvolve")
    L.append(f"| {n} | {sg(r['theta'])} | [{f(r['ci'][0])}, {f(r['ci'][1])}] | {pf(r['p'])} | n/a |{ex} [{f(r['pipe'][0])}, {f(r['pipe'][1])}] |")
    L += ["", "per-search deltas over the seed: " + ", ".join(f"{s} {sg(v)}" for s, v in zip(("search 1", "search 2", "search 3"), r["per_search"])), ""]
    L += ["## Secondary (raw p, no family) and checks", "", hdr, sep]
    sec = [(f"{n} minus seed", [n], ["seed"]) for n in [S1, NAIVE, NONE] + [a for _, a in ABL]] + [("search 2 minus search 1", [S2], [S1]), ("search 3 minus search 1", [S3], [S1]), (f"{NAIVE} minus {NONE}", [NAIVE], [NONE]), ("seed-check minus seed", ["seed-check"], ["seed"])]
    for nm, a, b in sec:
        n, r, ex = row(nm, a, b, "secondary")
        L.append(f"| {n} | {sg(r['theta'])} | [{f(r['ci'][0])}, {f(r['ci'][1])}] | {pf(r['p'])} | n/a |{ex}")
    L += ["", "Planning detectability (80% power, tau 0.15, within-variance 0.1236, tau_int 0.10, 20 tasks): about 0.133 between two single champions at 30 trials (m = 1), 0.149 at m = 2, 0.168 at m = 5; about 0.117 for the three-search mean against the seed. Differences below these are inconclusive."]
    if MROOT:
        _, _, MM = load(os.path.join(MROOT, "results_long.csv"))
        pairs = [("seed", "seed"), ("search 1", "GATE-K2-s0"), ("search 2", "GATE-K2-s1"), ("search 3", "GATE-K2-s3")] + [(lab, a) for lab, a in ABL]
        key = {"seed": "seed", "search 1": S1, "search 2": S2, "search 3": S3}; key.update({lab: a for lab, a in ABL})
        L += ["", "## Session-shift check: K30 minus MERGED for the artifacts scored in both (task-paired; feeds no test, no pooled estimate)", "",
              "| artifact | K30 mean | MERGED mean | K30 minus MERGED [95% CI, CR1 t19] | raw p |", "|---|---|---|---|---|"]
        shifts = []
        for lab, mk in pairs:
            if mk not in MM: continue
            a, b = M[key[lab]], MM[mk]
            r = pcb.paired_cluster_bootstrap([a], [b], fam, B=20); shifts.append(r["theta"]); J["shift " + lab] = {"theta": r["theta"], "ci": r["cr_ci"], "p": r["cr_p_two_sided"]}
            L.append(f"| {lab} | {f(mean(a))} | {f(mean(b))} | {sg(r['theta'])} [{f(r['cr_ci'][0])}, {f(r['cr_ci'][1])}] | {pf(r['cr_p_two_sided'])} |")
        if shifts:
            L += ["", f"Shift across the {len(shifts)} artifacts: mean {sg(mean(shifts))}, range {sg(min(shifts))} to {sg(max(shifts))}. A common shift would put the artifacts close together; a spread much wider than the trial noise of a 10-trial cell (about 0.03 to 0.04 per artifact) means the shift is not common and cross-session pooling is not supported."]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "k30.md"), "w").write("\n".join(L) + "\n"); json.dump(J, open(os.path.join(OUT, "k30.json"), "w"), indent=1, default=str)
    print("\n".join(L))


if __name__ == "__main__":
    main()
