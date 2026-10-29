#!/usr/bin/env python3
"""Family 1 analysis (amendment 12 addendum 28 to 31): 2x2 executable recipe vs prose inside frozen champions s0 and s3, tau2 test-20.
Written BEFORE any family-1 arm has an outcome. Exploratory prospective measurement of a retrospective hypothesis.

Cells (arm labels of the order): E1X-s0-{both,code,prose,base}, E1X-s3-{both,code,prose,base}, seed (= E1X-seed), optional seed-check (integrity only).
Per task t, champion c, outcome y in {reward, steps}: Y_c,cell(t) = mean over the cell's valid trials.
  reward: all trials; infra_final rows count 0 (primary rule, as everywhere in the campaign).
  steps (decision steps = n_llm_calls - 1, agent side, from raw/rollouts.jsonl): infra_final rows are EXCLUDED (no completed episode).
Interaction per champion: I_c(t) = Y_both - Y_prose - Y_code + Y_base. PRIMARY: I(t) = mean of I_c(t) over the champions present (2); inference: one-sample t(19)
on the 20 task values (= CR1 t with one observation per task cluster), 95% interval. Champions are also reported separately (descriptive).
Descriptive: main effects code-base, prose-base, both-base, both-code, both-prose; each arm minus the in-window seed; drift of seed (+ seed-check if present).
Multiplicity: Holm over the confirmatory family = interaction on reward and on steps (m = 2; the AppWorld run, if any, is a separate invocation and
the joint Holm over m = 4 is applied by the reviewer when both exist). Raw p printed beside. No pipeline-level statement exists (two frozen artifacts).
    python3 -I fam1_analysis.py OUTDIR RESULTS_ROOT
RESULTS_ROOT holds results_trials.csv and raw/rollouts.jsonl. Holm here is over m = 2 (reward, steps); if an AppWorld result exists the reviewer applies the joint Holm over m = 4 by hand from the raw p.
"""
import csv, json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from collections import defaultdict
OUT, ROOT = sys.argv[1:3]; M = 2
import paired_cluster_bootstrap as pcb                  # registered; pure-standard-library t quantile and cdf
tcrit = lambda df: pcb.t_ppf(0.975, df); tp = lambda t, df: 2 * (1 - pcb._t_cdf(abs(t), df))
CH = ["s0", "s3"]; CELLS = ["both", "code", "prose", "base"]
rows = list(csv.DictReader(open(os.path.join(ROOT, "results_trials.csv"))))
llm = {}
for l in open(os.path.join(ROOT, "raw", "rollouts.jsonl")):
    j = json.loads(l)
    if j.get("terminal") and j.get("final_status") == "done": llm[j["job_id"]] = j.get("n_llm_calls")
R = defaultdict(lambda: defaultdict(list)); S = defaultdict(lambda: defaultdict(list)); infra = defaultdict(int)
for x in rows:
    arm, t = x["arm"], str(x["task"])
    if x.get("infra_final") in ("1", "True", "true"): infra[arm] += 1; r = 0.0
    else: r = float(x["reward"])
    R[arm][t].append(r)
    if x.get("infra_final") not in ("1", "True", "true") and llm.get(x["job_id"]) is not None: S[arm][t].append(float(llm[x["job_id"]]) - 1)
tasks = sorted({t for a in R for t in R[a]}, key=lambda s: (len(s), s))
mean = lambda v: sum(v) / len(v)
def Y(D, arm): return [mean(D[arm][t]) if D[arm].get(t) else float("nan") for t in tasks]
def one(v):
    v = [a for a in v if a == a]; n = len(v); m = mean(v); sd = math.sqrt(sum((a - m) ** 2 for a in v) / (n - 1)); se = sd / math.sqrt(n)
    tt = m / se if se > 0 else 0.0; c = tcrit(n - 1)
    return dict(est=m, lo=m - c * se, hi=m + c * se, se=se, p=tp(tt, n - 1) if se > 0 else 1.0, n=n)
def holm(ps):
    o = sorted(range(len(ps)), key=lambda i: ps[i]); out = [0] * len(ps); run = 0
    for k, i in enumerate(o): run = max(run, (len(ps) - k) * ps[i]); out[i] = min(1, run)
    return out
