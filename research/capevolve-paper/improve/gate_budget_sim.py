"""Gate / budget-policy simulation calibrated to the E22 null pool (40 evaluations of the seed, 49 tasks).

Model: per-task success p_i = the pool's empirical task means; every rollout is an independent Bernoulli(q_i)
(pool SD of the eval mean 0.065 vs binomial 0.071 => no shared per-evaluation noise detectable).
Candidate with true effect d: q = p + d*w/mean(w), w = (1-p) (d>0) or p (d<0)  (diffuse edit; see sim_common.apply_edit).
Incumbent estimate phat_i = mean of m fresh Bernoulli(p_i) trials (m=1 for the stock/rule-P screen).
Single-candidate designs spend rollouts as passes over a random permutation of the tasks (no task twice before all once).
Pure stdlib. usage: python3 -I gate_budget_sim.py single|multi|merge|all   (writes JSON next to this file)
"""
import json, math, multiprocessing as mp, os, random, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "core"))
from cap_evolve import promotion  # real rule-P code

POOL = json.load(open(HERE / "null_p.json"))["p"]
T0 = len(POOL)
V = sum(x * (1 - x) for x in POOL) / T0         # 0.147 per-rollout Bernoulli variance
NCPU = min(60, os.cpu_count() or 4)


def edit(p, d):
    if d == 0:
        return list(p)
    w = [(1 - x) if d > 0 else x for x in p]; s = sum(w) / len(w)
    return [min(1.0, max(0.0, x + d * wi / s)) for x, wi in zip(p, w)]


def binom_mean(rng, pi, m):
    return sum(rng.random() < pi for _ in range(m)) / m


def phat_of(rng, p, m):
    return [binom_mean(rng, x, m) for x in p]


def ncdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


class Stream:
    """Candidate rollouts as passes over the tasks; keeps sum of deltas vs phat and per-task counts."""
    def __init__(self, rng, q, phat, m):
        self.rng, self.q, self.ph, self.m = rng, q, phat, m
        self.T = len(q); self.n = 0; self.sd = 0.0; self.j = [0] * self.T; self.sj2 = 0; self.perm = []; self.sy = 0.0

    def draw(self, k):
        for _ in range(k):
            if not self.perm:
                self.perm = list(range(self.T)); self.rng.shuffle(self.perm)
            t = self.perm.pop()
            y = 1.0 if self.rng.random() < self.q[t] else 0.0
            self.n += 1; self.sd += y - self.ph[t]; self.sy += y
            self.sj2 += 2 * self.j[t] + 1; self.j[t] += 1

    def mean(self):
        return self.sd / self.n

    def se(self, v=V):
        return math.sqrt(v * (1.0 / self.n + self.sj2 / (self.m * self.n * self.n)))

    def z(self):
        return self.mean() / self.se()


# ----------------------------------------------------------------------------- single-candidate designs
# each returns (accept, rollouts_on_candidate_side_incl_confirmation_both_sides, stages)
def d_stock(rng, q, par, k=1.0, T=T0):
    ph = phat_of(rng, par, 1); y = [1.0 if rng.random() < qi else 0.0 for qi in q]
    d = [a - b for a, b in zip(y, ph)]
    m, se, n = promotion.paired_stats(d)
    return (m > k * se and m > 0), T, 1


def d_P(rng, q, par, k=1.0, nc=3, z=1.282, dmin=0.0, T=T0):
    ph = phat_of(rng, par, 1); y = [1.0 if rng.random() < qi else 0.0 for qi in q]
    d = [a - b for a, b in zip(y, ph)]
    if not promotion.screen(d, k)["pass"]:
        return False, T, 1
    cd = [binom_mean(rng, a, nc) - binom_mean(rng, b, nc) for a, b in zip(q, par)]
    return promotion.confirm(cd, dmin, z, T, 0.6)["pass"], T + 2 * T * nc, 2


def seq_driver(rng, q, par, m, looks, decide, vref=V):
    ph = phat_of(rng, par, m); s = Stream(rng, q, ph, m); prev = 0
    for i, n in enumerate(looks):
        s.draw(n - prev); prev = n
        r = decide(s, i, len(looks))
        if r is not None:
            return r, s.n, i + 1
    return False, s.n, len(looks)


GS_LOOKS = (12, 24, 49, 98, 147)
GS_FUT = (-0.5, 0.0, 0.3, 0.7)


