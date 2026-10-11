"""R3: empirical false-accept rate of the default paired gate (k_se=1) on NULL (byte-equivalent) candidates."""
import sys, random, math
sys.path.insert(0, "/home/dev/projects2/cap-evolve-campaign/core")
from cap_evolve import gate
rng = random.Random(1)
def measure(p, nt):  # per-task mean over nt Bernoulli trials
    return [sum(rng.random() < pi for _ in range(nt)) / nt for pi in p]
def one(T, nt, iters, k=1.0):
    p = [rng.betavariate(.7, .7) for _ in range(T)]          # heterogeneous task difficulty
    cur = measure(p, nt); first = None; acc = 0
    for it in range(iters):
        cand = measure(p, nt)                               # null: same true rates
        d = [c - a for c, a in zip(cand, cur)]
        dec = gate.decide(sum(cur)/T, sum(cand)/T, mode="paired", paired_deltas=d, k_se=k)
        if dec.accept:
            acc += 1; cur = cand
            first = first if first is not None else it
    return acc
print("T  trials | P(accept) single null test | P(>=1 false accept in 10 iters) | mean #accepts/10")
N = 4000
for T in (30, 60, 140):
    for nt in (1, 3, 5):
        single = sum(one(T, nt, 1) > 0 for _ in range(N)) / N
        runs = [one(T, nt, 10) for _ in range(N // 4)]
        print(f"{T:3d} {nt:3d}    | {single:.3f}                       | {sum(r>0 for r in runs)/len(runs):.3f}                           | {sum(runs)/len(runs):.2f}")
print("normal-theory one-sided P(Z>1) = 0.159")
