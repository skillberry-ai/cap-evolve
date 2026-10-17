#!/usr/bin/env python3
"""V3B1REJ descriptive analysis (amendment 12 erratum 19; commissioned after the main results were seen).
Rejected vs accepted HC-stock candidates on the held-out test-20, each cell expressed as a delta against its OWN window's seed.
Interval: candidate-level percentile bootstrap stratified by search seed. Per-candidate deltas with artifact-level CR1 CIs.
Exploratory Spearman between the gate's recorded search-time paired delta (and z) and the held-out delta. Pure standard library.
    python3 -I rej_analysis.py OUTDIR
"""
import csv, glob, json, math, os, random, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paired_cluster_bootstrap as pcb
PAPER = os.path.abspath(os.path.join(HERE, "..", ".."))
FE = "/home/dev/projects2/campaign-scratch/final_eval"; B = "/home/dev/projects2/campaign-scratch/runs/V3/B1"
OUT = sys.argv[1]


def load(win):
    R = [r for r in csv.DictReader(open(f"{FE}/{win}/results_long.csv")) if r["split"] == "test"]
    tasks = sorted({r["task"] for r in R}, key=lambda t: (len(t), t)); ix = {t: i for i, t in enumerate(tasks)}
    fam = {r["task"]: r["family"] for r in R}
    M = {}
    for r in R:
        M.setdefault((r["arm"], int(r["seed"])), [None] * len(tasks))[ix[r["task"]]] = float(r["reward"])
    return M, [fam[t] for t in tasks]


def delta(v, ref, fam):
    d = [a - b for a, b in zip(v, ref)]
    r = pcb.paired_cluster_bootstrap([d], [[0.0] * len(d)], fam, B=20)
    return r["theta"], r["cr_ci"]


