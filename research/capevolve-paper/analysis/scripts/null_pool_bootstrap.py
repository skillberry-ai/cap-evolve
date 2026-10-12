"""E22 amendment 7F: bootstrap interval over the K pool evaluations (resample evaluations as positions with replacement; each
decision then draws DISTINCT positions of the resampled pool). Uses the committed null_pool_replay.py functions and gates unchanged.
v2 (2026-10-12): the point estimate (full pool) and every bootstrap replicate use the SAME estimator and the same number of inner draws,
parallel over replicates; adds the n_conf 10 row.
usage: null_pool_bootstrap.py <pool_dir> [--B 400] [--reps 10000] [--procs 24]"""
import argparse, random, sys, multiprocessing as mp
sys.path.insert(0, "/home/dev/projects2/cap-evolve-campaign/research/capevolve-paper/analysis/scripts")
sys.path.insert(0, "/home/dev/projects2/wt-tau/core")
import null_pool_replay as R
from cap_evolve import promotion as P
G = {"one-stage / stock-unmasked (screen k_se=1)": ("screen", 1.0, 0, 0.0, 0.0), "screen k_se=2": ("screen", 2.0, 0, 0.0, 0.0),
     "rule P as E10B (k1, n_conf3, z1.282, dmin0)": ("P", 1.0, 3, 1.282, 0.0), "rule P frozen (k1, n_conf3, z2.0, dmin0.02)": ("P", 1.0, 3, 2.0, 0.02),
     "rule P n_conf10 z1.645 dmin0.02": ("P", 1.0, 10, 1.645, 0.02)}
ev = None; tasks = None; REPS = 0
def rate(pool, g, rng):
    kind, k, nc, z, dm = g; acc = 0
    for _ in range(REPS):
        idx = rng.sample(range(len(pool)), 2 + 2 * nc); sd = R.delta(pool[idx[0]], pool[idx[1]], tasks)
        if kind == "screen": acc += P.screen(sd, k)["pass"]
        else:
            pr = P.PromotionParams(k_se=k, n_conf=nc, dmin=dm, z_conf=z, min_coverage=0.95)
            cs = [pool[i] for i in idx[2:2 + nc]]; is_ = [pool[i] for i in idx[2 + nc:]]
            acc += P.decide(sd, lambda: R.delta(R.mean_eval(cs, tasks), R.mean_eval(is_, tasks), tasks), pr, len(sd)).promote
    return acc / REPS
def job(args):
    gi, b, seed = args; rng = random.Random(seed); name = list(G)[gi]
    pool = ev if b < 0 else [ev[rng.randrange(len(ev))] for _ in range(len(ev))]
    return gi, b, rate(pool, G[name], rng)
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("pool"); ap.add_argument("--B", type=int, default=400); ap.add_argument("--reps", type=int, default=10000)
    ap.add_argument("--procs", type=int, default=24); ap.add_argument("--seed", type=int, default=11); a = ap.parse_args()
    ev = R.load(a.pool); tasks = sorted(set.intersection(*[set(e) for e in ev]), key=lambda x: int(x)); REPS = a.reps
    jobs = [(gi, b, a.seed * 100003 + gi * 10007 + (b + 1)) for gi in range(len(G)) for b in range(-1, a.B)]
    with mp.get_context("fork").Pool(a.procs) as p: res = p.map(job, jobs, chunksize=4)
    out = [f"K = {len(ev)} evaluations, {len(tasks)} tasks; point = full pool, {a.reps} draws; interval = percentile of {a.B} bootstrap replicates, each {a.reps} draws (same estimator). Inner Monte Carlo error of one rate at p = 0.03: {((0.03*0.97/a.reps)**.5):.4f}.", "",
           "| gate | per candidate (point) | bootstrap 95% over evaluations | per 10 candidates (point; interval) |", "|---|---|---|---|"]
    for gi, name in enumerate(G):
        pt = next(r for g, b, r in res if g == gi and b < 0)
        bs = sorted(r for g, b, r in res if g == gi and b >= 0); lo, hi = bs[int(.025 * a.B)], bs[int(.975 * a.B) - 1]
        out.append(f"| {name} | {pt:.4f} | [{lo:.4f}, {hi:.4f}] | {1-(1-pt)**10:.3f}; [{1-(1-lo)**10:.3f}, {1-(1-hi)**10:.3f}] |")
    print("\n".join(out))
