"""P2 budget-fit search: pool sizes/budgets per suite, heterogeneous nulls, cluster-robust t confirmation on C.
Reuses gate_budget_sim (Stream, edit, POOL). usage: python3 -I p2_budget_sim.py grid|final"""
import importlib.util, itertools, json, math, multiprocessing as mp, random, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("g", HERE / "gate_budget_sim.py"); g = importlib.util.module_from_spec(spec); sys.modules["g"] = g; spec.loader.exec_module(g)
NCPU = g.NCPU


def t_pdf(x, df):
    return math.exp(math.lgamma((df + 1) / 2) - math.lgamma(df / 2)) / math.sqrt(df * math.pi) * (1 + x * x / df) ** (-(df + 1) / 2)


_tc = {}
def t_crit(df, alpha):
    """one-sided upper critical value of Student t (numeric integration + bisection)."""
    key = (df, round(alpha, 5))
    if key in _tc: return _tc[key]
    def tail(x):  # P(T>x) by Simpson on [x, x+60]
        n = 600; h = 30.0 / n; s = t_pdf(x, df) + t_pdf(x + 30, df)
        for i in range(1, n): s += (4 if i % 2 else 2) * t_pdf(x + i * h, df)
        return s * h / 3
    lo, hi = 0.0, 20.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if tail(mid) > alpha: lo = mid
        else: hi = mid
    _tc[key] = (lo + hi) / 2; return _tc[key]


def clip(x): return min(1.0, max(0.0, x))