def ranks(x):
    o = sorted(range(len(x)), key=lambda i: x[i]); r = [0.0] * len(x); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and x[o[j + 1]] == x[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = ranks(x), ranks(y); n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")


def perm_p(x, y, n=20000, seed=1):
    rng = random.Random(seed); obs = abs(spearman(x, y)); y2 = list(y); ge = 0
    for _ in range(n):
        rng.shuffle(y2); ge += abs(spearman(x, y2)) >= obs - 1e-12
    return (ge + 1) / (n + 1)


def f(x, d=3): return f"{x:.{d}f}"
def sg(x, d=3): return f"{x:+.{d}f}"


sys.argv = [sys.argv[0], OUT]
import unblind_analysis as U   # block-adjusted deltas (5I) for the REJ window, whose in-window seed drift is flagged
_WREJ = U.Win("V3B1REJ/main")
_ADJ, _EFF = U.block_adjusted("V3B1REJ/main", _WREJ)
ADJ = {a: (th, ci) for a, th, ci, _ in _ADJ}
Mr, fam = load("V3B1REJ/main"); Mc, famc = load("V3B1CHAIN/main"); Mm, famm = load("V3B1/main")
cells = {(c["search_seed"], c["candidate"]): c for c in json.load(open(os.path.join(PAPER, "experiments/final/manifests/v3_b1_rej_cells.json")))["cells"]}
cand = {}
for k in range(3):
    prev = {}
    for l in open(glob.glob(f"{B}/hcstock/s{k}/**/candidates.jsonl", recursive=True)[0]):
        r = json.loads(l); prev[r["candidate"]] = r
        if "accepted" not in r: continue
        z = None; m = re.search(r"SE=([0-9.]+)", r.get("reason", ""))
        d = r["train_mean"] - r["parent_train_mean"]
        cand[(k, r["candidate"])] = {"accepted": r["accepted"], "gate_delta": d, "gate_z": d / float(m.group(1)) if m else None, "train_mean": r["train_mean"], "rollouts": r["rollouts_cum"]}
final = {k: json.load(open(f"{B}/hcstock/s{k}/run_summary.json"))["champion"] for k in range(3)}
rows = []
for (k, c), info in sorted(cand.items()):
    if (k, c) in cells:
        v, ref, fm, win = Mr[(f"hcstock_s{k}_{c}", 0)], Mr[("seed", 0)], fam, "REJ"
    elif c == final[k]:
        v, ref, fm, win = Mm[("hcstock", k)], Mm[("seed", 0)], famm, "main"
    elif (f"hcstock_s{k}_{c}", 0) in Mc:
        v, ref, fm, win = Mc[(f"hcstock_s{k}_{c}", 0)], Mc[("seed", 0)], famc, "CHAIN"
    else:
        continue
    th, ci = delta(v, ref, fm)
    thadj, ciadj = (ADJ[f"hcstock_s{k}_{c}"] if win == "REJ" else (th, ci))
    rows.append({"seed": k, "cand": c, "window": win, **info, "delta_raw": th, "ci_raw": ci, "delta": thadj, "ci": ciadj})
rej = [r for r in rows if not r["accepted"]]; acc = [r for r in rows if r["accepted"]]
rng = random.Random(20261017)


def boot(B=20000):
    out = []
    for _ in range(B):
        sr, sa = [], []
        for k in range(3):
            xr = [r["delta"] for r in rej if r["seed"] == k]; xa = [r["delta"] for r in acc if r["seed"] == k]
            sr += [rng.choice(xr) for _ in xr]; sa += [rng.choice(xa) for _ in xa]
        out.append(sum(sr) / len(sr) - sum(sa) / len(sa))
    out.sort(); return out[int(.025 * B)], out[int(.975 * B)]


mr = sum(r["delta"] for r in rej) / len(rej); ma = sum(r["delta"] for r in acc) / len(acc)
lo, hi = boot()
L = ["# V3B1REJ: rejected vs accepted HC-stock candidates (descriptive; commissioned after the main results were seen, erratum 19)", "",
     "Each candidate is one cell, expressed as its held-out test-20 delta against the seed of ITS OWN window (REJ, CHAIN or main window; different time blocks). The REJ window's in-window seed drift is flagged (5I: block range 0.269 vs SE of difference 0.072), so the REJ cells use the BLOCK-ADJUSTED delta (the seed's task-demeaned block effects subtracted from every trial); the CHAIN and main windows did not flag and use the plain delta. The unadjusted deltas are in rej_vs_accepted.json (`delta_raw`) and in the summary below. Accepted = the 9 CHAIN intermediates + the 3 final champions; rejected = the 45 REJ cells. One search seed = one stratum.", "",
     "## Rejected minus accepted", "",
     f"- rejected: n = {len(rej)}, mean delta {sg(mr)} (SD {f(math.sqrt(sum((r['delta']-mr)**2 for r in rej)/(len(rej)-1)))})",
     f"- accepted: n = {len(acc)}, mean delta {sg(ma)} (SD {f(math.sqrt(sum((r['delta']-ma)**2 for r in acc)/(len(acc)-1)))})",
     f"- rejected minus accepted: {sg(mr-ma)}, 95% percentile bootstrap over candidates stratified by search seed [{f(lo)}, {f(hi)}] (20,000 draws; treats candidates as exchangeable within a seed, which they are not: candidates share ancestors; the interval is descriptive)", ""]
for k in range(3):
    a = [r["delta"] for r in acc if r["seed"] == k]; b = [r["delta"] for r in rej if r["seed"] == k]
    L.append(f"- seed {k}: accepted n = {len(a)}, mean {sg(sum(a)/len(a))}; rejected n = {len(b)}, mean {sg(sum(b)/len(b))}; difference {sg(sum(b)/len(b)-sum(a)/len(a))}")
L += ["", "Share of candidates above the in-window seed: rejected " + f"{sum(r['delta']>0 for r in rej)}/{len(rej)}, accepted {sum(r['delta']>0 for r in acc)}/{len(acc)}; share whose artifact-level CI excludes 0 (upward): rejected {sum(r['ci'][0]>0 for r in rej)}/{len(rej)}, accepted {sum(r['ci'][0]>0 for r in acc)}/{len(acc)}.", ""]
allr = rej + acc
L += ["## Exploratory: gate score vs held-out delta (Spearman, candidates as units; permutation p, 20,000)", "",
      "| set | n | gate = paired search-time delta (train mean minus parent) | gate z | search-time train mean |", "|---|---|---|---|---|"]
for name, S in (("rejected only", rej), ("accepted only", acc), ("all candidates", allr)):
    y = [r["delta"] for r in S]; x1 = [r["gate_delta"] for r in S]; x2 = [r["gate_z"] for r in S]; x3 = [r["train_mean"] for r in S]
    cell = lambda x: f"rho {sg(spearman(x, y), 2)} (p {perm_p(x, y):.3f})"
    L.append(f"| {name} | {len(S)} | {cell(x1)} | {cell(x2)} | {cell(x3)} |")
L += ["", "## Per candidate", "", "| seed | candidate | status | window | search rollouts | gate paired delta | gate z | held-out delta | 95% CI |", "|---|---|---|---|---|---|---|---|---|"]
for r in sorted(rows, key=lambda r: (r["seed"], r["rollouts"], r["cand"])):
    L.append(f"| {r['seed']} | {r['cand']} | {'accepted' if r['accepted'] else 'rejected'}{' (final)' if r['cand']==final[r['seed']] else ''} | {r['window']} | {r['rollouts']} | {sg(r['gate_delta'])} | {f(r['gate_z'],2) if r['gate_z'] is not None else ''} | {sg(r['delta'])} | [{f(r['ci'][0])}, {f(r['ci'][1])}] |")
mrr = sum(r["delta_raw"] for r in rej) / len(rej); mar = sum(r["delta_raw"] for r in acc) / len(acc)
L += ["", f"Sensitivity, unadjusted deltas: rejected {sg(mrr)}, accepted {sg(mar)}, difference {sg(mrr-mar)}; REJ-window block effects of the in-window seed (hour blocks from the window start): {_EFF}."]
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "rej_vs_accepted.md"), "w").write("\n".join(L) + "\n")
json.dump(rows, open(os.path.join(OUT, "rej_vs_accepted.json"), "w"), indent=1, default=str)
print("\n".join(L[:30]))
