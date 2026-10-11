"""R4: false-accept rate of the posterior rule (posterior.Pair.verdict) on NULL candidates under repeated looks."""
import sys, random
sys.path.insert(0, "/home/dev/projects2/cap-evolve-campaign/core")
from cap_evolve import posterior
rng = random.Random(7)
def sim(T, n_parent, looks, het=0.0):
    p = [min(.98, max(.02, rng.betavariate(.7, .7))) for _ in range(T)]
    # true candidate rate: null (het=0) or zero-mean heterogeneous trade (some tasks up, some down)
    q = [min(.98, max(.02, pi + rng.uniform(-het, het))) for pi in p]
    sp = [sum(rng.random() < pi for _ in range(n_parent)) for pi in p]
    npar = [n_parent] * T
    k = posterior.k_vector([(s + .5) / (n + 1) for s, n in zip(sp, npar)])
    sc, nc = [0.0] * T, [0.0] * T
    for look in range(1, looks + 1):
        for i in range(T):
            sc[i] += rng.random() < q[i]; nc[i] += 1
        P = posterior.Pair(k, sp, npar, sc, nc)
        v = P.verdict(random.Random(0), int(sum(nc)))
        if v["decision"] == "accept":
            return look, sum(qi - pi for qi, pi in zip(q, p)) / T
        if v["decision"] == "prune":
            return None, None
    return None, None
for T, npar, het in ((30, 3, 0.0), (30, 3, 0.3), (30, 1, 0.0), (60, 3, 0.0)):
    N = 250; acc = []; true_d = []
    for _ in range(N):
        l, d = sim(T, npar, 8, het)
        if l: acc.append(l); true_d.append(d)
    print(f"T={T} parent_trials={npar} true-effect spread +-{het}: P(false accept within 8 looks)={len(acc)/N:.3f}"
          + (f"  mean true delta of accepts={sum(true_d)/len(true_d):+.4f}" if acc else ""))