def d_gs(rng, q, par, c=2.0, m=4, looks=GS_LOOKS, fut=GS_FUT):
    nmax = looks[-1]
    def dec(s, i, K):
        z = s.z()
        if z >= c * math.sqrt(nmax / s.n):
            return True
        if i < K - 1 and z < fut[i]:
            return False
        return None
    return seq_driver(rng, q, par, m, looks, dec)


def d_fixed(rng, q, par, c=1.7, n=98, m=4):
    return seq_driver(rng, q, par, m, (n,), lambda s, i, K: s.z() >= c)


def d_sprt(rng, q, par, A=3.0, d1=0.10, m=4, nmax=147, step=6):
    B = math.log(0.2 / 0.95)
    looks = tuple(range(step, nmax + 1, step))
    def dec(s, i, K):
        llr = d1 * (s.mean() - d1 / 2) / (s.se() ** 2)
        if llr >= A: return True
        if llr <= B: return False
        return None
    return seq_driver(rng, q, par, m, looks, dec)


def d_hoeff(rng, q, par, alpha=0.05, m=4, nmax=147, step=6, kind="H"):
    looks = tuple(range(step, nmax + 1, step))
    def dec(s, i, K):
        n = s.n; dn = 6 * alpha / (math.pi ** 2 * (i + 1) ** 2)   # union over looks
        if kind == "H":     # Hoeffding on d in [-1,1]
            r = math.sqrt(2 * math.log(1 / dn) / n)
        else:               # empirical Bernstein with known sd (Maurer-Pontil, b=2)
            r = s.se() * math.sqrt(2 * math.log(2 / dn)) + 7 * 2 * math.log(2 / dn) / (3 * (n - 1))
        mu = s.mean()
        if mu - r > 0: return True
        if mu + r < 0: return False
        return None
    return seq_driver(rng, q, par, m, looks, dec)


def d_bayes(rng, q, par, pstar=0.9, tau=0.05, dstar=0.02, m=4, nmax=147, step=6, fut=0.02):
    looks = tuple(range(step, nmax + 1, step))
    def dec(s, i, K):
        v = s.se() ** 2; pv = 1 / (1 / tau ** 2 + 1 / v); pm = pv * s.mean() / v
        pr = 1 - ncdf((dstar - pm) / math.sqrt(pv))
        if pr >= pstar: return True
        if pr < fut: return False
        return None
    return seq_driver(rng, q, par, m, looks, dec)


DESIGNS = {
    "stock (k=1, 49 rollouts)": (d_stock, {}),
    "rule P as run (n_conf3 z1.282 dmin0)": (d_P, {}),
    "rule P frozen (n_conf3 z2.0 dmin.02)": (d_P, dict(z=2.0, dmin=0.02)),
    "rule P n_conf10 z1.645 dmin.02": (d_P, dict(nc=10, z=1.645, dmin=0.02)),
}
CAL = {  # name -> (fn, base kwargs, parameter name, lo, hi, increasing-param-lowers-FA?)
    "fixed n=98, m_inc=4": (d_fixed, {}, "c", 0.5, 4.0),
    "group-sequential OBF (5 looks) + futility": (d_gs, {}, "c", 0.8, 4.0),
    "SPRT (d1=.10)": (d_sprt, {}, "A", 0.5, 8.0),
    "Bayes sequential (tau .05, P(d>.02)>=p*)": (d_bayes, {}, "pstar", 0.5, 0.9999),
}
NOMINAL = {
    "Hoeffding race (nominal alpha .05)": (d_hoeff, dict(kind="H")),
    "empirical-Bernstein race (nominal alpha .05)": (d_hoeff, dict(kind="EB")),
}
EFFECTS = (-0.05, 0.0, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20)


def _job(a):
    fn, kw, d, reps, seed = a
    rng = random.Random(seed); par = POOL; q = edit(par, d)
    acc = n = st = 0
    for _ in range(reps):
        r, nn, ss = fn(rng, q, par, **kw)
        acc += bool(r); n += nn; st += ss
    return acc, n, st, reps


def run_cell(fn, kw, d, reps=24000, seed0=1):
    per = reps // NCPU
    with mp.get_context("fork").Pool(NCPU) as pool:
        out = pool.map(_job, [(fn, kw, d, per, seed0 * 1000003 + i) for i in range(NCPU)])
    acc = sum(o[0] for o in out); n = sum(o[1] for o in out); st = sum(o[2] for o in out); R = sum(o[3] for o in out)
    return acc / R, n / R, st / R


