#!/usr/bin/env python3
"""Registered final-evaluation analysis, run once under the user-decision unblinding (analysis_plan erratum 36).

Implements, with the estimators of paired_cluster_bootstrap.py (CR1 t, family clusters, Holm) and the families of
experiments/final/manifests/comparison_family*.json:
  * per-arm tables (mean reward, 95% CI, per-seed means, inert and infra counts),
  * the registered contrast families per suite (artifact-level CR1 test with Holm, pipeline-level t(S-1) interval,
    TOST at margin 0.10 where the plan allows it),
  * the v2 family V2 (11G) on the v2 E and v2 D windows,
  * the descriptive v1-versus-v2 comparison (within-window deltas against each window's own seed).
Primary basis: infra_final = failure (results_long.csv). Sensitivity: results_long_infra_missing.csv.
Inert artifacts (tree hash equal to the seed, manifest flag) are replaced by the in-window seed scores, so their
delta against the seed is exactly 0 (9D (i)); the as-measured re-score of an inert artifact is reported separately.
Reads only hash-registered result files (verified before the run by the caller). Pure standard library.
    python3 -I unblind_analysis.py OUTDIR
"""
import csv, glob, json, math, os, statistics, sys
from collections import defaultdict, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paired_cluster_bootstrap as pcb  # noqa: E402

PAPER = os.path.abspath(os.path.join(HERE, "..", ".."))
FE = "/home/dev/projects2/campaign-scratch/final_eval"
MAN = os.path.join(PAPER, "experiments", "final", "manifests")
RUNS = "/home/dev/projects2/campaign-scratch/runs"
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

WINDOWS = OrderedDict([("A", "A"), ("B", "B"), ("C", "C"), ("D", "D"), ("E", "E"), ("V2/D", "V2_D"), ("V2/E", "V2_E"), ("V2/A", "V2_A")])
SPLITS = {"A": ("",), "B": ("test",), "C": ("test",), "D": ("test",), "E": ("test",), "V2/D": ("test",), "V2/E": ("test",), "V2/A": ("",)}
MARGIN = 0.10
V21 = OrderedDict()
_REG = set()
for _l in open(os.path.join(PAPER, "experiments", "registry.jsonl")):
    _REG.add(json.loads(_l)["item"])
for _s, _sp in (("D", ("test",)), ("A", ("",))):   # only windows whose results files are hash-registered
    if f"results_V21_{_s}_results_long.csv" in _REG:
        V21[f"V21/{_s}"] = (f"V21_{_s}", _sp)
if "results_V3B1_main_results_long.csv" in _REG:   # V3 B1 test block (amendment 12, erratum 8: freeze declaration)
    V21["V3B1/main"] = ("V3B1", ("test",))
if "results_V3B1LATE_main_results_long.csv" in _REG:   # V3 B1 late-competitor window (addendum 3, erratum 13)
    V21["V3B1LATE/main"] = ("V3B1LATE", ("test",))
if "results_V3B1CHAIN_main_results_long.csv" in _REG:   # V3 B1 chain window, descriptive (erratum 15, 16)
    V21["V3B1CHAIN/main"] = ("V3B1CHAIN", ("test",))
if "results_V3B1_traineval_results_long.csv" in _REG:   # V3 B1 train-30 re-evaluation (descriptive)
    V21["V3B1/traineval"] = ("V3B1_traineval", ("train",))
for _w, (_k, _sp) in V21.items():
    WINDOWS[_w] = _k
    SPLITS[_w] = _sp


def rr(r):
    return (r["arm"], r["vs"]) if isinstance(r, dict) else (r[0], r[1])


def f(x, d=3):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}"


def sgn(x, d=3):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:+.{d}f}"


def pf(p):
    if p is None:
        return "n/a"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


# ------------------------------------------------------------------ data
class Win:
    def __init__(self, win, infra_missing=False):
        self.win, self.key = win, WINDOWS[win]
        fn = "results_long_infra_missing.csv" if infra_missing else "results_long.csv"
        rows = [r for r in csv.DictReader(open(os.path.join(FE, win, fn))) if r["split"] in SPLITS[win]]
        self.tasks = sorted({r["task"] for r in rows}, key=lambda t: (len(t), t))
        self.tix = {t: i for i, t in enumerate(self.tasks)}
        fam = {r["task"]: r["family"] for r in rows}
        self.fam = [fam[t] for t in self.tasks]
        self.M = defaultdict(lambda: [None] * len(self.tasks))
        self.ntr = defaultdict(list)
        self.infra_final = defaultdict(int)
        for r in rows:
            k = (r["arm"], int(r["seed"]))
            v = r["reward"]
            self.M[k][self.tix[r["task"]]] = None if v in ("", "nan", "NaN") else float(v)
            self.ntr[k].append(int(r["n_trials"] or 0))
            self.infra_final[k] += int(r["n_infra_final"] or 0)
        man = json.load(open(os.path.join(MAN, f"artifacts_{self.key}.json")))
        self.inert, self.seeds_of, self.tree = {}, defaultdict(set), {}
        for e in man["entries"]:
            if e.get("mode", "B") != "B":
                continue
            self.inert[(e["arm"], e["seed"])] = bool(e.get("inert"))
            self.seeds_of[e["arm"]].add(e["seed"])
            self.tree[(e["arm"], e["seed"])] = e.get("tree_sha256") or e.get("normalized_tree_sha256")
        self.seedvec = self.M[("seed", 0)]
        self.arms = [a for a in self.seeds_of]

    def vec(self, arm, s, adjusted=True):
        if adjusted and self.inert.get((arm, s)):
            return list(self.seedvec)
        return self.M.get((arm, s)) if (arm, s) in self.M else (list(self.seedvec) if self.inert.get((arm, s)) else None)

    def rows(self, arm, adjusted=True):
        if arm == "seed":
            return [list(self.seedvec)], [0]
        out, ss = [], []
        for s in sorted(self.seeds_of.get(arm, ())):
            v = self.vec(arm, s, adjusted)
            if v is not None:
                out.append(v); ss.append(s)
        return out, ss

    def collapsed(self, arm):
        R, _ = self.rows(arm)
        if len(R) == 1:
            return R
        col = []
        for t in range(len(self.tasks)):
            xs = [r[t] for r in R if r[t] is not None]
            col.append(sum(xs) / len(xs) if xs else None)
        return [col]

    def n_inert(self, arm):
        ss = sorted(self.seeds_of.get(arm, ()))
        return sum(1 for s in ss if self.inert.get((arm, s))), len(ss)

    def trials(self, arm):
        xs = [n for s in self.seeds_of.get(arm, ()) for n in self.ntr.get((arm, s), [])] if arm != "seed" else self.ntr.get(("seed", 0), [])
        return statistics.mode(xs) if xs else None


def mean_ci(vals, fam):
    """Mean of task-level values with CR1 t(C-1) CI (family clusters)."""
    ok = [(v, c) for v, c in zip(vals, fam) if v is not None]
    if not ok:
        return None
    r = pcb.paired_cluster_bootstrap([[v for v, _ in ok]], [[0.0] * len(ok)], [c for _, c in ok], B=20)
    return {"mean": r["theta"], "ci": r["cr_ci"], "se": r["cr_se"], "n_tasks": r["n_tasks"], "n_clusters": r["n_clusters"]}


