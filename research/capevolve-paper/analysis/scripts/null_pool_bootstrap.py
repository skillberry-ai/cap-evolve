"""E22 amendment 7F: bootstrap interval over the K pool evaluations (resample evaluations as positions with replacement; each
decision then draws DISTINCT positions of the resampled pool). Uses the committed null_pool_replay.py functions and gates unchanged.
usage: null_pool_bootstrap.py <pool_dir> [--B 200] [--reps 3000]"""
import argparse, random, sys
sys.path.insert(0, "/home/dev/projects2/cap-evolve-campaign/research/capevolve-paper/analysis/scripts")
sys.path.insert(0, "/home/dev/projects2/wt-tau/core")
import null_pool_replay as R
from cap_evolve import promotion as P
ap = argparse.ArgumentParser(); ap.add_argument("pool"); ap.add_argument("--B", type=int, default=200); ap.add_argument("--reps", type=int, default=3000); ap.add_argument("--seed", type=int, default=11)
a = ap.parse_args(); ev = R.load(a.pool); K = len(ev)
tasks = sorted(set.intersection(*[set(e) for e in ev]), key=lambda x: int(x)); rng = random.Random(a.seed)
G = {"one-stage / stock-unmasked": ("screen", 1.0, 0, 0.0, 0.0), "screen k_se=2": ("screen", 2.0, 0, 0.0, 0.0),
     "rule P as E10B (k1,n3,z1.282,dmin0)": ("P", 1.0, 3, 1.282, 0.0), "rule P frozen (z2.0,dmin.02)": ("P", 1.0, 3, 2.0, 0.02)}
def rate(pool, g):
    kind, k, nc, z, dm = g; acc = 0
    for _ in range(a.reps):
        idx = rng.sample(range(len(pool)), 2 + 2 * nc); sd = R.delta(pool[idx[0]], pool[idx[1]], tasks)
        if kind == "screen": acc += P.screen(sd, k)["pass"]
        else:
            pr = P.PromotionParams(k_se=k, n_conf=nc, dmin=dm, z_conf=z, min_coverage=0.95)
            cs = [pool[i] for i in idx[2:2 + nc]]; is_ = [pool[i] for i in idx[2 + nc:]]
            acc += P.decide(sd, lambda: R.delta(R.mean_eval(cs, tasks), R.mean_eval(is_, tasks), tasks), pr, len(sd)).promote
    return acc / a.reps
out = ["| gate | point (pool) | bootstrap 95% over evaluations | per 10 candidates (point; interval) |", "|---|---|---|---|"]
for name, g in G.items():
    pt = rate(ev, g); bs = sorted(rate([ev[rng.randrange(K)] for _ in range(K)], g) for _ in range(a.B))
    lo, hi = bs[int(.025 * a.B)], bs[int(.975 * a.B) - 1]
    out.append(f"| {name} | {pt:.4f} | [{lo:.4f}, {hi:.4f}] | {1-(1-pt)**10:.3f}; [{1-(1-lo)**10:.3f}, {1-(1-hi)**10:.3f}] |")
print("\n".join(out))