def calibrate(fn, kw, pname, lo, hi, target=0.018, reps=24000):
    for _ in range(14):
        mid = (lo + hi) / 2
        fa, _, _ = run_cell(fn, {**kw, pname: mid}, 0.0, reps, seed0=7)
        if fa > target: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def single():
    res = {}
    for name, (fn, kw) in DESIGNS.items():
        res[name] = {"params": kw, "cells": {str(d): run_cell(fn, kw, d) for d in EFFECTS}}
        print(name, {k: tuple(round(x, 3) for x in v) for k, v in res[name]["cells"].items()}, flush=True)
    for name, (fn, kw, pn, lo, hi) in CAL.items():
        v = calibrate(fn, kw, pn, lo, hi)
        k2 = {**kw, pn: v}
        res[name] = {"params": k2, "cells": {str(d): run_cell(fn, k2, d, seed0=3) for d in EFFECTS}}
        print(name, k2, {k: tuple(round(x, 3) for x in v) for k, v in res[name]["cells"].items()}, flush=True)
    for name, (fn, kw) in NOMINAL.items():
        res[name] = {"params": kw, "cells": {str(d): run_cell(fn, kw, d, seed0=5) for d in EFFECTS}}
        print(name, {k: tuple(round(x, 3) for x in v) for k, v in res[name]["cells"].items()}, flush=True)
    (HERE / "gate_budget_single.json").write_text(json.dumps(res, indent=1))


# ----------------------------------------------------------------------------- multi-candidate rounds (K candidates, shared incumbent)
K = 8
GS_C = 2.033


def mix_effects(rng, pnull=0.55, pharm=0.15):
    out = []
    for _ in range(K):
        u = rng.random()
        out.append(0.0 if u < pnull else (-0.05 if u < pnull + pharm else rng.uniform(0.04, 0.14)))
    return out


def conf_stream(rng, q, ph, m, n):
    s = Stream(rng, q, ph, m); s.draw(n); return s


def champ(cands):
    """cands: list of (j, apparent) accepted; champion = max apparent."""
    return max(cands, key=lambda x: x[1]) if cands else None


def m_stock(rng, ds, par, qs, **kw):
    ph = phat_of(rng, par, 1); acc = []
    for j, q in enumerate(qs):
        y = [1.0 if rng.random() < qi else 0.0 for qi in q]
        m, se, n = promotion.paired_stats([a - b for a, b in zip(y, ph)])
        if m > se and m > 0: acc.append((j, m))
    return champ(acc), K * T0, 1


def m_P(rng, ds, par, qs, **kw):
    ph = phat_of(rng, par, 1); acc = []; cost = K * T0
    for j, q in enumerate(qs):
        y = [1.0 if rng.random() < qi else 0.0 for qi in q]
        if not promotion.screen([a - b for a, b in zip(y, ph)], 1.0)["pass"]: continue
        cost += 2 * 3 * T0
        cd = [binom_mean(rng, a, 3) - binom_mean(rng, b, 3) for a, b in zip(q, par)]
        c = promotion.confirm(cd, 0.0, 1.282, T0, 0.6)
        if c["pass"]: acc.append((j, c["mean"]))
    return champ(acc), cost, 2


def m_gs(rng, ds, par, qs, c=GS_C, **kw):
    ph = phat_of(rng, par, 4); acc = []; cost = 0; st = 0; nmax = GS_LOOKS[-1]
    for j, q in enumerate(qs):
        s = Stream(rng, q, ph, 4); prev = 0
        for i, n in enumerate(GS_LOOKS):
            s.draw(n - prev); prev = n; z = s.z()
            if z >= c * math.sqrt(nmax / n): acc.append((j, s.mean())); break
            if i < len(GS_LOOKS) - 1 and z < GS_FUT[i]: break
        cost += s.n; st = max(st, i + 1)
    return champ(acc), cost, st