def seedavg(R):
    out = []
    for t in range(len(R[0])):
        xs = [r[t] for r in R if r[t] is not None]
        out.append(sum(xs) / len(xs) if xs else None)
    return out


def contrast(W, a, b, adjusted=True):
    Ya, sa = W.rows(a, adjusted)
    Yb = W.collapsed(b) if adjusted else (W.rows(b, False)[0] if b == "seed" else None)
    if not Ya or Yb is None:
        return None
    if not adjusted and len(Yb) != 1:
        Yb = [seedavg(Yb)]
    r = pcb.paired_cluster_bootstrap(Ya, Yb, W.fam, B=20)
    S = r["n_seeds"]
    sd = r["seed_sd"]
    out = {"a": a, "b": b, "theta": r["theta"], "cr_se": r["cr_se"], "cr_ci": r["cr_ci"], "p": r["cr_p_two_sided"], "per_seed": r["per_seed"],
           "seeds": sa, "S": S, "C": r["n_clusters"], "T": r["n_tasks"], "seed_sd": sd}
    if S >= 2 and sd is not None:
        se2 = math.sqrt(r["cr_se"] ** 2 + sd ** 2 / S)
        q = pcb.t_ppf(0.975, S - 1)
        out["pipe_ci"] = (r["theta"] - q * se2, r["theta"] + q * se2)
        out["pipe_p"] = 2 * (1 - pcb._t_cdf(abs(r["theta"]) / se2, S - 1)) if se2 > 0 else 0.0
    q90 = pcb.t_ppf(0.95, r["n_clusters"] - 1)
    out["ci90"] = (r["theta"] - q90 * r["cr_se"], r["theta"] + q90 * r["cr_se"])
    if r["cr_se"] > 0 and not (r["cr_se"] == 0):
        tl = (r["theta"] + MARGIN) / r["cr_se"]; tu = (MARGIN - r["theta"]) / r["cr_se"]
        out["tost_p"] = max(1 - pcb._t_cdf(tl, r["n_clusters"] - 1), 1 - pcb._t_cdf(tu, r["n_clusters"] - 1))
    ia, na = W.n_inert(a)
    ib, nb = W.n_inert(b) if b != "seed" else (0, 1)
    out["inert_a"], out["inert_b"] = f"{ia}/{na}", f"{ib}/{nb}"
    if r["cr_se"] == 0 and r["theta"] == 0:
        out["p"] = 1.0
        out["pipe_p"] = 1.0
        out["tost_p"] = None
        out["structural_zero"] = True
    out["inert_block"] = (ia >= 2 and na >= 3) or (ib >= 2 and nb >= 3)
    out["all_inert"] = (ia == na and na > 0) and (b == "seed" or (ib == nb))
    return out


def family(W, Wsens, name, rows, tost=False, rescale=None):
    res = []
    for a, b in rows:
        if a not in W.seeds_of or (b != "seed" and b not in W.seeds_of):
            res.append({"a": a, "b": b, "missing": True}); continue
        c = contrast(W, a, b)
        cs = contrast(Wsens, a, b) if Wsens else None
        c["theta_sens"] = cs["theta"] if cs else None
        c["p_sens"] = cs["p"] if cs else None
        res.append(c)
    ok = [c for c in res if not c.get("missing")]
    adj = pcb.holm([c["p"] for c in ok]) if ok else []
    m = len(ok)
    for c, h in zip(ok, adj):
        c["holm"] = h
    sens_adj = pcb.holm([c["p_sens"] for c in ok]) if ok and all(c["p_sens"] is not None for c in ok) else [None] * m
    for c, h in zip(ok, sens_adj):
        c["holm_sens"] = h
    if tost:
        t_ok = [c for c in ok if c["holm"] >= 0.05 and not c["inert_block"] and "tost_p" in c]
        for c, h in zip(t_ok, pcb.holm([c["tost_p"] for c in t_ok]) if t_ok else []):
            c["tost_holm"] = h
    return {"name": name, "m": m, "rows": res}


def verdict(c, tost):
    if c.get("missing"):
        return "arm missing"
    if c["all_inert"]:
        return "both returned the seed (delta 0 by construction)"
    if c["holm"] < 0.05:
        return "superior" if c["theta"] > 0 else "inferior"
    if tost:
        if c["inert_block"]:
            return "not testable (inert)"
        if "tost_holm" in c and c["tost_holm"] < 0.05:
            return f"equivalent within +-{MARGIN:.2f}"
        return "inconclusive"
    return "n.s."