def one_round(rng, cfg, ds, het, tcrit):
    Fn, Cn, K = cfg["F"], cfg["C"], cfg["K"]
    pF = [g.POOL[rng.randrange(49)] for _ in range(Fn)]; pC = [g.POOL[rng.randrange(49)] for _ in range(Cn)]
    qF, qC = [], []
    for d in ds:
        eF = g.edit(pF, d); eC = g.edit(pC, d)
        qF.append([clip(x + rng.gauss(0, het)) for x in eF]); qC.append([clip(x + rng.gauss(0, het)) for x in eC])
    phF = g.phat_of(rng, pF, cfg["minc"]); S = [g.Stream(rng, q, phF, cfg["minc"]) for q in qF]
    r1, r2 = cfg["r"]
    for s in S: s.draw(r1)
    cost = K * r1
    keep = [j for j in sorted(range(K), key=lambda j: -S[j].z())[:max(1, K // 2)] if S[j].mean() > 0]
    for j in keep: S[j].draw(r2 - r1); cost += r2 - r1
    keep = [j for j in sorted(keep, key=lambda j: -S[j].z())[:cfg["S"]] if S[j].mean() > 0]
    if not keep: return None, cost
    phC = g.phat_of(rng, pC, cfg["mc"]); cost += cfg["mc"] * Cn
    best = None
    for j in keep:
        tc = cfg["tc"]; cost += tc * Cn
        d = [sum(rng.random() < qC[j][t] for _ in range(tc)) / tc - phC[t] for t in range(Cn)]
        m = sum(d) / Cn; v = sum((x - m) ** 2 for x in d) / (Cn - 1); se = math.sqrt(v / Cn) if v > 0 else 1e-9
        if m >= 0.02 and m / se >= tcrit and (best is None or m > best[1]): best = (j, m)
    return best, cost


def job(a):
    cfg, mode, het, reps, seed, alpha = a
    rng = random.Random(seed); tcrit = t_crit(cfg["C"] - 1, alpha); K = cfg["K"]
    eff = float(mode.split(':')[1]) if ':' in mode else 0.10; mode = mode.split(':')[0]
    acc = good = cost = 0
    for _ in range(reps):
        if mode == "null": ds = [0.0] * K
        else:
            ds = [0.0] * K; ds[rng.randrange(K)] = eff
        c, cs = one_round(rng, cfg, ds, het, tcrit); cost += cs
        if c is not None:
            acc += 1
            if mode == "alt" and ds[c[0]] > 0: good += 1
    return acc, good, cost, reps


def run(cfg, mode, het, reps=6000, alpha=0.05, seed0=1):
    t_crit(cfg['C'] - 1, alpha); per = max(1, reps // NCPU)
    with mp.get_context("fork").Pool(NCPU) as p:
        out = p.map(job, [(cfg, mode, het, per, seed0 * 9973 + i, alpha) for i in range(NCPU)])
    R = sum(o[3] for o in out)
    return sum(o[0] for o in out) / R, sum(o[1] for o in out) / R, sum(o[2] for o in out) / R


def worst(cfg):
    K = cfg["K"]; r1, r2 = cfg["r"]
    return K * r1 + math.ceil(K / 2) * (r2 - r1) + cfg["mc"] * cfg["C"] + cfg["S"] * cfg["tc"] * cfg["C"]


SUITES = {"A": dict(B=600, F=62, C=58), "D": dict(B=550, F=38, C=36), "E": dict(B=300, F=16, C=14)}


def feasible(su):
    B, F, C = su["B"], su["F"], su["C"]; out = []
    for minc, K, r, S, tc, mc in itertools.product((1, 2, 3, 4), (4, 6, 8), ((8, 16), (8, 24), (12, 36)), (1, 2), (1, 2, 3, 4, 6), (1, 2, 3, 4)):
        cfg = dict(F=F, C=C, minc=minc, K=K, r=r, S=S, tc=tc, mc=mc)
        w = worst(cfg); R = (B - minc * F) // w
        if R >= 2: out.append((cfg, w, R))
    return out


def grid():
    res = {}
    for name, su in SUITES.items():
        fe = feasible(su); fe = fe[::max(1, len(fe) // 250)]; print(name, "feasible configs", len(fe), flush=True); rows = []
        for cfg, w, R in fe:
            fw = run(cfg, "null", 0.2, 3000)[0]
            if fw > 0.12: continue
            pw = [run(cfg, "alt", h, 3000)[1] for h in (0.0, 0.1, 0.2)]
            rows.append(dict(cfg=cfg, worst=w, rounds=R, fwer_s02=fw, power=pw, mean_power=sum(pw) / 3))
        rows.sort(key=lambda r: -r["mean_power"]); res[name] = rows[:15]
        for r in rows[:5]: print(name, r, flush=True)
    json.dump(res, open(HERE / "p2_grid.json", "w"), indent=1)


def final():
    G = json.load(open(HERE / "p2_grid.json")); out = {}
    for name in SUITES:
        out[name] = []
        for row in G[name][:4]:
            cfg = row["cfg"]; cfg["r"] = tuple(cfg["r"]); lo, hi = 0.002, 0.5
            for _ in range(9):                      # alpha (one-sided t) so that FWER at het 0.2 is ~0.10
                mid = (lo + hi) / 2
                if max(run(cfg, "null", h, 8000, mid, 5)[0] for h in (0.0, 0.2)) > 0.10: hi = mid
                else: lo = mid
            al = lo
            fw = [run(cfg, "null", h, 12000, al, 7)[0] for h in (0.0, 0.1, 0.2)]
            pw = [run(cfg, "alt", h, 12000, al, 9)[1] for h in (0.0, 0.1, 0.2)]
            cost = run(cfg, "alt", 0.1, 6000, al, 11)[2]
            rec = dict(cfg=cfg, alpha=al, tcrit=t_crit(cfg["C"] - 1, al), worst=row["worst"], rounds=row["rounds"], fwer=fw, power=pw, cost_round=cost)
            out[name].append(rec); print(name, json.dumps(rec), flush=True)
    json.dump(out, open(HERE / "p2_final2.json", "w"), indent=1)


if __name__ == "__main__":
    if sys.argv[1] == "grid": grid()
    if sys.argv[1] == "final": final()
