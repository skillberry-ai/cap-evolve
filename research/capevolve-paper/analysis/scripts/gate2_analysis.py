#!/usr/bin/env python3
"""GATE2 window analysis (amendment 12 addendum 20, erratum 75), a variant of k02_analysis.py. Written BEFORE the data exist. Exploratory.

Cells expected: GATE-NAIVE-K2, GATE-NONE-K2 (the two gate-ablation champions), GATE-K2-search1 (K2 search 1 re-scored in this window), 'seed' (n = 20),
'seed-check' (k = 10), all on the 20 test tasks.
Outputs: PRIMARY (exploratory, raw p): each gate arm minus K2 search 1, task-paired; each gate arm minus the seed; NAIVE minus NONE; K2 search 1 minus the seed (window check); seed-check minus seed; (4) the 5I drift check with block-adjusted deltas beside the plain ones when it flags. Artifact-level CR1 t(19), raw p only.
One search per arm: no pipeline-level interval; each arm differs from K2 search 1 only in the gate rule. Pure standard library.
    python3 -I gate2_analysis.py OUTDIR RESULTS_ROOT
"""
import csv, datetime as dt, json, math, os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paired_cluster_bootstrap as pcb

OUT, ROOT = sys.argv[1], sys.argv[2]
NAIVE, NONE, REF = "GATE-NAIVE-K2", "GATE-NONE-K2", "GATE-K2-search1"; NEW = NAIVE
f = lambda x, d=3: f"{x:.{d}f}"; sg = lambda x, d=3: f"{x:+.{d}f}"
pf = lambda p: "<0.001" if p < 0.001 else f"{p:.3f}"


def load(path):
    R = [r for r in csv.DictReader(open(path)) if r["split"] == "test"]
    tasks = sorted({r["task"] for r in R}, key=lambda t: (len(t), t)); ix = {t: i for i, t in enumerate(tasks)}
    fam = {r["task"]: r["family"] for r in R}
    M = {}
    for r in R:
        M.setdefault(r["arm"], [None] * len(tasks))[ix[r["task"]]] = float(r["reward"])
    return tasks, [fam[t] for t in tasks], M


def dlt(a, b, fam):
    r = pcb.paired_cluster_bootstrap([a], [b], fam, B=20)
    return r["theta"], r["cr_ci"], r["cr_p_two_sided"]


def main():
    tasks, fam, M = load(os.path.join(ROOT, "results_long.csv"))
    for need in (NAIVE, NONE, "seed", "seed-check", REF):
        if need not in M: raise SystemExit(f"cell {need!r} missing from results_long.csv; cells present: {sorted(M)}")
    tr = [(dt.datetime.strptime(r["t_start"], "%Y-%m-%dT%H:%M:%SZ").timestamp(), r["arm"], r["task"], float(r["reward"]))
          for r in csv.DictReader(open(os.path.join(ROOT, "results_trials.csv"))) if r["split"] == "test" and r["reward"] != ""]
    t0 = min(x[0] for x in tr); seedt = [x for x in tr if x[1] == "seed"]
    mu = {}
    for _, _, k, x in seedt: mu.setdefault(k, []).append(x)
    mu = {k: sum(v) / len(v) for k, v in mu.items()}; blk = {}
    for t, _, k, x in seedt: blk.setdefault(int((t - t0) // 3600), []).append(x - mu[k])
    # 5I: blocks with fewer than 5% of the seed trials are merged into the neighbouring block
    keys = sorted(blk); tot = sum(len(v) for v in blk.values()); bmap = {k: k for k in keys}; changed = True
    while changed and len(set(bmap.values())) > 1:
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
    sd = statistics.pstdev([x for v in mb.values() for x in v])
    ms = [(k, sum(v) / len(v), sd / math.sqrt(len(v)), len(v)) for k, v in sorted(mb.items())]
    rng = max(m[1] for m in ms) - min(m[1] for m in ms); se2 = math.sqrt(sum(m[2] ** 2 for m in ms) / len(ms) * 2); flag = rng > 2 * se2
    eff = {k: sum(v) / len(v) for k, v in mb.items()}
    acc = {}
    for t, a, k, x in tr:
        hb = int((t - t0) // 3600); acc.setdefault((a, k), []).append(x - (eff.get(bmap.get(hb, hb), 0.0) if flag else 0.0))
    Mb = {a: [sum(acc[(a, k)]) / len(acc[(a, k)]) for k in tasks] for a in {a for a, _ in acc}}
    mean = lambda v: sum(v) / len(v)
    L = ["# GATE2 window (addendum 20; exploratory)", "",
         "One search per arm; each gate arm differs from K2 search 1 only in the gate rule (naive: accept iff the mean paired delta is >= 0; none: accept every decisive scored candidate). No pipeline-level interval; no claim about the gate in general. Raw p only.", "",
         f"- means: {NAIVE} {f(mean(M[NAIVE]))}, {NONE} {f(mean(M[NONE]))}, {REF} {f(mean(M[REF]))}, seed {f(mean(M['seed']))} (n = 20), seed-check {f(mean(M['seed-check']))} (k = 10)",
         "- drift (5I, in-window seed, task-demeaned, hour blocks): " + "; ".join(f"{k}: {sg(m)} (SE {s:.3f}, n={n})" for k, m, s, n in ms) + f". Range {rng:.3f}, SE of difference {se2:.3f}, flag (>2 SE): {flag}.", ""]
    rows = [(f"PRIMARY: {NAIVE} minus {REF} (task-paired)", NAIVE, REF), (f"PRIMARY: {NONE} minus {REF} (task-paired)", NONE, REF),
            (f"{NAIVE} minus seed", NAIVE, "seed"), (f"{NONE} minus seed", NONE, "seed"), (f"{NAIVE} minus {NONE}", NAIVE, NONE),
            (f"{REF} minus seed (window check; earlier windows +0.145, +0.130, +0.130, +0.113, +0.153)", REF, "seed"), ("seed-check minus seed", "seed-check", "seed")]
    L += ["| contrast | delta | 95% CI (artifact, CR1 t19) | raw p | " + ("block-adjusted delta [CI] p |" if flag else ""), "|---|---|---|---|" + ("---|" if flag else "")]
    out = {}
    for name, a, b in rows:
        th, ci, p = dlt(M[a], M[b], fam); out[name] = {"theta": th, "ci": ci, "p": p}
        ex = ""
        if flag:
            tb, cb, pb = dlt(Mb[a], Mb[b], fam); ex = f" {sg(tb)} [{f(cb[0])}, {f(cb[1])}] p {pf(pb)} |"
        L.append(f"| {name} | {sg(th)} | [{f(ci[0])}, {f(ci[1])}] | {pf(p)} |{ex}")
    L += ["", "Planning detectability (80% power, within-variance 0.1236, tau 0.15): 0.149 against the seed at n = 20; 0.158 against another single champion. Differences below these are inconclusive."]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "gate2.md"), "w").write("\n".join(L) + "\n"); json.dump(out, open(os.path.join(OUT, "gate2.json"), "w"), indent=1, default=str)
    print("\n".join(L))


if __name__ == "__main__":
    main()