def fam_table(F, tost=False, label_dagger=()):
    L = [f"**{F['name']}** (Holm m = {F['m']}; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)", "",
         "| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | full-family Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in F["rows"]:
        if c.get("missing"):
            L.append(f"| {c['a']} vs {c['b']} | arm absent | | | | | not run | | | |"); continue
        da = " (dagger)" if c["a"] in label_dagger else ""
        db = " (dagger)" if c["b"] in label_dagger else ""
        pp = c.get("pipe_ci")
        L.append(f"| {c['a']}{da} vs {c['b']}{db} | {sgn(c['theta'])} | [{f(c['cr_ci'][0])}, {f(c['cr_ci'][1])}] | "
                 f"{('[%s, %s]' % (f(pp[0]), f(pp[1]))) if pp else 'n/a'} | {pf(c['p'])} | {pf(c['holm'])} | {pf(c.get('holm_full')) if c.get('holm_full') is not None else '-'} | {verdict(c, tost)} | "
                 f"{sgn(c['theta_sens'])} ({pf(c.get('holm_sens'))}) | a {c['inert_a']}, b {c['inert_b']} | {', '.join(sgn(x, 2) for x in c['per_seed'])} |")
    return L


def arm_table(W, Ws):
    order = ["seed", "seed-check"] + sorted(a for a in W.arms if a not in ("seed", "seed-check"))
    present = [a for a in order if a in W.seeds_of or a in ("seed", "seed-check") and (a, 0) in W.M]
    L = ["| arm | seeds | trials/task | mean reward (as measured) | mean (inert -> seed) | 95% CI (CR1, artifact-level) | per-seed mean (as measured) | inert seeds | infra_final cells | mean, infra_final missing |", "|---|---|---|---|---|---|---|---|---|---|"]
    for a in present:
        if a in ("seed", "seed-check"):
            v = W.M[(a, 0)]
            mc = mean_ci(v, W.fam); ms = mean_ci(Ws.M[(a, 0)], Ws.fam)
            L.append(f"| {a} | 1 | {W.trials(a) if a == 'seed' else W.ntr[(a,0)][0] if W.ntr.get((a,0)) else ''} | {f(mc['mean'])} | {f(mc['mean'])} | [{f(mc['ci'][0])}, {f(mc['ci'][1])}] | - | - | {W.infra_final[(a,0)]} | {f(ms['mean'])} |")
            continue
        Rraw = [W.M[(a, s)] for s in sorted(W.seeds_of[a]) if (a, s) in W.M]
        Radj, ss = W.rows(a)
        if not Radj:
            continue
        mraw = mean_ci(seedavg(Rraw), W.fam) if Rraw else None
        madj = mean_ci(seedavg(Radj), W.fam)
        msens = mean_ci(seedavg(Ws.rows(a)[0]), Ws.fam)
        psm = ", ".join(f"s{s}:{f(sum(x for x in W.M[(a,s)] if x is not None)/max(1,sum(1 for x in W.M[(a,s)] if x is not None)),3)}" if (a, s) in W.M else f"s{s}:inert(not rescored)" for s in sorted(W.seeds_of[a]))
        ni, ns = W.n_inert(a)
        inf = sum(W.infra_final[(a, s)] for s in W.seeds_of[a])
        L.append(f"| {a} | {ns} | {W.trials(a) or '-'} | {f(mraw['mean']) if mraw else 'n/a'} | {f(madj['mean'])} | [{f(madj['ci'][0])}, {f(madj['ci'][1])}] | {psm} | {ni}/{ns} | {inf} | {f(msens['mean'])} |")
    return L


# ------------------------------------------------------------------ cost / infra / latency
def price_opt(cs):
    o = cs.get("optimizer") or {}
    if not o.get("calls"):
        return None, None, None
    p = json.load(open(os.path.join(PAPER, "protocol", "pricing.json")))["usd_per_mtok"]["aws/claude-sonnet-5-5"]
    return (o.get("prompt", 0) * p["input"] + o.get("completion", 0) * p["output"] + o.get("cache_read", 0) * p["cache_read"] + o.get("cache_creation", 0) * p["cache_write_5m"]) / 1e6, o.get("non_cache_read_tokens"), o.get("calls")


def run_dirs(win):
    """(arm, seed) -> run_dir for v1 (bstar manifest) and v2 (runs/V2)."""
    m = {}
    if win.startswith("V2/"):
        S = win[3]
        for arm in ("hc2", "ao2", "ao21"):
            for s in range(3):
                d = f"{RUNS}/V2/{S}/{arm}/s{s}"
                if os.path.isdir(d):
                    m[(arm, s)] = d
    else:
        b = json.load(open(os.path.join(MAN, f"bstar_{win}.json")))
        for r in b["runs"]:
            m[(r["arm"], r["seed"])] = (r["run_dir"], r.get("counter"))
    return m


_MET = None


def metrics_fallback(suite, arm, seed):
    global _MET
    if _MET is None:
        _MET = {}
        p = os.path.join(OUT, "metrics", "metrics_by_arm.csv")
        if os.path.exists(p):
            for r in csv.DictReader(open(p)):
                if r["category"] == "main":
                    _MET[(r["suite"], r["arm"], int(r["seed"] or -1))] = r
    return _MET.get((suite, arm, seed))


def ledger_v2(win, arm, seed):
    """Gateway-ledger optimizer cost of a v2 search by tag V2-<suite>-<arm>-s<k> (the cost source of truth named in the run's manifest/cost_source.txt)."""
    global _MET
    metrics_fallback("-", "", 0)
    key = ("LEDGER", f"V2-{win[3]}-{arm}-s{seed}")
    if key not in _MET:
        p = os.path.join(OUT, "metrics", "metrics_by_arm.csv")
        for r in csv.DictReader(open(p)) if os.path.exists(p) else []:
            _MET[("LEDGER", r["arm"])] = r
    return _MET.get(key)


def state_calls(d):
    try:
        return json.load(open(os.path.join(d, "logs", "rollout_counter.json")))["total"]
    except Exception:
        pass
    try:
        return json.load(open(os.path.join(d, ".capevolve", "run_main", "state.json")))["spent"]["metric_calls"]
    except Exception:
        return None


def cost_rows(win):
    if win.startswith("V3B1/"):
        out = []
        for fw in sorted(os.listdir(os.path.join(RUNS, "V3", "B1"))):
            for k in range(3):
                p = os.path.join(RUNS, "V3", "B1", fw, f"s{k}", "run_summary.json")
                if os.path.exists(p):
                    d = json.load(open(p))
                    out.append({"arm": fw, "seed": k, "optimizer_usd_proxy": d.get("optimizer_usd"), "optimizer_noncache_tokens": d.get("optimizer_tokens_non_cache"), "optimizer_calls": d.get("optimizer_calls"), "search_rollouts": d.get("rollouts_used"), "source": f"run_summary.json (usd_total {d.get('usd_total')}, wall_s {d.get('wall_s')})"})
        return out
    if win.startswith("V21/"):
        return []
    out = []
    rd = run_dirs(win)
    for (arm, s), v in sorted(rd.items()):
        d, cnt = (v if isinstance(v, tuple) else (v, None))
        usd = toks = calls = None
        p = os.path.join(d, "cost_summary.json")
        if os.path.exists(p):
            try:
                usd, toks, calls = price_opt(json.load(open(p)))
            except Exception:
                pass
        src = "cost_summary.json"
        if usd is None and not win.startswith("V2/"):
            m = metrics_fallback(win, arm, s)
            if m and m.get("optimizer_usd_priced"):
                usd, toks, calls, src = float(m["optimizer_usd_priced"]), int(m["optimizer_noncache_tokens"] or 0), int(m["optimizer_calls"] or 0), "collect_metrics gateway ledger"
        if usd is None and win == "V2/A":
            m = ledger_v2(win, arm, s)
            if m and m.get("optimizer_usd_priced"):
                usd, toks, calls, src = float(m["optimizer_usd_priced"]), int(m["optimizer_noncache_tokens"] or 0), int(m["optimizer_calls"] or 0), "gateway ledger by tag (lower bound: some calls unpriced)"
        if cnt is None and win.startswith("V2/"):
            cnt = state_calls(d)
        out.append({"arm": arm, "seed": s, "optimizer_usd_proxy": usd, "optimizer_noncache_tokens": toks, "optimizer_calls": calls, "search_rollouts": cnt, "source": src})
    return out


def latency(win):
    agg = defaultdict(list)
    try:
        import datetime as dt
        for r in csv.DictReader(open(os.path.join(FE, win, "results_trials.csv"))):
            if r["split"] not in SPLITS[win] or not r["t_start"] or not r["t_end"]:
                continue
            a = dt.datetime.strptime(r["t_start"], "%Y-%m-%dT%H:%M:%SZ"); b = dt.datetime.strptime(r["t_end"], "%Y-%m-%dT%H:%M:%SZ")
            agg[r["arm"]].append((b - a).total_seconds())
    except Exception as e:  # pragma: no cover
        return {"error": str(e)}
    return {a: (statistics.mean(v), statistics.median(v), len(v)) for a, v in agg.items()}


def raw_tokens(win):
    agg = defaultdict(lambda: [0, 0, 0])
    p = os.path.join(FE, win, "raw", "rollouts.jsonl")
    if not os.path.exists(p):
        return {}
    for line in open(p):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("type") != "attempt":
            continue
        a = agg[r.get("arm")]
        a[0] += 1; a[1] += r.get("tokens") or 0; a[2] += r.get("n_llm_calls") or 0
    return {k: (v[1] / v[0] if v[0] else None, v[2] / v[0] if v[0] else None, v[0]) for k, v in agg.items()}


def infra_counts(win):
    d = json.load(open(os.path.join(FE, win, "per_arm_report.json")))
    return d


def seed_drift(win):
    """5I check on the in-window seed: task-demeaned reward by ~1 h blocks."""
    import datetime as dt
    rows = []
    for r in csv.DictReader(open(os.path.join(FE, win, "results_trials.csv"))):
        if r["arm"] != "seed" or r["split"] not in SPLITS[win] or r["reward"] == "":
            continue
        rows.append((dt.datetime.strptime(r["t_start"], "%Y-%m-%dT%H:%M:%SZ").timestamp(), r["task"], float(r["reward"])))
    if len(rows) < 20:
        return None
    mu = defaultdict(list)
    for t, k, x in rows:
        mu[k].append(x)
    mu = {k: sum(v) / len(v) for k, v in mu.items()}
    t0 = min(r[0] for r in rows)
    blocks = defaultdict(list)
    for t, k, x in rows:
        blocks[int((t - t0) // 3600)].append(x - mu[k])
    keys = sorted(blocks)
    merged = []
    for k in keys:
        if merged and len(blocks[k]) < 0.05 * len(rows):
            merged[-1][1].extend(blocks[k])
        else:
            merged.append([k, list(blocks[k])])
    if len(merged) > 1 and len(merged[0][1]) < 0.05 * len(rows):
        merged[1][1] = merged[0][1] + merged[1][1]; merged.pop(0)
    allr = [x for _, v in merged for x in v]
    sd = statistics.pstdev(allr) if len(allr) > 1 else float("nan")
    ms = [(k, sum(v) / len(v), sd / math.sqrt(len(v)), len(v)) for k, v in merged]
    rng = max(m[1] for m in ms) - min(m[1] for m in ms)
    se = math.sqrt(sum(m[2] ** 2 for m in ms) / len(ms) * 2)
    return {"blocks": ms, "range": rng, "se_of_diff": se, "flag_gt_2se": rng > 2 * se}


def block_adjusted(win, W):
    """5I: block-adjusted delta vs seed when the in-window seed drifts by more than 2 SE. Block effect = task-demeaned
    in-window seed mean of the block (hour blocks from the window start, small blocks merged as in seed_drift);
    each trial reward has its block's effect subtracted before the task-level means are formed."""
    import datetime as dt
    trials = []
    for r in csv.DictReader(open(os.path.join(FE, win, "results_trials.csv"))):
        if r["split"] not in SPLITS[win] or r["reward"] == "":
            continue
        trials.append((dt.datetime.strptime(r["t_start"], "%Y-%m-%dT%H:%M:%SZ").timestamp(), r["arm"], int(r["seed"]), r["task"], float(r["reward"])))
    t0 = min(t[0] for t in trials)
    seedtr = [t for t in trials if t[1] == "seed"]
    mu = defaultdict(list)
    for t in seedtr:
        mu[t[3]].append(t[4])
    mu = {k: sum(v) / len(v) for k, v in mu.items()}
    blk = defaultdict(list)
    for t in seedtr:
        blk[int((t[0] - t0) // 3600)].append(t[4] - mu[t[3]])
    eff = {k: sum(v) / len(v) for k, v in blk.items()}
    def b(t):
        k = int((t - t0) // 3600)
        return eff.get(k, 0.0)
    acc = defaultdict(list)
    for t, arm, sd, task, rew in trials:
        acc[(arm, sd, task)].append(rew - b(t))
    def vec(arm, sd):
        return [ (sum(acc[(arm, sd, t)]) / len(acc[(arm, sd, t)])) if acc.get((arm, sd, t)) else None for t in W.tasks]
    seedv = vec("seed", 0)
    out = []
    for arm in sorted(W.seeds_of):
        if arm in ("seed", "seed-check"):
            continue
        R = []
        for sd in sorted(W.seeds_of[arm]):
            R.append(list(seedv) if W.inert.get((arm, sd)) else vec(arm, sd))
        r = pcb.paired_cluster_bootstrap(R, [seedv], W.fam, B=20)
        out.append((arm, r["theta"], r["cr_ci"], r["per_seed"]))
    return out, {k: round(v, 3) for k, v in sorted(eff.items())}


def main():
    md = OrderedDict()
    J = {}
    W, Ws = {}, {}
    for w in WINDOWS:
        W[w], Ws[w] = Win(w), Win(w, True)

    # ---- v1 families
    cf = json.load(open(os.path.join(MAN, "comparison_family.json")))
    cfV = {s: json.load(open(os.path.join(MAN, f"comparison_family_V2_{s}.json"))) for s in "ADE"}
    fams = defaultdict(list)
    for s in "ABC":
        F = cf[s]
        dag = tuple(F.get("dagger_arms", []))
        fams[s].append((family(W[s], Ws[s], f"Suite {s} primary 5A", [rr(r) for r in F["primary_5A"]], tost=(s in "AB")), dag, s in "AB"))
        if dag:
            rows = [rr(r) for r in F["primary_5A_without_dagger_arms"]]
            fams[s].append((family(W[s], Ws[s], f"Suite {s} primary 5A WITHOUT dagger arms {list(dag)} (Holm rescaled)", rows, tost=(s in "AB")), (), s in "AB"))
        fams[s].append((family(W[s], Ws[s], f"Suite {s} secondary 5B(i) vs seed", [rr(r) for r in F["secondary_5B_i"]], tost=(s in "AB")), dag, s in "AB"))
        fams[s].append((family(W[s], Ws[s], f"Suite {s} secondary 5B(ii) CapEvolve vs others", [rr(r) for r in F["secondary_5B_ii"]], tost=(s in "AB")), dag, s in "AB"))
        if s == "A":
            fams[s].append((family(W[s], Ws[s], "Suite A S-stock (5P-1)", [("hcstock", b) for b in ("seed", "gepa", "skillopt", "metaharness", "wikiskill", "evoskill")], tost=True), (), True))
        if F.get("secondary_S_stock_B_holm_m3"):
            fams[s].append((family(W[s], Ws[s], f"Suite {s} S-stock (9G; hcstock = E12B stock-gate arm if present)", [rr(r) for r in F["secondary_S_stock_B_holm_m3"]], tost=True), (), True))
        if s == "C":
            fams[s].append((family(W[s], Ws[s], "Suite C S-stock (5P-1)", [("hcstock", "seed"), ("hcstock", "gepa")], tost=False), (), False))
    for s in "DE":
        F = cf[s]
        fams[s].append((family(W[s], Ws[s], f"Suite {s} primary family (m = 11)", [rr(r) for r in F[f"primary_{s}_holm_m11"]], tost=(s == "D")), (), s == "D"))
        fams[s].append((family(W[s], Ws[s], f"Suite {s} secondary family {s}-sec (m = 4)", [rr(r) for r in F[f"secondary_{s}_sec_holm_m4"]], tost=(s == "D")), (), s == "D"))
        if s == "E":
            fams[s].append((family(W[s], Ws[s], "Suite E competitors E-comp", [rr(r) for r in F["E_comp_own_holm"]]), ("ao",), False))
    famv2 = {}
    for s in "ADE":
        k = f"V2/{s}"
        rows = [rr(r) for r in cfV[s]["primary_11G"]]
        famv2[s] = family(W[k], Ws[k], f"v2 window Suite {s}: family V2 (11G, m = 4)", rows, tost=False)
        desc = [("hc2", "ao2"), ("ao21", "seed"), ("ao21", "gepa")] if s != "A" else [("hc2", "ao2"), ("ao2", "seed")]
        famv2[s + "_desc"] = family(W[k], Ws[k], f"v2 window Suite {s}: descriptive rows (no Holm claim)", desc)

    famv21 = {}
    for w in V21:
        if not w.startswith("V21/"):
            continue
        sx = w[-1]
        cfx = json.load(open(os.path.join(MAN, f"comparison_family_V21_{sx}.json")))
        famv21[sx] = family(W[w], Ws[w], f"v2.1 window Suite {sx}: AO-2 v2.1 (erratum 43; secondary under 11D, own Holm m = 2)", [rr(r) for r in cfx["primary_11G"]])
    if "V3B1/main" in V21:
        w3 = "V3B1/main"
        CE = ["hcstock", "hc3", "ao22"]
        COMP = ["evoskill", "gepa", "gepafull", "metaharness", "mipro", "skillopt", "trace2skill", "wikiskill"]
        F1 = family(W[w3], Ws[w3], "V3 B1 family P1: each CapEvolve arm vs the seed (Holm m = 3)", [(c, "seed") for c in CE])
        F2 = [family(W[w3], Ws[w3], f"V3 B1 family P2: {c} vs each competitor (Holm m = 8)", [(c, b) for b in COMP]) for c in CE]
        rows = [r for F in [F1] + F2 for r in F["rows"] if not r.get("missing")]
        for r, h in zip(rows, pcb.holm([r["p"] for r in rows])):
            r["holm_full"] = h
        fams[w3] = [(F1, (), False)] + [(F, (), False) for F in F2]
        J["v3_B1"] = {"P1": F1, "P2": F2}
    if "V3B1LATE/main" in V21:
        wl = "V3B1LATE/main"
        for _x in (W[wl], Ws[wl]):
            _x.seeds_of["hl-v0"] = {0}
            _x.seeds_of.pop("harnesslens", None)
        CE = ["hcstock", "hc3", "ao22"]
        F_ace = family(W[wl], Ws[wl], "LC-ACE: each CapEvolve arm vs ACE (Holm m = 3; secondary, own family)", [(c, "ace") for c in CE])
        F_hl = family(W[wl], Ws[wl], "LC-HL: each CapEvolve arm vs hl-v0 (Holm m = 3; secondary; ARTIFACT-LEVEL ONLY: hl-v0 is one artifact standing for the 3 HarnessLens seeds)", [(c, "hl-v0") for c in CE])
        for _r in F_hl["rows"]:
            _r.pop("pipe_ci", None)      # LC-HL is artifact-level only (addendum 3): hl-v0 is one artifact standing for 3 seeds
            _r.pop("pipe_p", None)
        F_desc = family(W[wl], Ws[wl], "Descriptive rows in this window (no Holm claim): late competitors and CapEvolve arms vs the in-window seed", [("ace", "seed"), ("hl-v0", "seed")] + [(c, "seed") for c in CE])
        fams[wl] = [(F_ace, (), False), (F_hl, (), False), (F_desc, (), False)]
        J["v3_LATE"] = {"LC-ACE": F_ace, "LC-HL": F_hl, "desc": F_desc}
    chain_md = None
    if "V3B1CHAIN/main" in V21:
        wc = "V3B1CHAIN/main"
        Wc, Wm = W[wc], W["V3B1/main"]
        champ_path = os.path.join(FE, "champions_V3B1CHAIN.json")
        chains = {}
        for a in Wc.arms:
            if a in ("seed", "seed-check"):
                continue
            fw, sd, *c = a.split("_")
            chains.setdefault((fw, int(sd[1:])), []).append("_".join(c))
        rows = ["**CHAIN window (descriptive; commissioned after the main results were seen, erratum 16). Per chain: held-out mean of each ACCEPTED intermediate candidate (k = 10, test-20) minus the in-window seed (n = 20), with the artifact-level CR1 CI; the last row of each chain is the final champion from the MAIN window, shown for reference and NOT in this window (different time block). 'search-time rollouts' = cumulative counted rollouts at the candidate's evaluation, from candidates.jsonl.**", "",
                "| chain | step | candidate | search-time rollouts | held-out mean | delta vs in-window seed | 95% CI | step change |", "|---|---|---|---|---|---|---|---|"]
        for (fw, sd), cs in sorted(chains.items()):
            cs = sorted(cs)
            prev = None
            cf = [json.loads(l) for l in open(glob.glob(os.path.join(RUNS, "V3", "B1", fw, f"s{sd}", "**", "candidates.jsonl"), recursive=True)[0])]
            roll = {r["candidate"]: r.get("rollouts_cum") for r in cf}
            for i, c in enumerate(cs, 1):
                key = f"{fw}_s{sd}_{c}"
                v = Wc.M[(key, 0)]
                d = [None if (x is None or y is None) else x - y for x, y in zip(v, Wc.seedvec)]
                m = mean_ci(d, Wc.fam)
                mean = mean_ci(v, Wc.fam)["mean"]
                step = "" if prev is None else sgn(mean - prev)
                prev = mean
                rows.append(f"| {fw} s{sd} | {i} | {c} | {roll.get(c, '')} | {f(mean)} | {sgn(m['mean'])} | [{f(m['ci'][0])}, {f(m['ci'][1])}] | {step} |")
            fin = json.load(open(os.path.join(RUNS, "V3", "B1", fw, f"s{sd}", "run_summary.json"))).get("champion")
            v = Wm.M[(fw, sd)]
            d = [None if (x is None or y is None) else x - y for x, y in zip(v, Wm.seedvec)]
            m = mean_ci(d, Wm.fam); mean = mean_ci(v, Wm.fam)["mean"]
            rows.append(f"| {fw} s{sd} | final | {fin} (main window) | {roll.get(fin, '')} | {f(mean)} | {sgn(m['mean'])} vs main-window seed | [{f(m['ci'][0])}, {f(m['ci'][1])}] | {sgn(mean - prev) + ' (cross-window)' if prev is not None else ''} |")
        rows.append("")
        chain_md = rows
    # ---- write per-suite markdown
    ARMLINES = {}
    for w in WINDOWS:
        L = [f"# Window {w}: per-arm tables (" + ("descriptive CHAIN window, amendment 12 errata 15, 16" if w.startswith("V3B1CHAIN") else "released under the V3 B1 LATE freeze declaration, amendment 12 erratum 13" if w.startswith("V3B1LATE") else "released under the V3 B1 freeze declaration, amendment 12 erratum 8" if w.startswith("V3") else "user-directed early unblinding, erratum 36") + ")", ""]
        nT = len(W[w].tasks); nF = len(set(W[w].fam))
        L += [f"Task set: {nT} tasks, {nF} families (cluster = family; split filter {SPLITS[w]}). Primary basis infra_final = failure; sensitivity infra_final = missing. Mean (as measured) includes the physical re-score of inert artifacts; mean (inert -> seed) is the contrast basis.", ""]
        if w.startswith("V2/") and w != "V2/A":
            L += ["v2 note: hc2/ao2 searches that returned the seed have no scored cell (erratum 11 (3)); they enter at the in-window seed score, delta 0. ao21 (v2.1) is inert by construction and no window cell exists.", ""]
        # synthesize ao2/ao21 etc. for V2 windows
        L += arm_table(W[w], Ws[w]) if True else []
        L.append("")
        if w in ("V3B1/main", "V3B1/traineval"):
            L += [f"**Per-framework {'train-30 re-evaluation (descriptive, k = 5)' if w.endswith('traineval') else 'test'} mean (T = {len(W[w].tasks)}; mean of the 3 per-seed means; SE = SD of the 3 per-seed means / sqrt(3), n = 3 search seeds; per-seed means as measured)**", "",
                  "| framework | mean | SE across seeds | per-seed means | 95% CI of mean (artifact-level, CR1) |", "|---|---|---|---|---|"]
            for a in [x for x in ("seed", "seed-check") if (x, 0) in W[w].M] + sorted(x for x in W[w].arms if x not in ("seed", "seed-check")):
                if a in ("seed", "seed-check"):
                    v = W[w].M[(a, 0)]; mm = mean_ci(v, W[w].fam)
                    L.append(f"| {a} (n = {W[w].trials(a) or '-'} trials/task) | {f(mm['mean'])} | - | - | [{f(mm['ci'][0])}, {f(mm['ci'][1])}] |")
                    continue
                pm = []
                for sd in sorted(W[w].seeds_of[a]):
                    xs = [x for x in W[w].M[(a, sd)] if x is not None]
                    pm.append(sum(xs) / len(xs))
                mu = sum(pm) / len(pm)
                se = statistics.stdev(pm) / math.sqrt(len(pm)) if len(pm) > 1 else float("nan")
                mm = mean_ci(seedavg([W[w].M[(a, sd)] for sd in sorted(W[w].seeds_of[a])]), W[w].fam)
                L.append(f"| {a} | {f(mu)} | {f(se)} | {', '.join(f(x) for x in pm)} | [{f(mm['ci'][0])}, {f(mm['ci'][1])}] |")
            L.append("")
            if w == "V3B1/traineval":
                Wm = W["V3B1/main"]
                L += ["**Train re-evaluation vs test, per framework (descriptive; delta = framework minus the seed scored in the same block; train = the 30 official train ids re-scored at k = 5 with fresh seeds, test = the 20 official test ids at k = 10; 'train minus test' = the selection-to-final gap in the sense of 5P-2, with the train re-score in place of the search-time selection split; SE across the 3 seeds)**", "",
                      "| framework | train delta vs seed | SE | test delta vs seed | SE | train minus test |", "|---|---|---|---|---|---|"]
                def seedmeans(Wx, a, ref):
                    rm = sum(x for x in ref if x is not None) / sum(1 for x in ref if x is not None)
                    out = []
                    for sd in sorted(Wx.seeds_of[a]):
                        xs = [x for x in Wx.M[(a, sd)] if x is not None]
                        out.append(sum(xs) / len(xs) - rm)
                    return out
                for a in sorted(x for x in W[w].arms if x not in ("seed", "seed-check")):
                    tr = seedmeans(W[w], a, W[w].seedvec); te = seedmeans(Wm, a, Wm.seedvec)
                    mtr, mte = sum(tr) / 3, sum(te) / 3
                    setr = statistics.stdev(tr) / math.sqrt(3); sete = statistics.stdev(te) / math.sqrt(3)
                    L.append(f"| {a} | {sgn(mtr)} | {f(setr)} | {sgn(mte)} | {f(sete)} | {sgn(mtr - mte)} |")
                L.append("")
        if w == "V3B1LATE/main":
            Wm = W["V3B1/main"]
            L += ["**Window-to-window noise check (descriptive; the same frozen artifacts scored in the main window and again here; difference = this window minus main window; task-paired CR1 on the per-task difference of seed-averaged scores; hl-v0 and ACE have no main-window cell). It is a measure of how much the same artifact moves between time blocks and enters no test.**", "",
                  "| cell | main window mean | this window mean | difference | 95% CI | per-seed difference |", "|---|---|---|---|---|---|"]
            for a in ["seed", "seed-check"] + ["hcstock", "hc3", "ao22"]:
                if a in ("seed", "seed-check"):
                    x, y = W[w].M[(a, 0)], Wm.M[(a, 0)]
                    ps = ""
                else:
                    x = seedavg([W[w].M[(a, sd)] for sd in range(3)]); y = seedavg([Wm.M[(a, sd)] for sd in range(3)])
                    ps = ", ".join(sgn(mean_ci(W[w].M[(a, sd)], W[w].fam)["mean"] - mean_ci(Wm.M[(a, sd)], Wm.fam)["mean"], 3) for sd in range(3))
                dd = [None if (u is None or v is None) else u - v for u, v in zip(x, y)]
                m = mean_ci(dd, W[w].fam)
                L.append(f"| {a} | {f(mean_ci(y, Wm.fam)['mean'])} | {f(mean_ci(x, W[w].fam)['mean'])} | {sgn(m['mean'])} | [{f(m['ci'][0])}, {f(m['ci'][1])}] | {ps} |")
            L.append("")
        if w == "V3B1CHAIN/main" and chain_md:
            L += chain_md
        drift = seed_drift(w)
        if drift:
            L += [f"Seed drift (5I, in-window seed, task-demeaned): blocks (index, mean, SE, n) = " + "; ".join(f"{k}: {sgn(m,3)} (SE {se:.3f}, n={n})" for k, m, se, n in drift["blocks"]) +
                  f". Range {drift['range']:.3f}, SE of difference {drift['se_of_diff']:.3f}, drift flag (>2 SE): {drift['flag_gt_2se']}.", ""]
        sc = [a for a in ("seed", "seed-check") if (a, 0) in W[w].M]
        if len(sc) == 2:
            d = pcb.paired_cluster_bootstrap([W[w].M[("seed-check", 0)]], [W[w].M[("seed", 0)]], W[w].fam, B=20)
            L += [f"Seed-check minus seed (empirical null of window noise, 9D(ii)): {sgn(d['theta'])}, 95% CI [{f(d['cr_ci'][0])}, {f(d['cr_ci'][1])}], p {pf(d['cr_p_two_sided'])}.", ""]
        # inert re-measurement
        inr = []
        for (a, s), iv in sorted(W[w].inert.items()):
            if iv and (a, s) in W[w].M:
                d = pcb.paired_cluster_bootstrap([W[w].M[(a, s)]], [W[w].seedvec], W[w].fam, B=20)
                inr.append(f"{a}/s{s}: {sgn(d['theta'])} [{f(d['cr_ci'][0])}, {f(d['cr_ci'][1])}]")
        if inr:
            L += ["Inert artifacts re-scored in this window (as measured minus in-window seed; identical content, so this is pure measurement noise; excluded from every contrast): " + "; ".join(inr), ""]
        if drift and drift["flag_gt_2se"]:
            adj, eff = block_adjusted(w, W[w])
            L += [f"**5I block-adjusted headline (seed drift > 2 SE): delta vs seed after subtracting the seed's task-demeaned block effects from every trial (block effects {eff})**", "", "| arm | block-adjusted delta vs seed | 95% CI (artifact, CR1) | per-seed |", "|---|---|---|---|"]
            for arm, th, ci, ps in adj:
                L.append(f"| {arm} | {sgn(th)} | [{f(ci[0])}, {f(ci[1])}] | {', '.join(sgn(x,2) for x in ps)} |")
            L.append("")
            J.setdefault("block_adjusted", {})[w] = [(a, th, ci, ps) for a, th, ci, ps in adj]
        for F, dag, tost in fams.get(w, []):
            L += fam_table(F, tost, dag) + [""]
        if w.startswith("V21/"):
            sx = w[-1]
            L += ["**v2.1-AO2 (erratum 43 champions)**: the P2-accepted candidates whose commit was voided by the pooled-mode defect; secondary version (11D). Literal-final-state reading beside it: all three champions = the seed, delta 0 by construction (no scoring needed).", ""]
            L += fam_table(famv21[sx]) + [""]
            if sx == "A":
                a21 = [None if (x is None or y is None) else x - y for x, y in zip(seedavg(W[w].rows("ao21")[0]), W[w].seedvec)]
                a20 = [None if (x is None or y is None) else x - y for x, y in zip(seedavg(W["V2/A"].rows("ao2")[0]), W["V2/A"].seedvec)]
                dd = [None if (x is None or y is None) else x - y for x, y in zip(a21, a20)]
                m = mean_ci(dd, W[w].fam)
                m21, m20 = mean_ci(a21, W[w].fam), mean_ci(a20, W[w].fam)
                L += ["**Descriptive row: ao21 vs v2.0 AO-2 (= the v2 start), each against its own window's seed** (different windows and time blocks, never pooled; task-paired CR1 on the difference of seed-averaged deltas):", "",
                      "| quantity | value | 95% CI |", "|---|---|---|",
                      f"| ao21 delta vs its window seed (V21/A) | {sgn(m21['mean'])} | [{f(m21['ci'][0])}, {f(m21['ci'][1])}] |",
                      f"| v2.0 AO-2 delta vs its window seed (V2/A) | {sgn(m20['mean'])} | [{f(m20['ci'][0])}, {f(m20['ci'][1])}] |",
                      f"| ao21 minus v2.0 AO-2 (accepted-candidate effect over the v2 start) | {sgn(m['mean'])} | [{f(m['ci'][0])}, {f(m['ci'][1])}] |", ""]
                J.setdefault("v21_A_vs_v20_ao2", {"diff": m["mean"], "ci": m["ci"]})
            for sd in sorted(W[w].seeds_of.get("ao21", ())):
                if W[w].inert.get(("ao21", sd)) or ("ao21", sd) not in W[w].M:
                    continue
                parts = []
                for lab, ref in (("in-window seed", W[w].seedvec), ("seed-check (same artifact, n as the arms)", W[w].M[("seed-check", 0)])):
                    r = pcb.paired_cluster_bootstrap([W[w].M[("ao21", sd)]], [ref], W[w].fam, B=20)
                    parts.append(f"vs {lab}: {sgn(r['theta'])} [{f(r['cr_ci'][0])}, {f(r['cr_ci'][1])}], p {pf(r['cr_p_two_sided'])}")
                L.append(f"Scored champion ao21 s{sd} alone (descriptive{'; the family row above averages it with the seeds that returned the seed' if any(W[w].inert.get(('ao21', q)) for q in W[w].seeds_of['ao21']) else ''}): " + "; ".join(parts) + ".")
            L.append("")
        if w.startswith("V2/"):
            s = w[3]
            if s == "A":
                L += ["**Suite A v2 start (erratum 38, 40):** v2 A started from the v1 seed + empty helper scaffold + 3 prompt lines; every helper script in the HC-2 champions was written by CapEvolve. AO-2 returned its v2 start (one artifact, three identical cells; artifact-level only). AO-2 vs seed = scaffold effect (descriptive); HC-2 vs AO-2 = search effect (descriptive); HC-2 vs seed is the registered row.", ""]
            L += fam_table(famv2[s]) + [""] + fam_table(famv2[s + "_desc"]) + [""]
        # infra
        rep = infra_counts(w)
        tot = defaultdict(int)
        L += ["Infrastructure and missing cells (per_arm_report.json of THIS window; counts only; key prefix is the scoring mode):", "", "| mode\|arm (mode B = matched-checkpoint artifacts; it is NOT the suite letter) | jobs | done | infra attempts | infra_final | hangs | missing hang | candidate errors | empty output | raw tool text |", "|---|---|---|---|---|---|---|---|---|---|"]
        for k, v in sorted(rep.items()):
            for kk in ("jobs", "done", "infra_attempts", "infra_final", "hangs", "missing_hang", "candidate_errors", "empty_output", "raw_tool_text_last"):
                tot[kk] += v.get(kk, 0)
            if v.get("infra_final") or v.get("missing_hang") or v.get("candidate_errors") or v.get("infra_attempts"):
                L.append(f"| {k} | {v['jobs']} | {v['done']} | {v['infra_attempts']} | {v['infra_final']} | {v['hangs']} | {v['missing_hang']} | {v['candidate_errors']} | {v['empty_output']} | {v['raw_tool_text_last']} |")
        L.append(f"| TOTAL | {tot['jobs']} | {tot['done']} | {tot['infra_attempts']} | {tot['infra_final']} | {tot['hangs']} | {tot['missing_hang']} | {tot['candidate_errors']} | {tot['empty_output']} | {tot['raw_tool_text_last']} |")
        L += ["(rows with all-zero infra, missing and candidate-error counts omitted)", ""]
        # latency / tokens
        lat = latency(w); rt = raw_tokens(w)
        L += ["Target latency and tokens per final rollout (wall seconds from results_trials t_start to t_end of the final attempt; tokens = raw `tokens` field per logged attempt, semantics as recorded by the runner, not re-derived):", "", "| arm | trials | mean wall s | median wall s | mean tokens/attempt | mean LLM calls/attempt |", "|---|---|---|---|---|---|"]
        for a in sorted(lat):
            m, md_, n = lat[a]
            t = rt.get(a) or (None, None, 0)
            L.append(f"| {a} | {n} | {m:.0f} | {md_:.0f} | {f(t[0],0) if t[0] else 'n/a'} | {f(t[1],1) if t[1] else 'n/a'} |")
        L.append("")
        # cost
        try:
            cr = cost_rows(w)
        except Exception as e:
            cr = []
        if cr:
            L += ["Search cost (optimizer = Sonnet 5.5 at the proxy list price of protocol/pricing.json, from the run's cost_summary.json; blank = no cost_summary.json in the run dir; search rollouts = counted rollouts of the B* manifest for v1 windows, and for v2 windows the run's logs/rollout_counter.json total on A, or state.json metric_calls on tau, which includes the host-side finalize rollouts and is NOT the counted-rollout definition):", "", "| arm | seed | optimizer USD (proxy) | optimizer non-cache-read tokens | optimizer calls | search rollouts | source |", "|---|---|---|---|---|---|---|"]
            for r in cr:
                L.append(f"| {r['arm']} | {r['seed']} | {f(r['optimizer_usd_proxy'],2) if r['optimizer_usd_proxy'] is not None else ''} | {r['optimizer_noncache_tokens'] if r['optimizer_noncache_tokens'] is not None else ''} | {r['optimizer_calls'] if r['optimizer_calls'] is not None else ''} | {r['search_rollouts'] if r['search_rollouts'] is not None else ''} | {r.get('source') if r['optimizer_usd_proxy'] is not None else ''} |")
            L.append("")
        md[w] = L
        J[w] = {"families": [F for F, _, _ in fams.get(w, [])], "cost": cr}
    J["v2_families"] = famv2
    J["v21_families"] = famv21

    # ---- v1 vs v2
    L = ["# v1 versus v2 (descriptive; user-directed early unblinding)", "",
         "Each delta is measured inside its own window against that window's own in-window seed (n = 10 trials per task on D and E). Windows are different time blocks and are never pooled. "
         "Rows are DESCRIPTIVE unless marked; the registered v2 confirmatory rows are family V2 (11G) in the v2 window files. Inert artifacts (champion = seed) enter at the seed score, delta 0.", ""]
    PAIRS = {"A": {"v1 hc (rule P hill-climb)": ("A", "hc"), "v1 hcstock (stock-gate hill-climb)": ("A", "hcstock"), "v1 ao (agent-optimize, inert)": ("A", "ao")},
             "D": {"v1 pt (stock-gate hill-climb, reference)": ("D", "pt"), "v1 rulep (rule P hill-climb)": ("D", "rulep")},
             "E": {"v1 pt (stock-gate hill-climb, reference)": ("E", "pt"), "v1 rulep (rule P hill-climb)": ("E", "rulep"), "v1 ao (agent-optimize, dagger)": ("E", "ao")}}
    V2ARMS = {"hc2": "v2.0 HC-2", "ao2": "v2.0 AO-2", "ao21": "v2.1 AO-2 (inert by construction)"}
    V2ARMS_A = {"hc2": "v2.0 HC-2", "ao2": "v2.0 AO-2 (= v2 start: scaffold effect; not inert)"}
    summary = []
    for s in "ADE":
        k2 = f"V2/{s}"
        w2 = W[k2]
        V2A = V2ARMS_A if s == "A" else V2ARMS
        if s != "A":
            w2.seeds_of["ao21"] = {0, 1, 2}
            for sd in (0, 1, 2):
                w2.inert[("ao21", sd)] = True
        L += [f"## Suite {s} ({ {'A': 'SpreadsheetBench, T = 70, seed n = 2', 'D': 'tau2 retail, test 40', 'E': 'tau2 airline, test 20'}[s] })", ""]
        if s == "A":
            L += ["v2 A started from the v1 seed + empty helper scaffold + 3 prompt lines (erratum 40); every helper script is CapEvolve-written. The A v2.1-AO2 runs have no scored cell.", ""]
        L += ["| arm (window) | delta vs in-window seed | 95% CI (artifact, CR1) | 95% CI (pipeline, t2) | inert seeds | per-seed delta (seed 0, 1, 2) |", "|---|---|---|---|---|---|"]
        deltas = {}
        for lab, (win, arm) in PAIRS[s].items():
            c = contrast(W[win], arm, "seed")
            deltas[lab] = (win, arm, c)
        for arm, lab in V2A.items():
            c = contrast(w2, arm, "seed")
            deltas[lab] = (k2, arm, c)
        for lab, (win, arm, c) in deltas.items():
            pp = c.get("pipe_ci")
            L.append(f"| {lab} ({win}) | {sgn(c['theta'])} | [{f(c['cr_ci'][0])}, {f(c['cr_ci'][1])}] | {('[%s, %s]' % (f(pp[0]), f(pp[1]))) if pp else 'n/a'} | {c['inert_a']} | {', '.join(sgn(x,3) for x in c['per_seed'])} |")
        # anchors
        g1 = contrast(W[s], "gepa", "seed"); g2 = contrast(w2, "gepa", "seed")
        L += ["", f"Window-shift controls (same GEPA artifact scored in both windows when the tree hashes match): GEPA delta vs seed v1 window {sgn(g1['theta'])} [{f(g1['cr_ci'][0])}, {f(g1['cr_ci'][1])}], v2 window {sgn(g2['theta'])} [{f(g2['cr_ci'][0])}, {f(g2['cr_ci'][1])}]. "
              f"Seed mean v1 {f(mean_ci(W[s].seedvec, W[s].fam)['mean'])} vs v2 {f(mean_ci(w2.seedvec, w2.fam)['mean'])}; GEPA mean v1 {f(mean_ci(seedavg(W[s].rows('gepa')[0]), W[s].fam)['mean'])} vs v2 {f(mean_ci(seedavg(w2.rows('gepa')[0]), w2.fam)['mean'])}.",
              f"GEPA artifact tree hashes identical across windows: {all(W[s].tree.get(('gepa', i)) == w2.tree.get(('gepa', i)) and W[s].tree.get(('gepa', i)) for i in range(3))}.", ""]
        # difference of deltas v2 minus v1, task-paired
        L += ["Difference of deltas (v2 arm minus v1 arm, each against its own window's seed; task-paired CR1 on the per-task difference of seed-averaged deltas; descriptive):", "",
              "| v2 arm | v1 arm | v2 minus v1 | 95% CI |", "|---|---|---|---|"]
        for arm2, lab2 in V2A.items():
            for lab1, (win1, arm1) in PAIRS[s].items():
                d2 = [None if (a is None or b is None) else a - b for a, b in zip(seedavg(w2.rows(arm2)[0]), w2.seedvec)]
                d1 = [None if (a is None or b is None) else a - b for a, b in zip(seedavg(W[win1].rows(arm1)[0]), W[win1].seedvec)]
                dd = [None if (a is None or b is None) else a - b for a, b in zip(d2, d1)]
                m = mean_ci(dd, w2.fam)
                L.append(f"| {lab2} | {lab1} | {sgn(m['mean'])} | [{f(m['ci'][0])}, {f(m['ci'][1])}] |")
                summary.append((s, lab2, lab1, m["mean"], m["ci"]))
        L.append("")
    md["v1v2"] = L
    J["v1v2_summary"] = [{"suite": a, "v2": b, "v1": c, "diff": d, "ci": e} for a, b, c, d, e in summary]

    for w, L in md.items():
        name = w.replace("/", "_")
        open(os.path.join(OUT, f"window_{name}.md" if w != "v1v2" else "v1_vs_v2.md"), "w").write("\n".join(L) + "\n")
    json.dump(J, open(os.path.join(OUT, "unblind_results.json"), "w"), indent=1, default=str)
    print("written", list(md))


if __name__ == "__main__":
    main()
