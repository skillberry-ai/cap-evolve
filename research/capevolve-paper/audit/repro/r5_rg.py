"""R5: accept rate of the agent-optimize promote gate (objectives.decide_reward_gated, defaults) vs true effect."""
import sys, random
sys.path.insert(0, "/home/dev/projects2/cap-evolve-campaign/core")
from cap_evolve import objectives as O
rng = random.Random(3)
def arm(p, nt):
    return [O.TrialRec(task=f"t{i}", k=k, reward=float(rng.random() < pi), cost_usd=1.0 + rng.random()*0.2)
            for i, pi in enumerate(p) for k in range(nt)]
def rate(T, nt_par, nt_c, shift, N=1500):
    acc = 0
    for _ in range(N):
        p = [rng.betavariate(.7, .7) for _ in range(T)]
        q = [min(1, max(0, pi + shift)) for pi in p]
        v = O.decide_reward_gated(arm(p, nt_par), arm(q, nt_c))
        acc += v.outcome == "accept"
    return acc / N
print("z_accept =", round(O.z_accept(O.GateCfg()), 3), " noise_floor =", O.NOISE_FLOOR)
for T in (30, 60, 140):
    for nt in (3, 8):
        print(f"T={T:3d} trials/arm={nt}: P(accept | true d=0)={rate(T, nt, nt, 0.0):.3f}  d=+0.05: {rate(T, nt, nt, 0.05, 600):.3f}  d=+0.10: {rate(T, nt, nt, 0.10, 600):.3f}")
