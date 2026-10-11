"""R7: stats.combined_stderr adds within-task trial variance on top of a between-task variance that already contains it."""
import sys, random, math
sys.path.insert(0, "/home/dev/projects2/cap-evolve-campaign/core")
from cap_evolve import stats
rng = random.Random(5); T = 40
for nt in (1, 3, 5, 10):
    emp, comb = [], []
    p = [rng.betavariate(.7, .7) for _ in range(T)]      # FIXED val set of tasks
    means_all = []
    for rep in range(3000):
        xs = [[rng.random() < pi for _ in range(nt)] for pi in p]
        m = [sum(x)/nt for x in xs]
        se = [stats.stderr([float(v) for v in x]) for x in xs]
        means_all.append(sum(m)/T); comb.append(stats.combined_stderr(m, se))
    mu = sum(means_all)/len(means_all)
    emp_sd = math.sqrt(sum((a-mu)**2 for a in means_all)/(len(means_all)-1))     # true sd of the val mean over re-measurement of THIS val set
    print(f"trials={nt:2d}: sd of val mean under re-measurement (fixed tasks) = {emp_sd:.4f}; mean combined_stderr = {sum(comb)/len(comb):.4f}; ratio = {sum(comb)/len(comb)/emp_sd:.2f}")