def comb(f, D, ch, wt=None): return [f(*[Y(D, f"E1X-{c}-{k}") for k in CELLS]) for c in ch]
res = {}; lines = ["# Family 1 (2x2 recipe vs prose), tau2 test-20: results (exploratory, prospective measurement of a retrospective hypothesis)", ""]
champs = [c for c in CH if all(f"E1X-{c}-{k}" in R for k in CELLS)]
lines.append(f"champions present: {champs}; tasks: {len(tasks)}; infra_final rows by arm: {dict(infra)}"); lines.append("")
prim = []
for oname, D in (("reward", R), ("steps", S)):
    inter = {}
    for c in champs:
        b, co, pr, ba = [Y(D, f"E1X-{c}-{k}") for k in CELLS]
        inter[c] = [b[i] - pr[i] - co[i] + ba[i] for i in range(len(tasks))]
    I = [mean([inter[c][i] for c in champs]) for i in range(len(tasks))]
    res[oname] = dict(primary=one(I), per_champion={c: one(inter[c]) for c in champs}, effects={})
    prim.append(res[oname]["primary"]["p"])
    names = {"code-base": lambda b, co, pr, ba: [co[i] - ba[i] for i in range(len(b))], "prose-base": lambda b, co, pr, ba: [pr[i] - ba[i] for i in range(len(b))],
             "both-base": lambda b, co, pr, ba: [b[i] - ba[i] for i in range(len(b))], "both-code": lambda b, co, pr, ba: [b[i] - co[i] for i in range(len(b))],
             "both-prose": lambda b, co, pr, ba: [b[i] - pr[i] for i in range(len(b))]}
    for nm, fn in names.items():
        per = {c: fn(*[Y(D, f"E1X-{c}-{k}") for k in CELLS]) for c in champs}
        res[oname]["effects"][nm] = dict(mean=one([mean([per[c][i] for c in champs]) for i in range(len(tasks))]), per_champion={c: one(per[c]) for c in champs})
    if "seed" in D:
        sd = Y(D, "seed"); res[oname]["vs_seed"] = {f"{c}-{k}": one([a - b for a, b in zip(Y(D, f"E1X-{c}-{k}"), sd)]) for c in champs for k in CELLS}
        res[oname]["seed_mean"] = mean([a for a in sd if a == a])
        if "seed-check" in D: res[oname]["seedcheck_minus_seed"] = one([a - b for a, b in zip(Y(D, "seed-check"), sd)])
h = holm(prim)
for (oname, _), hp in zip((("reward", R), ("steps", S)), h): res[oname]["primary"]["holm_m2"] = hp
f3 = lambda x: f"{x:+.3f}"
for oname in ("reward", "steps"):
    r = res[oname]; p = r["primary"]
    lines += [f"## {oname}", f"PRIMARY interaction I = both - prose - code + base (mean of {len(champs)} champions): {f3(p['est'])} [{f3(p['lo'])}, {f3(p['hi'])}] raw p {p['p']:.4f}, Holm (m=2) {p['holm_m2']:.4f}; t({p['n']-1}); artifact-level only (two frozen artifacts)"]
    for c, v in r["per_champion"].items(): lines.append(f"  champion {c}: {f3(v['est'])} [{f3(v['lo'])}, {f3(v['hi'])}] raw p {v['p']:.4f}")
    lines.append("main effects (descriptive, raw p):")
    for nm, v in r["effects"].items(): lines.append(f"  {nm}: {f3(v['mean']['est'])} [{f3(v['mean']['lo'])}, {f3(v['mean']['hi'])}] p {v['mean']['p']:.4f}; " + "; ".join(f"{c} {f3(w['est'])}" for c, w in v["per_champion"].items()))
    if "vs_seed" in r:
        lines.append(f"in-window seed mean {r['seed_mean']:.3f}; arm minus seed: " + "; ".join(f"{k} {f3(v['est'])}" for k, v in r["vs_seed"].items()))
        if "seedcheck_minus_seed" in r: v = r["seedcheck_minus_seed"]; lines.append(f"seed-check minus seed {f3(v['est'])} [{f3(v['lo'])}, {f3(v['hi'])}] p {v['p']:.3f}")
    lines.append("")
os.makedirs(OUT, exist_ok=True); json.dump(res, open(os.path.join(OUT, "fam1.json"), "w"), indent=1); open(os.path.join(OUT, "fam1.md"), "w").write("\n".join(lines))
print("\n".join(lines))
