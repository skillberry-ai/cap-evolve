"""Paired bootstrap between two groups of runs: per-task mean test reward of group A minus group B.
Infra-error rows (opt_infra) are dropped; only tasks scored in every run of both groups are kept.
usage: groups.py A1,A2,... B1,B2,..."""
import glob
import json
import random
import sys


def pt(i):
    f = glob.glob(f"/tmp/exp606/runs/{i}/*/metrics.jsonl")[0]
    return {r["task"]: float(r["reward_opt"]) for r in map(json.loads, open(f))
            if r.get("reward_opt") is not None and not r.get("opt_infra")}


A = [pt(i) for i in sys.argv[1].split(",")]
B = [pt(i) for i in sys.argv[2].split(",")]
tasks = sorted(set.intersection(*[set(g) for g in A + B]))
ma = {t: sum(g[t] for g in A) / len(A) for t in tasks}
mb = {t: sum(g[t] for g in B) / len(B) for t in tasks}
d = [ma[t] - mb[t] for t in tasks]
rng = random.Random(0)
means = sorted(sum(d[rng.randrange(len(d))] for _ in d) / len(d) for _ in range(2000))
print(f"tasks={len(d)}  A={100 * sum(ma.values()) / len(d):.1f}  B={100 * sum(mb.values()) / len(d):.1f}  "
      f"A-B={100 * sum(d) / len(d):+.1f} points  95% CI [{100 * means[50]:+.1f}, {100 * means[1949]:+.1f}]")
