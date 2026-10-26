#!/usr/bin/env python3
"""K02R follow-up analysis (amendment 12 addendum 19, erratum 74). Written BEFORE the data exist. Exploratory; not for the paper unless a later addendum says so.

Cells expected in results_long.csv / results_trials.csv (one shared window, one session, test-20): K02R-s1, K02R-s2, K02R-s3 (stock gate k = 0.2, new search seeds),
K02 (cand_0011, the search that triggered the follow-up), GATE-NAIVE (accept if mean paired delta >= 0), GATE-NONE (accept every decisive candidate),
GATE-K2-search1 (reference), seed (n = 20), seed-check (k = 10).
Outputs:
  PRIMARY (one quantity): K02R-s1..s3 (fresh stock-gate searches) minus the in-window seed. Artifact-level CR1 t(19) on the seed-averaged score and pipeline-level t(S-1)
          with SE^2 = SE_task^2 + s_seed^2/S, S = 3. The triggering search K02 is NOT in the primary: it was run first and its result decided whether the others ran.
  SENSITIVITY: the same with K02 included (S = 4) and with each search alone.
  GATE CONTRASTS (exploratory, raw p, no family): GATE-NAIVE minus seed; GATE-NONE minus seed; each minus the mean of the stock searches K02R-s1..s3 (task-paired; one search per
          gate arm, so the interval carries no search-to-search variation for that arm); GATE-NAIVE minus GATE-NONE.
  CHECKS: K2 search 1 minus seed (window check), seed-check minus seed, the 5I drift check with block-adjusted deltas when it flags, infra counts.
Pure standard library.   python3 -I k02r_analysis.py OUTDIR RESULTS_ROOT
"""
import csv, datetime as dt, json, math, os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paired_cluster_bootstrap as pcb

OUT, ROOT = sys.argv[1], sys.argv[2]
STOCK = ["K02R-s1", "K02R-s2", "K02R-s3"]; TRIG = "K02"; NAIVE = "GATE-NAIVE"; NONE = "GATE-NONE"; REF = "GATE-K2-search1"
f = lambda x, d=3: f"{x:.{d}f}"; sg = lambda x, d=3: f"{x:+.{d}f}"
pf = lambda p: "<0.001" if p < 0.001 else f"{p:.3f}"


def load(path):
    R = [r for r in csv.DictReader(open(path)) if r["split"] == "test"]
    tasks = sorted({r["task"] for r in R}, key=lambda t: (len(t), t)); ix = {t: i for i, t in enumerate(tasks)}
    fam = {r["task"]: r["family"] for r in R}; M = {}
    for r in R: M.setdefault(r["arm"], [None] * len(tasks))[ix[r["task"]]] = float(r["reward"])
    return tasks, [fam[t] for t in tasks], M


def avg(vs): return [sum(v[i] for v in vs) / len(vs) for i in range(len(vs[0]))]
mean = lambda v: sum(v) / len(v)


def contrast(Ya, Yb, fam):
    """Ya: list of search rows, Yb: list of rows averaged on the other side. Artifact-level CR1 t(19); pipeline-level t(S-1) over the Ya side only."""
    r = pcb.paired_cluster_bootstrap(Ya, [avg(Yb)], fam, B=20)
    o = {"theta": r["theta"], "ci": r["cr_ci"], "p": r["cr_p_two_sided"], "per_seed": r["per_seed"], "pipe": None}
    if len(Ya) >= 2 and r["seed_sd"] is not None:
        se2 = math.sqrt(r["cr_se"] ** 2 + r["seed_sd"] ** 2 / len(Ya)); q = pcb.t_ppf(0.975, len(Ya) - 1); o["pipe"] = (r["theta"] - q * se2, r["theta"] + q * se2)
    return o


