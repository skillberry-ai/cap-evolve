#!/usr/bin/env python3
"""E5a analysis: AppWorld test_challenge, frozen artifacts, 2 trials per task (amendment 12 addendum 25). Written BEFORE any episode exists. Exploratory.

Input: STATE_DIR/records/<idx>.json written by run_window.py (fields idx, arm, task_id, scenario, trial, success, error_kind, termination, n_steps, ...), STATE_DIR/order.sha256,
and the registered window definition (arms, tasks, trials). One record per (arm, task, trial).
Metrics (per arm): TGC = mean over tasks of the mean over the trials of success; SGC = for each trial, the share of scenarios in which EVERY task passed, averaged over trials.
Bootstrap: resample SCENARIOS with replacement (the same resample for all arms: paired), keep all tasks and both trials of a drawn scenario, 10,000 resamples, numpy seed 20261029,
percentile 95% intervals. Two-sided bootstrap p = 2 * min(share of resamples with difference <= 0, share >= 0), floored at 1/10,001 (raw, exploratory).
Primary basis: infra failures (error_kind == "infra", after the runner's 3 retries) scored 0 (success False). Sensitivity: infra rows dropped (scenario-level drop of any task with an infra row in any arm or trial: the (task, trial) cell is removed for ALL arms).
Contrasts (primary window = the 7 arms): gain of each arm over seed; cape_k02 minus each of the six comparators (trace2skill, gepa_full, skillopt, ace, gepa) -- five comparators in the
primary window plus seed; cape_k02 minus the EQUAL-WEIGHT MEAN of the five comparators (pooled test); Holm over the five cape_k02-vs-comparator contrasts as an exploratory family.
Extras window (evoskill, wikiskill, miprov2, metaharness; own seed cell): the same computations within that window, against its own seed; NEVER compared with the primary window's arms.
Completeness: if fewer than all cells exist, only (task, trial) cells complete for ALL arms of the window are used and the counts are printed; the window is labelled INCOMPLETE.
    python3 -I e5a_analysis.py OUTDIR STATE_DIR TASKS_FILE ARMS_CSV TRIALS REGISTERED_ORDER_SHA256     (numpy needed: run with the campaign venv)
"""
import json, os, sys, math
from pathlib import Path
import numpy as np
OUT, STATE, TASKS, ARMS, TRIALS, REG = sys.argv[1:7]
arms = ARMS.split(","); trials = int(TRIALS)
tasks = [x for x in Path(TASKS).read_text().split() if x]
f = lambda x, d=3: f"{x:.{d}f}"; sg = lambda x, d=3: f"{x:+.{d}f}"
pf = lambda p: "<0.001" if p < 0.001 else f"{p:.3f}"


def holm(ps):
    items = sorted(ps.items(), key=lambda kv: kv[1]); m = len(items); adj = {}; run = 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p)); adj[k] = run
    return adj


