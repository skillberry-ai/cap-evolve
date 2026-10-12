"""E22 empirical null pool: false-accept rates of gates under the real trial noise of the Suite D target.

Input: single.py outputs of 40 evaluations of the UNMODIFIED seed on retail opt-49 (runs/E22-null/chunk*.out).
A null candidate is another evaluation of the same seed. Screen = one evaluation per side (num_trials 1);
confirmation = n_conf FRESH evaluations per side (never reused from the screen). The REAL cap_evolve
promotion.screen/decide code is called. Stock gate with footprint masking is not exercised (a null edit has
an empty footprint); the unmasked paired k_se screen is its null-equivalent and equals the one-stage gate.

usage: python3 null_pool_replay.py <pool_dir> [--reps 20000] [--out null_pool_replay.md]
"""
import argparse, glob, json, math, random, statistics, sys
sys.path.insert(0, "/home/dev/projects2/wt-tau/core")
from cap_evolve import promotion as P  # noqa: E402


def load(pool_dir):
    evals = []  # each: {task: reward}
    for f in sorted(glob.glob(f"{pool_dir}/chunk*.out")):
        t = open(f).read()
        if "{" not in t:
            continue
        rows = json.loads(t[t.index("{"):])["rows"]
        by = {}
        for r in rows:
            by.setdefault(r["trial"], {})[r["task"]] = (None if r["err"] else float(r["reward"]))
        evals += [by[k] for k in sorted(by)]
    return evals


def delta(a, b, tasks):
    return [a[t] - b[t] for t in tasks if a.get(t) is not None and b.get(t) is not None]


def mean_eval(es, tasks):
    out = {}
    for t in tasks:
        v = [e[t] for e in es if e.get(t) is not None]
        out[t] = sum(v) / len(v) if v else None
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return (0, 0)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("pool"); ap.add_argument("--reps", type=int, default=20000)
    ap.add_argument("--out", default=None); ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    ev = load(a.pool); K = len(ev)
    tasks = sorted(set.intersection(*[set(e) for e in ev]), key=lambda x: int(x))
    rng = random.Random(a.seed)
    means = [statistics.mean(v for v in e.values() if v is not None) for e in ev]
    gates = {
        "one-stage / stock-unmasked (screen k_se=1)": ("screen", dict(k=1.0)),
        "screen k_se=2": ("screen", dict(k=2.0)),
        "rule P as E10B (k1, n_conf3, z1.282, dmin0)": ("P", dict(k=1.0, nc=3, z=1.282, dmin=0.0)),
        "rule P frozen (k1, n_conf3, z2.0, dmin0.02)": ("P", dict(k=1.0, nc=3, z=2.0, dmin=0.02)),
        "rule P n_conf10 z1.645 dmin0.02": ("P", dict(k=1.0, nc=10, z=1.645, dmin=0.02)),
    }
    res = {}
    for name, (kind, g) in gates.items():
        nc = g.get("nc", 0); need = 2 + 2 * nc
        if need > K:
            res[name] = None; continue
        acc = scr = 0
        for _ in range(a.reps):
            idx = rng.sample(range(K), need)
            cand, inc = ev[idx[0]], ev[idx[1]]
            sd = delta(cand, inc, tasks)
            if kind == "screen":
                ok = P.screen(sd, g["k"])["pass"]; scr += ok; acc += ok
            else:
                pr = P.PromotionParams(k_se=g["k"], n_conf=nc, dmin=g["dmin"], z_conf=g["z"], min_coverage=0.95)
                cs = [ev[i] for i in idx[2:2 + nc]]; is_ = [ev[i] for i in idx[2 + nc:]]
                r = P.decide(sd, lambda: delta(mean_eval(cs, tasks), mean_eval(is_, tasks), tasks), pr, len(sd))
                scr += r.stage != "screen_reject"; acc += r.promote
        res[name] = (acc, scr)
    # split-half robustness: pools of evals 0..K/2 and K/2..K separately for the E10B rule
    lines = [f"# E22 null pool replay\n", f"Pool: {K} evaluations of the unmodified seed, {len(tasks)} tasks, 1 trial per task per evaluation. Reps per gate {a.reps} (draws share a finite pool, so the Wilson CI is optimistic; see split-half).\n",
             f"Seed mean reward per evaluation: mean {statistics.mean(means):.3f}, SD {statistics.pstdev(means):.3f} (binomial expectation about {math.sqrt(statistics.mean(means)*(1-statistics.mean(means))/len(tasks)):.3f}); first-half mean {statistics.mean(means[:K//2]):.3f}, second-half {statistics.mean(means[K//2:]):.3f}.\n",
             "| gate | screen pass | false accept per candidate | Wilson 95% | P(>=1 false accept in 10 candidates) |", "|---|---|---|---|---|"]
    for name, r in res.items():
        if r is None:
            lines.append(f"| {name} | n/a pool too small | | | |"); continue
        acc, scr = r; lo, hi = wilson(acc, a.reps); p = acc / a.reps
        lines.append(f"| {name} | {scr/a.reps:.3f} | {p:.4f} | [{lo:.4f}, {hi:.4f}] | {1-(1-p)**10:.3f} |")
    sh = []
    for nm, sl in (("first half", slice(0, K // 2)), ("second half", slice(K // 2, K))):
        sub = ev[sl]; k = len(sub); acc = 0; reps = 5000
        for _ in range(reps):
            i = rng.sample(range(k), 8)
            sd = delta(sub[i[0]], sub[i[1]], tasks)
            pr = P.PromotionParams(k_se=1.0, n_conf=3, dmin=0.0, z_conf=1.282, min_coverage=0.95)
            cs = [sub[j] for j in i[2:5]]; is_ = [sub[j] for j in i[5:8]]
            acc += P.decide(sd, lambda: delta(mean_eval(cs, tasks), mean_eval(is_, tasks), tasks), pr, len(sd)).promote
        sh.append(f"{nm}: {acc/reps:.4f}")
    lines += ["", "Split-half check, rule P as E10B (8 evaluations per draw): " + "; ".join(sh) + ".",
              "", "Compare with analysis/out/sim_promotion.md (simulated: one-stage 0.57 and rule P 0.04 per 10-iteration search).",
              "Scope: unmasked decision rules on null edits only. False reject needs true effects (E26)."]
    txt = "\n".join(lines); print(txt)
    if a.out:
        open(a.out, "w").write(txt + "\n")


if __name__ == "__main__":
    main()
