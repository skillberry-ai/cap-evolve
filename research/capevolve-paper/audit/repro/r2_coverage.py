"""R2: errored/invalid candidate trials are DROPPED from the pair (not counted as failures); coverage is candidate-marginal only."""
import sys
sys.path.insert(0, "/home/dev/projects2/cap-evolve-campaign/core")
from cap_evolve import gate
from cap_evolve.harness import _paired_deltas
from cap_evolve.loop import aggregate_scores
from cap_evolve.types import Score

T = 30
tid = [f"t{i:02d}" for i in range(T)]
def score(t, r, valid=True):
    return Score(task_id=t, reward=r, feedback="", n=1, stderr=0.0, trial_rewards=[r] if valid else [],
                 raw={"valid_trials": 1 if valid else 0, "n_trials": 1, "errored_trials": 0 if valid else 1})
par = {t: (0.0 if i < 8 else 1.0) for i, t in enumerate(tid)}      # parent passes 22/30
# candidate: fixes 4 failing tasks, but CRASHES (error rollout => dropped) on 6 tasks the parent passed
cand_scores = []
for i, t in enumerate(tid):
    if 1 <= i < 5: cand_scores.append(score(t, 1.0))
    elif 20 <= i < 26: cand_scores.append(score(t, 0.0, valid=False))   # candidate-induced crash
    else: cand_scores.append(score(t, par[t]))
P = aggregate_scores("val", [score(t, par[t]) for t in tid]); C = aggregate_scores("val", cand_scores)
d = _paired_deltas(P, C)
print(f"parent val={P.reward:.3f}  candidate val={C.reward:.3f}  cand coverage={C.coverage:.2f} (min_coverage default 0.6)")
dec = gate.decide(P.reward, C.reward, mode="paired", paired_deltas=d, coverage=C.coverage)
print("paired n =", len(d), " accept =", dec.accept, "::", dec.reason)
# joint coverage: parent-valid AND cand-valid
print("joint paired coverage =", len(d)/T)
# disjoint-missingness: both marginals above 0.6 but joint far lower
import itertools
P2 = aggregate_scores("val", [score(t, par[t], valid=(i % 2 == 0 or i < 4)) for i, t in enumerate(tid)])
C2 = aggregate_scores("val", [score(t, par[t], valid=(i % 2 == 1 or i < 4)) for i, t in enumerate(tid)])
d2 = _paired_deltas(P2, C2)
print(f"disjoint missingness: parent cov={P2.coverage:.2f} cand cov={C2.coverage:.2f} joint paired n={len(d2 or [])}/{T}")
P3 = aggregate_scores("val", [score(t, par[t], valid=(i >= 9)) for i, t in enumerate(tid)])
C3 = aggregate_scores("val", [score(t, par[t], valid=(i < 21)) for i, t in enumerate(tid)])
d3 = _paired_deltas(P3, C3)
dd = gate.decide(P3.reward, C3.reward, mode="paired", paired_deltas=d3, coverage=C3.coverage)
print(f"marginals parent={P3.coverage:.2f} cand={C3.coverage:.2f} (both >= 0.6) but joint paired n={len(d3)}/{T}={len(d3)/T:.2f}; indecisive={dd.indecisive}")