def main():
    order_sha = (Path(STATE) / "order.sha256").read_text().strip()
    recs = [json.load(open(p)) for p in sorted(Path(STATE, "records").glob("*.json"))]
    byc = {(r["arm"], r["task_id"], int(r["trial"])): r for r in recs}
    scen = {t: t.split("_")[0] for t in tasks}; scenarios = sorted(set(scen.values()))
    L = ["# E5a: AppWorld test_challenge (addendum 25; exploratory; frozen artifacts; one window)", "",
         f"- order sha256 in the state dir: {order_sha}; registered: {REG}; equal: {order_sha == REG}",
         f"- window arms: {arms}; tasks {len(tasks)} in {len(scenarios)} scenarios; trials {trials}; records read {len(recs)} of {len(tasks) * len(arms) * trials} expected"]
    cnt = {a: dict(n=0, infra=0, fail=0, success=0) for a in arms}
    for r in recs:
        if r["arm"] in cnt:
            c = cnt[r["arm"]]; c["n"] += 1; c["infra"] += int(r.get("error_kind") == "infra"); c["success"] += int(bool(r["success"]))
    L.append("- per arm records / successes / infra failures: " + "; ".join(f"{a} {c['n']} / {c['success']} / {c['infra']}" for a, c in cnt.items()))
    term = {}
    for r in recs: term.setdefault(r["arm"], {}).setdefault(str(r.get("termination")), 0); term[r["arm"]][str(r.get("termination"))] += 1
    L.append("- termination reasons per arm: " + json.dumps(term))
    cells_all = [(t, k) for t in tasks for k in range(trials)]
    complete = [(t, k) for (t, k) in cells_all if all((a, t, k) in byc for a in arms)]
    L.append(f"- (task, trial) cells complete for ALL arms: {len(complete)} of {len(cells_all)}" + ("" if len(complete) == len(cells_all) else "  *** WINDOW INCOMPLETE: only these cells are used ***"))
    J = {}

    def analyse(label, drop_infra):
        cells = [c for c in complete if not (drop_infra and any(byc[(a, c[0], c[1])].get("error_kind") == "infra" for a in arms))]
        if not cells: return [f"## {label}: no complete cell"]
        # arrays: arm x scenario -> (sum success, n tasks-trials) ; TGC by scenario sums; SGC per (scenario, trial)
        sidx = {s: i for i, s in enumerate(scenarios)}; S = len(scenarios)
        succ = np.zeros((len(arms), S)); nn = np.zeros(S)
        tr_all = np.zeros((len(arms), S, trials)); tr_ok = np.zeros((len(arms), S, trials)); tr_n = np.zeros((S, trials))
        for (t, k) in cells:
            s = sidx[scen[t]]; nn[s] += 1; tr_n[s, k] += 1
            for ai, a in enumerate(arms):
                v = float(bool(byc[(a, t, k)]["success"])); succ[ai, s] += v
                tr_ok[ai, s, k] += v
        # SGC: a scenario counts in trial k only if all its tasks are present (3) and all passed
        full = (tr_n == 3)
        sg_ind = np.where(full[None, :, :], (tr_ok == 3).astype(float), 0.0)
        def stats(idx):
            w = nn[idx].sum()
            tgc = succ[:, idx].sum(axis=1) / w
            den = full[idx].sum(axis=0)       # per trial: number of full scenarios
            sgc = np.mean(sg_ind[:, idx, :].sum(axis=1) / np.maximum(den, 1)[None, :], axis=1)
            return tgc, sgc
        rng = np.random.default_rng(20261029); B = 10000
        base_t, base_s = stats(np.arange(S))
        bt = np.empty((B, len(arms))); bs = np.empty((B, len(arms)))
        for b in range(B):
            idx = rng.integers(0, S, S); bt[b], bs[b] = stats(idx)
        ai = {a: i for i, a in enumerate(arms)}
        def con(name, plus, minus, which):
            # plus, minus: lists of arms; difference of arm-set means
            bv = (base_t if which == "TGC" else base_s); bb = (bt if which == "TGC" else bs)
            d0 = bv[[ai[a] for a in plus]].mean() - bv[[ai[a] for a in minus]].mean()
            db = bb[:, [ai[a] for a in plus]].mean(axis=1) - bb[:, [ai[a] for a in minus]].mean(axis=1)
            lo, hi = np.percentile(db, [2.5, 97.5]); p = max(2 * min((db <= 0).mean(), (db >= 0).mean()), 1 / (B + 1))
            return d0, lo, hi, p
        out = [f"## {label}", "", f"cells used: {len(cells)} of {len(cells_all)}; scenarios {S}", "",
               "| arm | TGC | SGC | TGC gain over seed [95% CI] | raw p | SGC gain over seed [95% CI] |", "|---|---|---|---|---|---|"]
        seedarm = "seed"
        for a in arms:
            row = f"| {a} | {f(base_t[ai[a]] * 100, 1)} | {f(base_s[ai[a]] * 100, 1)} | "
            if a == seedarm: row += "n/a | n/a | n/a |"
            else:
                d, lo, hi, p = con(a, [a], [seedarm], "TGC"); ds, los, his, ps = con(a, [a], [seedarm], "SGC")
                J[f"{label}|{a} minus seed|TGC"] = dict(d=d * 100, lo=lo * 100, hi=hi * 100, p=p)
                row += f"{sg(d * 100, 1)} [{f(lo * 100, 1)}, {f(hi * 100, 1)}] | {pf(p)} | {sg(ds * 100, 1)} [{f(los * 100, 1)}, {f(his * 100, 1)}] |"
            out.append(row)
        if "cape_k02" in arms:
            comps = [a for a in arms if a not in ("seed", "cape_k02")]
            out += ["", "cape_k02 minus each comparator (paired scenario bootstrap; descriptive; Holm over the family of these contrasts, TGC)", "",
                    f"| contrast | TGC diff [95% CI] | raw p | Holm p (family of {len(comps)}) | SGC diff [95% CI] |", "|---|---|---|---|---|"]
            ps = {}; rows = []
            for a in comps:
                d, lo, hi, p = con(a, ["cape_k02"], [a], "TGC"); ds, los, his, _ = con(a, ["cape_k02"], [a], "SGC"); ps[a] = p; rows.append((a, d, lo, hi, p, ds, los, his))
            ha = holm(ps) if comps else {}
            for a, d, lo, hi, p, ds, los, his in rows:
                J[f"{label}|cape_k02 minus {a}|TGC"] = dict(d=d * 100, lo=lo * 100, hi=hi * 100, p=p, holm=ha[a])
                out.append(f"| cape_k02 minus {a} | {sg(d * 100, 1)} [{f(lo * 100, 1)}, {f(hi * 100, 1)}] | {pf(p)} | {pf(ha[a])} | {sg(ds * 100, 1)} [{f(los * 100, 1)}, {f(his * 100, 1)}] |")
            if comps:
                d, lo, hi, p = con("pooled", ["cape_k02"], comps, "TGC"); ds, los, his, ps_ = con("pooled", ["cape_k02"], comps, "SGC")
                J[f"{label}|cape_k02 minus mean of comparators|TGC"] = dict(d=d * 100, lo=lo * 100, hi=hi * 100, p=p)
                out += ["", f"POOLED: cape_k02 minus the equal-weight mean of the {len(comps)} comparators ({', '.join(comps)}): TGC {sg(d * 100, 1)} [{f(lo * 100, 1)}, {f(hi * 100, 1)}], raw p {pf(p)}; SGC {sg(ds * 100, 1)} [{f(los * 100, 1)}, {f(his * 100, 1)}]. This is a test against the AVERAGE comparator."]
        return out + [""]
    L += [""] + analyse("PRIMARY (infra scored 0)", False) + analyse("SENSITIVITY (cells with an infra failure in any arm dropped for all arms)", True)
    L += ["Each AppWorld arm is ONE search (the frozen artifact of one optimization run); intervals are over scenarios of test_challenge for these artifacts and do not carry search-to-search variation. The harder-difficulty split is disjoint from train, dev and test_normal.",
          "Seed-relative SE planning (planning document, not re-derived): about 1.5 to 2.0 TGC points for a CapEvolve-vs-X contrast at 2 trials."]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "e5a.md"), "w").write("\n".join(L) + "\n"); json.dump(J, open(os.path.join(OUT, "e5a.json"), "w"), indent=1)
    print("\n".join(L))


if __name__ == "__main__":
    main()