def main():
    tasks, fam, M = load(os.path.join(ROOT, "results_long.csv"))
    for need in STOCK + [TRIG, NAIVE, NONE, REF, "seed", "seed-check"]:
        if need not in M: raise SystemExit(f"cell {need!r} missing from results_long.csv; cells present: {sorted(M)}")
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
    rng = max(m[1] for m in ms) - min(m[1] for m in ms); se2 = math.sqrt(sum(m[2] ** 2 for m in ms) / len(ms) * 2); flag = rng > 2 * se2
    eff = {k: mean(v) for k, v in mb.items()}; acc = {}
    for t, a, k, x in tr:
        hb = int((t - t0) // 3600); acc.setdefault((a, k), []).append(x - (eff.get(bmap.get(hb, hb), 0.0) if flag else 0.0))
    Mb = {a: [mean(acc[(a, k)]) for k in tasks] for a in {a for a, _ in acc}}
    rep = json.load(open(os.path.join(ROOT, "per_arm_report.json")))
    tot_i = {x: sum(v.get(x, 0) for v in rep.values() if isinstance(v, dict)) for x in ("jobs", "done", "infra_attempts", "infra_final", "hangs", "candidate_errors")}
    J = {}; L = ["# K02R follow-up window (addendum 19; exploratory; not for the paper unless a later addendum says so)", "",
                 "One search per arm except the stock gate (three fresh searches); the gate arms differ from the stock arms only in the gate_override switch and the stated seed. No claim about the method in general.", "",
                 f"- infrastructure: {tot_i}", "- means: " + ", ".join(f"{a} {f(mean(M[a]))}" for a in STOCK + [TRIG, NAIVE, NONE, REF]) + f"; seed {f(mean(M['seed']))} (n = 20), seed-check {f(mean(M['seed-check']))} (k = 10)",
                 "- drift (5I, in-window seed, task-demeaned, hour blocks): " + "; ".join(f"{k}: {sg(m)} (SE {s:.3f}, n={n})" for k, m, s, n in ms) + f". Range {rng:.3f}, SE of difference {se2:.3f}, flag (>2 SE): {flag}.", ""]
    rows = [("PRIMARY: fresh stock-gate searches K02R-s1..s3 minus seed", [M[a] for a in STOCK], [M["seed"]], [Mb[a] for a in STOCK], [Mb["seed"]]),
            ("sensitivity: with K02 (4 searches) minus seed", [M[a] for a in STOCK + [TRIG]], [M["seed"]], [Mb[a] for a in STOCK + [TRIG]], [Mb["seed"]])]
    rows += [(f"{a} alone minus seed", [M[a]], [M["seed"]], [Mb[a]], [Mb["seed"]]) for a in STOCK + [TRIG]]
    rows += [(f"{g} minus seed", [M[g]], [M["seed"]], [Mb[g]], [Mb["seed"]]) for g in (NAIVE, NONE)]
    rows += [(f"{g} minus the mean of K02R-s1..s3 (task-paired)", [M[g]], [M[a] for a in STOCK], [Mb[g]], [Mb[a] for a in STOCK]) for g in (NAIVE, NONE)]
    rows += [(f"{NAIVE} minus {NONE}", [M[NAIVE]], [M[NONE]], [Mb[NAIVE]], [Mb[NONE]]),
             (f"{REF} minus seed (window check)", [M[REF]], [M["seed"]], [Mb[REF]], [Mb["seed"]]), ("seed-check minus seed", [M["seed-check"]], [M["seed"]], [Mb["seed-check"]], [Mb["seed"]])]
    L += ["| contrast | delta | 95% CI (artifact, CR1 t19) | raw p | 95% CI (pipeline, t S-1; stock side only) | " + ("block-adjusted delta [CI] p |" if flag else ""), "|---|---|---|---|---|" + ("---|" if flag else "")]
    for name, a, b, ab, bb in rows:
        r = contrast(a, b, fam); J[name] = {"theta": r["theta"], "ci": r["ci"], "p": r["p"], "pipe": r["pipe"], "per_seed": r["per_seed"]}
        pipe = f"[{f(r['pipe'][0])}, {f(r['pipe'][1])}]" if r["pipe"] else "n/a"; ex = ""
        if flag:
            rb = contrast(ab, bb, fam); ex = f" {sg(rb['theta'])} [{f(rb['ci'][0])}, {f(rb['ci'][1])}] p {pf(rb['p'])} |"
        L.append(f"| {name} | {sg(r['theta'])} | [{f(r['ci'][0])}, {f(r['ci'][1])}] | {pf(r['p'])} | {pipe} |{ex}")
    L += ["", "Planning detectability (80% power, within-variance 0.1236, tau 0.15): 0.149 against the seed at n = 20; 0.158 against another single champion. Differences below these are inconclusive. Per-search deltas are in the JSON."]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "k02r.md"), "w").write("\n".join(L) + "\n"); json.dump(J, open(os.path.join(OUT, "k02r.json"), "w"), indent=1, default=str)
    print("\n".join(L))


if __name__ == "__main__":
    main()
