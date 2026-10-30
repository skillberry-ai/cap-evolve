#!/usr/bin/env python3
"""Family 4 (F4) analysis (addendum 34, erratum 175). Written and registered BEFORE any F4 outcome is read. Confirmatory replication of the tool-versus-prose contrast on new frozen tau2 champions.
Cells: F4-<tag>-{code,prose_A,prose_B,prose_C,base} for tags nk2s0, k165s0, k165s1, k165s2; seed; seed-check. 10 trials per task per cell, 20 test tasks. infra_final rows count 0 for reward and are excluded from steps.
D_cj = Y_code(c,j) - mean over drafts d of Y_prose_d(c,j), Y = mean reward over the cell's trials. PRIMARY (m = 1): pooled mean of D_cj over 20 tasks and the champions present.
INTERVALS (both reported, both required for 'detected'; erratum/addendum 34): (i) two-level percentile bootstrap, 10,000 reps, numpy default_rng(20261030): resample champions with replacement, then tasks within each sampled champion;
(ii) one-sample t over the champion means of D (df = champions - 1). Descriptive/secondary: decision steps (n_llm_calls - 1), seed-tool calls, pass^5 (per task C(c,5)/C(10,5)), draft-to-draft spread (SD over the three drafts of each draft's champion-mean reward, and the
three pairwise differences), code - base and prose_d - base per champion, per-champion D with a task-level t(19) interval, a leave-one-champion-out table of the pooled D, and prompt tokens. No other test.
    python3 -I fam4_analysis.py OUTDIR RESULTS_ROOT   (numpy required: run WITHOUT -I if numpy is not on the isolated path)"""
import csv, json, math, os, sys
from collections import defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paired_cluster_bootstrap as pcb
OUT, ROOT = sys.argv[1:3]; B = 10000
SEEDP = ("book_reservation", "calculate", "cancel_reservation", "get_reservation_details", "get_user_details", "list_all_airports", "search_direct_flight", "search_onestop_flight", "send_certificate", "transfer_to_human_agents", "update_reservation_baggages", "update_reservation_flights", "update_reservation_passengers", "get_flight_status")
TAGS_ALL = ["nk2s0", "k165s0", "k165s1", "k165s2"]; DR = ["A", "B", "C"]
rows = list(csv.DictReader(open(os.path.join(ROOT, "results_trials.csv")))); dirs = {}; llm = {}
for l in open(os.path.join(ROOT, "raw", "rollouts.jsonl")):
    j = json.loads(l); dirs[j["job_id"]] = j["attempt_dir"]; llm[j["job_id"]] = j.get("n_llm_calls")
Q = defaultdict(lambda: defaultdict(list)); infra = defaultdict(int)
for x in rows:
    a, t = x["arm"], str(x["task"]); inf = x.get("infra_final") in ("1", "True", "true"); infra[a] += inf
    r = 0.0 if inf else float(x["reward"]); Q[(a, "reward")][t].append(r); Q[(a, "succ")][t].append(1.0 if r == 1.0 else 0.0)
    if not inf and llm.get(x["job_id"]) is not None:
        Q[(a, "steps")][t].append(llm[x["job_id"]] - 1)
        try:
            tr = json.load(open(os.path.join(dirs[x["job_id"]], "trace.json"))); asst = [m for m in tr if m.get("role") == "assistant"]
            Q[(a, "seedp")][t].append(sum(1 for m in asst for c in (m.get("tool_calls") or []) if c.get("name") in SEEDP))
            Q[(a, "ptok")][t].append(sum(((m.get("usage") or {}).get("prompt_tokens") or 0) for m in asst if m.get("usage")))
        except Exception: pass
tasks = sorted({t for k in Q for t in Q[k]}, key=lambda s: (len(s), s)); mean = lambda v: sum(v) / len(v)
tags = [g for g in TAGS_ALL if all(f"F4-{g}-{k}" in {a for a, _ in Q} for k in ["code", "prose_A", "prose_B", "prose_C", "base"])]
def Y(a, q): return np.array([mean(Q[(a, q)][t]) if Q[(a, q)].get(t) else np.nan for t in tasks])
def pk(a, k=5):
    return np.array([math.comb(sum(1 for r in Q[(a, "succ")][t] if r == 1.0), k) / math.comb(len(Q[(a, "succ")][t]), k) for t in tasks])
def one(v):
    v = np.asarray(v, float); v = v[~np.isnan(v)]; n = len(v); m = v.mean(); sd = v.std(ddof=1); se = sd / math.sqrt(n); c = pcb.t_ppf(.975, n - 1)
    return dict(est=float(m), lo=float(m - c * se), hi=float(m + c * se), p=float(2 * (1 - pcb._t_cdf(abs(m / se), n - 1))) if se > 0 else 1.0, n=n)
def D_matrix(q):             # champions x tasks
    f = (lambda a: pk(a)) if q == "pk5" else (lambda a: Y(a, q))
    return np.array([f(f"F4-{g}-code") - np.mean([f(f"F4-{g}-prose_{d}") for d in DR], axis=0) for g in tags])
