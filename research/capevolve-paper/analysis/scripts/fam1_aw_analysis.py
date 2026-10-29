#!/usr/bin/env python3
"""Family 1, AppWorld part (AWX; addenda 28-31, erratum 150). Written and registered BEFORE any AWX record outcome is read. Exploratory prospective measurement of a retrospective hypothesis.
Cells: arms both, code, prose, base (the 2x2 inside the frozen champion cape_k02) and seed (session anchor, outside the 2x2); 30 tasks in 30 scenarios x 3 trials. Records: STATE/records/*.json.
Outcomes per record: success (TGC), n_steps (decision steps). Per-task cell mean over the 3 trials; infra records (error_kind == 'infra') count success 0 and are EXCLUDED from steps.
Unit/cluster: scenario (= task here: one task per scenario, 30 clusters). INTERACTION I = both - prose - code + base per task. Inference: scenario-clustered paired bootstrap of the mean of I, B = 10,000 resamples of the 30 scenarios,
numpy default_rng(20261029) integers; 95% interval = 2.5 / 97.5 percentiles; two-sided p = min(1, 2 * (min(#{b <= 0}, #{b >= 0}) + 1) / (B + 1)). Registered primary = I on TGC and I on n_steps; the joint Holm over m = 4 is applied
with the two tau2 raw p of erratum 148 (reward 0.3229, steps 0.2994) passed on the command line. Descriptive: cell means, main effects, code - prose (post hoc), the spillover split (triggered vs non-triggered tasks from subset.json), helper-call counts are in fam1_aw_helpers.py.
    python3 -I fam1_aw_analysis.py OUTDIR STATE_DIR SUBSET_JSON TAU2_P_REWARD TAU2_P_STEPS   (numpy required: run WITHOUT -I if numpy is not on the isolated path)"""
import glob, json, os, sys
import numpy as np
OUT, STATE, SUBSET, P_R, P_S = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
B = 10000; ARMS = ["both", "code", "prose", "base", "seed"]
R = [json.load(open(f)) for f in glob.glob(os.path.join(STATE, "records", "*.json"))]
sub = json.load(open(SUBSET)); chosen = sorted(sub["chosen"]); trig = {t for t, w in sub["chosen_trigger_words"].items() if w}; non = [t for t in chosen if t not in trig]      # triggered = at least one trigger word in the task text (subset.json chosen_trigger_words)
D = {a: {t: {"succ": [], "steps": []} for t in chosen} for a in ARMS}
for r in R:
    a, t = r["arm"], r["task_id"]; inf = r.get("error_kind") == "infra"
    D[a][t]["succ"].append(0.0 if inf else float(bool(r["success"])))
    if not inf: D[a][t]["steps"].append(float(r["n_steps"]))
def Y(a, q): return np.array([np.mean(D[a][t][q]) if D[a][t][q] else np.nan for t in chosen])
rng = np.random.default_rng(20261029); idx = rng.integers(0, len(chosen), size=(B, len(chosen)))
def boot(v):
    v = np.asarray(v); m = ~np.isnan(v); vv = np.where(m, v, 0.0); w = m.astype(float)
    bs = (vv[idx] * w[idx]).sum(1) / np.maximum(w[idx].sum(1), 1)
    est = vv.sum() / w.sum(); n0 = min((bs <= 0).sum(), (bs >= 0).sum())
    return dict(est=float(est), lo=float(np.percentile(bs, 2.5)), hi=float(np.percentile(bs, 97.5)), p=float(min(1.0, 2 * (n0 + 1) / (B + 1))))
def holm(ps):
    o = sorted(range(len(ps)), key=lambda i: ps[i]); m = len(ps); out = [0] * m; run = 0
    for k, i in enumerate(o): run = max(run, (m - k) * ps[i]); out[i] = min(1.0, run)
    return out
res = {}; L = ["# Family 1, AppWorld part (AWX): registered results (exploratory prospective measurement of a retrospective hypothesis)", ""]
L.append(f"records: {len(R)}; infra records: {sum(1 for r in R if r.get('error_kind')=='infra')}; tasks {len(chosen)} (triggered {len(chosen)-len(non)}, non-triggered spillover control {len(non)}); trials per cell-task: {sorted({len(D[a][t]['succ']) for a in ARMS for t in chosen})}")
for q, nm in (("succ", "TGC"), ("steps", "decision steps")):
    b, c, p, ba = [Y(a, q) for a in ("both", "code", "prose", "base")]
    I = b - p - c + ba; res[nm] = dict(I=boot(I), cells={a: float(np.nanmean(Y(a, q))) for a in ARMS})
    res[nm]["effects"] = {k: boot(v) for k, v in (("code-base", c - ba), ("prose-base", p - ba), ("both-base", b - ba), ("both-code", b - c), ("both-prose", b - p), ("code-prose (POST HOC)", c - p))}
    res[nm]["vs_seed"] = {a: boot(Y(a, q) - Y("seed", q)) for a in ("both", "code", "prose", "base")}
    if non:
        mk = np.array([t in non for t in chosen]); res[nm]["spillover"] = dict(I_non=float(np.nanmean(I[mk])), I_trig=float(np.nanmean(I[~mk])), n_non=int(mk.sum()))
hp = holm([res["TGC"]["I"]["p"], res["decision steps"]["I"]["p"], P_R, P_S])
res["TGC"]["I"]["holm_m4"] = hp[0]; res["decision steps"]["I"]["holm_m4"] = hp[1]
f = lambda x: f"{x:+.3f}"
for nm in ("TGC", "decision steps"):
    r = res[nm]; i = r["I"]
    L += ["", f"## {nm}", "cell means: " + ", ".join(f"{a} {v:.3f}" for a, v in r["cells"].items()),
          f"PRIMARY interaction I = both - prose - code + base: {f(i['est'])} [{f(i['lo'])}, {f(i['hi'])}] raw p {i['p']:.4f}, Holm (m=4 with tau2 reward {P_R} and steps {P_S}) {i['holm_m4']:.4f}; scenario bootstrap, B={B}, 30 clusters"]
    L.append("main effects (descriptive, raw p): " + "; ".join(f"{k} {f(v['est'])} [{f(v['lo'])}, {f(v['hi'])}] p {v['p']:.4f}" for k, v in r["effects"].items()))
    L.append("arm minus seed: " + "; ".join(f"{k} {f(v['est'])} [{f(v['lo'])}, {f(v['hi'])}]" for k, v in r["vs_seed"].items()))
    if "spillover" in r: L.append(f"interaction by task type (descriptive): triggered {f(r['spillover']['I_trig'])}, non-triggered ({r['spillover']['n_non']} tasks) {f(r['spillover']['I_non'])}")
os.makedirs(OUT, exist_ok=True); json.dump(res, open(os.path.join(OUT, "fam1_aw.json"), "w"), indent=1); open(os.path.join(OUT, "fam1_aw.md"), "w").write("\n".join(L)); print("\n".join(L))