def m_sh(rng, ds, par, qs, zc=2.0, nconf=98, n1=12, n2=24, m=4, eps=0.0, ctrl=False, mc_=2, **kw):
    ph = phat_of(rng, par, m); S = [Stream(rng, q, ph, m) for q in qs]
    for s in S: s.draw(n1)
    cost = n1 * K
    keep = [j for j in sorted(range(K), key=lambda j: -S[j].z())[:K // 2] if S[j].mean() > 0]
    for j in keep: S[j].draw(n2); cost += n2
    keep = [j for j in sorted(keep, key=lambda j: -S[j].z())[:K // 4] if S[j].mean() > 0]
    acc = []
    if ctrl and keep:                               # concurrent control: re-measure the incumbent beside the confirmation
        ph_c = phat_of(rng, edit(par, eps), mc_); cost += mc_ * T0; mc = mc_
    else:
        ph_c, mc = ph, m
    for j in keep:                                  # FRESH confirmation, never reuses screen rollouts
        f = conf_stream(rng, qs[j], ph_c, mc, nconf); cost += nconf
        if f.z() >= zc: acc.append((j, f.mean()))
    return champ(acc), cost, 3 + bool(keep)


def m_ts(rng, ds, par, qs, zc=2.0, budget=300, batch=24, nconf=98, tau=0.07, **kw):
    ph = phat_of(rng, par, 4); S = [Stream(rng, q, ph, 4) for q in qs]
    for s in S: s.draw(12)
    cost = 12 * K; waves = 1
    def post(s):
        v = s.se() ** 2; pv = 1 / (1 / tau ** 2 + 1 / v); return pv * s.mean() / v, pv
    while cost + batch <= budget:
        P = [post(s) for s in S]
        pr = [1 - ncdf((0.02 - pm) / math.sqrt(pv)) for pm, pv in P]
        if max(pr) < 0.05: break
        take = [0] * K
        for _ in range(batch // 6):                 # 6-rollout units, each to the Thompson argmax
            th = [rng.gauss(pm, math.sqrt(pv)) for pm, pv in P]
            take[max(range(K), key=lambda j: th[j])] += 6
        for j, k in enumerate(take):
            if k: S[j].draw(k)
        cost += batch; waves += 1
    P = [post(s) for s in S]; j = max(range(K), key=lambda j: P[j][0])
    if P[j][0] <= 0.02: return None, cost, waves
    f = conf_stream(rng, qs[j], ph, 4, nconf); cost += nconf
    return ((j, f.mean()) if f.z() >= zc else None), cost, waves + 1


MULTI = {"stock x8 (k=1)": (m_stock, {}), "rule P as run x8": (m_P, {}), "group-sequential x8": (m_gs, {}),
         "successive halving 8>4>2 + fresh confirm": (m_sh, {}), "Thompson allocation + fresh confirm": (m_ts, {})}


def _mjob(a):
    fn, kw, mode, reps, seed = a
    rng = random.Random(seed); R = dict(n=0, any=0, good=0, bad=0, gain=0.0, infl=0.0, ninfl=0, cost=0, st=0, maxcost=0)
    for _ in range(reps):
        ds = [0.0] * K if mode == "null" else mix_effects(rng)
        par = POOL; eps = kw.get('eps', 0.0); qs = [edit(par, d + eps) if eps else edit(par, d) for d in ds]
        c, cost, st = fn(rng, ds, par, qs, **kw)
        R["n"] += 1; R["cost"] += cost; R["st"] += st
        if c is not None:
            j, app = c; R["any"] += 1; d = ds[j]
            R["good"] += d >= 0.04; R["bad"] += d <= 0; R["gain"] += d; R["infl"] += app - d; R["ninfl"] += 1
    return R


def run_multi(fn, kw, mode, reps=24000, seed0=11):
    per = reps // NCPU
    with mp.get_context("fork").Pool(NCPU) as pool:
        out = pool.map(_mjob, [(fn, kw, mode, per, seed0 * 7919 + i) for i in range(NCPU)])
    A = {k: sum(o[k] for o in out) for k in out[0]}; n = A["n"]
    return dict(p_champion=A["any"] / n, p_good=A["good"] / n, p_bad=A["bad"] / n, gain=A["gain"] / n,
                inflation=(A["infl"] / A["ninfl"]) if A["ninfl"] else float("nan"), rollouts=A["cost"] / n, stages=A["st"] / n,
                rollouts_per_good=(A["cost"] / A["good"]) if A["good"] else float("inf"))


def calibrate_multi(fn, target, lo=1.0, hi=4.5, reps=24000):
    for _ in range(12):
        mid = (lo + hi) / 2
        r = run_multi(fn, dict(zc=mid), "null", reps, seed0=13)
        if r["p_champion"] > target: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def sweeps():
    base = json.load(open(HERE / "gate_budget_multi.json"))["_fwer_target"]; out = {}
    def go(label, kw, mode_kw=None):
        zc = calibrate_multi(lambda *a, **k: m_sh(*a, **{**kw, **k}), base) if False else None
    def cal(kw, target=base):
        lo, hi = 1.0, 4.5
        for _ in range(11):
            mid = (lo + hi) / 2
            r = run_multi(m_sh, {**kw, "zc": mid}, "null", 16000, seed0=13)
            if r["p_champion"] > target: lo = mid
            else: hi = mid
        return (lo + hi) / 2
    for label, kw in [("m_inc=1", dict(m=1)), ("m_inc=2", dict(m=2)), ("m_inc=4 (default)", dict(m=4)), ("m_inc=8", dict(m=8)),
                      ("n1=16,n2=24", dict(n1=16)), ("n1=24,n2=24", dict(n1=24)), ("nconf=147", dict(nconf=147)),
                      ("nconf=196", dict(nconf=196)), ("nconf=49", dict(nconf=49))]:
        z = cal(kw); k2 = {**kw, "zc": z}
        out[label] = {"params": k2, "null": run_multi(m_sh, k2, "null", 16000), "mixed": run_multi(m_sh, k2, "mixed", 16000, seed0=17)}
        print(label, k2, json.dumps(out[label]["mixed"]), "FWER", round(out[label]["null"]["p_champion"], 3), flush=True)
    z0 = out["m_inc=4 (default)"]["params"]["zc"]
    for eps in (0.0, 0.03, 0.05):
        for ctrl in (False, True):
            kw = dict(zc=z0 if not ctrl else cal(dict(ctrl=True, eps=eps)), eps=eps, ctrl=ctrl)
            out[f"drift eps={eps} ctrl={ctrl}"] = {"params": kw, "null": run_multi(m_sh, kw, "null", 16000), "mixed": run_multi(m_sh, kw, "mixed", 16000, seed0=17)}
            print("drift", eps, ctrl, kw, "FWER", round(out[f"drift eps={eps} ctrl={ctrl}"]["null"]["p_champion"], 3),
                  "good", round(out[f"drift eps={eps} ctrl={ctrl}"]["mixed"]["p_good"], 3), flush=True)
    (HERE / "gate_budget_sweeps.json").write_text(json.dumps(out, indent=1))


def sweeps2():
    base = json.load(open(HERE / "gate_budget_multi.json"))["_fwer_target"]; out = {}
    def cal(kw):
        lo, hi = 1.0, 4.5
        for _ in range(11):
            mid = (lo + hi) / 2
            r = run_multi(m_sh, {**kw, "zc": mid}, "null", 16000, seed0=13)
            if r["p_champion"] > base: lo = mid
            else: hi = mid
        return (lo + hi) / 2
    for label, kw in [("nconf98 ctrl2", dict(nconf=98, mc_=2)), ("nconf147 ctrl3", dict(nconf=147, mc_=3)), ("nconf196 ctrl4", dict(nconf=196, mc_=4)),
                      ("nconf147 ctrl2", dict(nconf=147, mc_=2))]:
        kw = {**kw, "ctrl": True, "eps": 0.03}; z = cal(kw); k2 = {**kw, "zc": z}
        out[label] = {"params": k2, "null": run_multi(m_sh, k2, "null", 16000), "mixed": run_multi(m_sh, k2, "mixed", 16000, seed0=17)}
        print(label, round(z, 3), "FWER", round(out[label]["null"]["p_champion"], 3), {a: round(b, 3) for a, b in out[label]["mixed"].items()}, flush=True)
    (HERE / "gate_budget_sweeps2.json").write_text(json.dumps(out, indent=1))


# ----------------------------------------------------------------------------- merged-pool analysis
def boost(q, r):
    return [x + r * (1 - x) for x in q]


def m_merge(rng, ds, par, scheme, rho, zc, nF=33, nconf=98, mC=8, eps=0.0, mctrl=0):
    """One round of K candidates on a pool of 49 tasks. rho = mean 'seen-task memorisation' boost (per-candidate U(0,2rho)).
    scheme 'naive': feedback, screening and confirmation all on the same 49 tasks (proposer saw all their traces).
    scheme 'fc'   : F=nF tasks shown to the proposer + screening; C=49-nF tasks: confirm-only, no traces (no boost)."""
    T = len(par); idx = list(range(T)); rng.shuffle(idx); F, C = idx[:nF], idx[nF:]
    rj = [rng.uniform(0, 2 * rho) for _ in range(K)]
    qg = [edit(par, d + eps) if eps else edit(par, d) for d in ds]   # true generalising effect (+ time drift eps)
    if scheme == "naive":
        qs = [boost(qg[j], rj[j]) for j in range(K)]
        ph = phat_of(rng, par, 4); S = [Stream(rng, q, ph, 4) for q in qs]
        for s in S: s.draw(12)
        cost = 12 * K
        keep = [j for j in sorted(range(K), key=lambda j: -S[j].z())[:K // 2] if S[j].mean() > 0]
        for j in keep: S[j].draw(24); cost += 24
        keep = [j for j in sorted(keep, key=lambda j: -S[j].z())[:K // 4] if S[j].mean() > 0]
        acc = []
        for j in keep:
            f = conf_stream(rng, qs[j], ph, 4, nconf); cost += nconf
            if f.z() >= zc: acc.append((j, f.mean()))
        return champ(acc), cost, "full"
    parF = [par[i] for i in F]; parC = [par[i] for i in C]
    qF = [[boost(qg[j], rj[j])[i] for i in F] for j in range(K)]
    qC = [[qg[j][i] for i in C] for j in range(K)]
    phF = phat_of(rng, parF, 4); S = [Stream(rng, q, phF, 4) for q in qF]
    for s in S: s.draw(12)
    cost = 12 * K
    keep = [j for j in sorted(range(K), key=lambda j: -S[j].z())[:K // 2] if S[j].mean() > 0]
    for j in keep: S[j].draw(24); cost += 24
    keep = [j for j in sorted(keep, key=lambda j: -S[j].z())[:K // 4] if S[j].mean() > 0]
    if mctrl and keep:                                    # concurrent control on C (same drift as the candidates)
        phC = phat_of(rng, [edit(par, eps)[i] for i in C], mctrl); mm = mctrl; cost += mctrl * len(C)
    else:
        phC = phat_of(rng, parC, mC); mm = mC
    acc = []
    for j in keep:
        f = conf_stream(rng, qC[j], phC, mm, nconf); cost += nconf
        if f.z() >= zc: acc.append((j, f.mean()))
    return champ(acc), cost, "full"


def _mgjob(a):
    scheme, rho, zc, mode, reps, seed, nF, nconf, eps, mctrl = a
    rng = random.Random(seed); R = dict(n=0, any=0, good=0, bad=0, infl=0.0, ninfl=0, cost=0)
    for _ in range(reps):
        ds = [0.0] * K if mode == "null" else mix_effects(rng)
        c, cost, _ = m_merge(rng, ds, POOL, scheme, rho, zc, nF=nF, nconf=nconf, eps=eps, mctrl=mctrl)
        R["n"] += 1; R["cost"] += cost
        if c is not None:
            j, app = c; R["any"] += 1; R["good"] += ds[j] >= 0.04; R["bad"] += ds[j] <= 0; R["infl"] += app - ds[j]; R["ninfl"] += 1
    return R


def run_mg(scheme, rho, zc, mode, reps=16000, seed0=21, nF=33, nconf=98, eps=0.0, mctrl=0):
    per = reps // NCPU
    with mp.get_context("fork").Pool(NCPU) as pool:
        out = pool.map(_mgjob, [(scheme, rho, zc, mode, per, seed0 * 104729 + i, nF, nconf, eps, mctrl) for i in range(NCPU)])
    A = {k: sum(o[k] for o in out) for k in out[0]}; n = A["n"]
    return dict(p_champion=A["any"] / n, p_good=A["good"] / n, p_bad=A["bad"] / n,
                inflation=(A["infl"] / A["ninfl"]) if A["ninfl"] else float("nan"), rollouts=A["cost"] / n)


def merge():
    base = json.load(open(HERE / "gate_budget_multi.json"))["_fwer_target"]; out = {}
    for label, scheme, nF, nconf in [("naive merged pool (gate = feedback tasks), n=98", "naive", 49, 98),
                                      ("F33/C16 split, confirm on C n=98", "fc", 33, 98),
                                      ("F33/C16 split, confirm on C n=147", "fc", 33, 147),
                                      ("F25/C24 split, confirm on C n=98", "fc", 25, 98),
                                      ("F25/C24 split, confirm on C n=147", "fc", 25, 147)]:
        lo, hi = 1.0, 4.5
        for _ in range(11):                                  # calibrate zc at rho = 0 to the same round FWER
            mid = (lo + hi) / 2
            if run_mg(scheme, 0.0, mid, "null", 16000, 13, nF, nconf)["p_champion"] > base: lo = mid
            else: hi = mid
        zc = (lo + hi) / 2; out[label] = {"zc": zc, "nF": nF, "nconf": nconf, "rho": {}}
        for rho in (0.0, 0.05, 0.10):
            out[label]["rho"][str(rho)] = {"null": run_mg(scheme, rho, zc, "null", 16000, 13, nF, nconf),
                                            "mixed": run_mg(scheme, rho, zc, "mixed", 16000, 17, nF, nconf)}
            r = out[label]["rho"][str(rho)]
            print(label, "zc", round(zc, 2), "rho", rho, "FWER", round(r["null"]["p_champion"], 3), "good", round(r["mixed"]["p_good"], 3),
                  "bad", round(r["mixed"]["p_bad"], 3), "infl", round(r["mixed"]["inflation"], 3), "roll", round(r["mixed"]["rollouts"]), flush=True)
    (HERE / "gate_budget_merge.json").write_text(json.dumps(out, indent=1))


def merge2():
    base = json.load(open(HERE / "gate_budget_multi.json"))["_fwer_target"]; out = {}
    for label, nF, nconf, mctrl, mC in [("F25/C24 n=147, hist m=8 (no control)", 25, 147, 0, 8), ("F25/C24 n=147, control m=3", 25, 147, 3, 8),
                                        ("F25/C24 n=147, control m=4", 25, 147, 4, 8), ("F25/C24 n=196, control m=4", 25, 196, 4, 8)]:
        lo, hi = 1.0, 4.5
        for _ in range(11):
            mid = (lo + hi) / 2
            if run_mg("fc", 0.0, mid, "null", 16000, 13, nF, nconf, 0.03, mctrl)["p_champion"] > base: lo = mid
            else: hi = mid
        zc = (lo + hi) / 2; out[label] = {"zc": zc, "res": {}}
        for rho, eps in ((0.0, 0.0), (0.1, 0.0), (0.1, 0.03)):
            r = {"null": run_mg("fc", rho, zc, "null", 16000, 13, nF, nconf, eps, mctrl), "mixed": run_mg("fc", rho, zc, "mixed", 16000, 17, nF, nconf, eps, mctrl)}
            out[label]["res"][f"rho={rho},eps={eps}"] = r
            print(label, "zc", round(zc, 2), "rho", rho, "eps", eps, "FWER", round(r["null"]["p_champion"], 3), "good", round(r["mixed"]["p_good"], 3),
                  "bad", round(r["mixed"]["p_bad"], 3), "infl", round(r["mixed"]["inflation"], 3), "roll", round(r["mixed"]["rollouts"]), flush=True)
    (HERE / "gate_budget_merge2.json").write_text(json.dumps(out, indent=1))


def multi():
    res = {}
    base = run_multi(m_P, {}, "null")["p_champion"]; print("round FWER target (rule P as run x8, null):", base, flush=True)
    for name, (fn, kw) in MULTI.items():
        if fn in (m_sh, m_ts):
            kw = dict(zc=calibrate_multi(fn, base))
        res[name] = {"params": kw, "null": run_multi(fn, kw, "null"), "mixed": run_multi(fn, kw, "mixed", seed0=17)}
        print(name, kw, json.dumps(res[name]), flush=True)
    res["_fwer_target"] = base
    (HERE / "gate_budget_multi.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    if sys.argv[1] in ("single", "all"):
        single()
    if sys.argv[1] == "merge2":
        merge2()
    if sys.argv[1] == "merge":
        merge()
    if sys.argv[1] == "sweeps2":
        sweeps2()
    if sys.argv[1] == "sweeps":
        sweeps()
    if sys.argv[1] in ("multi", "all"):
        multi()