rng = np.random.default_rng(20261030)
def two_level(Dm, reps=B):
    C, T = Dm.shape; out = np.empty(reps)
    for b in range(reps):
        ci = rng.integers(0, C, C); out[b] = np.mean([Dm[c][rng.integers(0, T, T)].mean() for c in ci])
    return out
res = {}; L = ["# Family 4 (F4): registered results (confirmatory replication of tool versus prose on new frozen champions; exploratory as to the framework)", ""]
L.append(f"champions present: {tags}; tasks {len(tasks)}; infra_final rows by arm: {dict(infra)}; seed mean {np.nanmean(Y('seed','reward')):.3f}, seed-check {np.nanmean(Y('seed-check','reward')):.3f}")
for q, nm in (("reward", "reward"), ("steps", "decision steps (n_llm_calls - 1)"), ("seedp", "seed-tool calls"), ("pk5", "pass^5"), ("ptok", "prompt tokens")):
    Dm = D_matrix(q)
    if np.isnan(Dm).all(): L += ["", f"## {nm}: no data in the records (skipped)"]; continue
    pooled = float(np.nanmean(Dm)); champ_means = np.nanmean(Dm, axis=1); bs = two_level(np.nan_to_num(Dm)); lo, hi = np.percentile(bs, [2.5, 97.5])
    tt = one(champ_means); per = {g: one(Dm[i]) for i, g in enumerate(tags)}
    loo = {g: float(np.nanmean(np.delete(Dm, i, axis=0))) for i, g in enumerate(tags)}
    res[q] = dict(pooled=pooled, boot_lo=float(lo), boot_hi=float(hi), t_over_champions=tt, per_champion=per, leave_one_out=loo, champ_means=[float(v) for v in champ_means])
    f = (lambda v: f"{v:+.0f}") if q == "ptok" else (lambda v: f"{v:+.3f}")
    L += ["", f"## {nm}: pooled code - mean(prose A, B, C)", f"pooled {f(pooled)}; two-level bootstrap [{f(lo)}, {f(hi)}]; t over {len(tags)} champion means [{f(tt['lo'])}, {f(tt['hi'])}] (df {len(tags)-1}) raw p {tt['p']:.4f}",
          "per champion: " + "; ".join(f"{g} {f(v['est'])} [{f(v['lo'])}, {f(v['hi'])}] p {v['p']:.3f}" for g, v in per.items()), "leave-one-champion-out pooled: " + "; ".join(f"without {g} {f(v)}" for g, v in loo.items())]
    if q == "reward":
        boot_ex = (lo > 0 or hi < 0); t_ex = (tt["lo"] > 0 or tt["hi"] < 0)
        verdict = "DETECTED (both intervals exclude 0)" if (boot_ex and t_ex) else ("NOT SEPARATED AT THE CHAMPION LEVEL (bootstrap excludes 0, t over champions does not)" if boot_ex else "not detected (the bootstrap interval includes 0)")
        res[q]["verdict"] = verdict; L.append("PRIMARY VERDICT (addendum 34 rule): " + verdict)
# draft spread, code-base, prose_d-base
L += ["", "## draft-to-draft spread (reward; champion-mean per draft)"]
for g in tags:
    dm = [float(np.nanmean(Y(f"F4-{g}-prose_{d}", "reward"))) for d in DR]; L.append(f"{g}: drafts A {dm[0]:.3f}, B {dm[1]:.3f}, C {dm[2]:.3f}; SD {np.std(dm, ddof=1):.3f}; max pairwise difference {max(dm)-min(dm):.3f}; code {np.nanmean(Y(f'F4-{g}-code','reward')):.3f}; base {np.nanmean(Y(f'F4-{g}-base','reward')):.3f}")
    res.setdefault("spread", {})[g] = dict(drafts=dm, sd=float(np.std(dm, ddof=1)), code=float(np.nanmean(Y(f'F4-{g}-code', 'reward'))), base=float(np.nanmean(Y(f'F4-{g}-base', 'reward'))))
L += ["", "## code - base and prose_d - base (reward), pooled over champions: raw t over champion means"]
for nm_, fn in (("code - base", lambda g: Y(f"F4-{g}-code", "reward") - Y(f"F4-{g}-base", "reward")),) + tuple((f"prose_{d} - base", (lambda d: (lambda g: Y(f"F4-{g}-prose_{d}", "reward") - Y(f"F4-{g}-base", "reward")))(d)) for d in DR):
    cm = [float(np.nanmean(fn(g))) for g in tags]; o = one(cm); L.append(f"{nm_}: {o['est']:+.3f} [{o['lo']:+.3f}, {o['hi']:+.3f}] over champions; per champion {[round(v, 3) for v in cm]}")
os.makedirs(OUT, exist_ok=True); json.dump(res, open(os.path.join(OUT, "fam4.json"), "w"), indent=1); open(os.path.join(OUT, "fam4.md"), "w").write("\n".join(L)); print("\n".join(L))
