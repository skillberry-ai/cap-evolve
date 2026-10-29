#!/usr/bin/env python3
"""Family 1 AppWorld part: SECONDARY descriptive means by arm from the AWX records (written after the primary was read; erratum 164). No tests.
Per arm: mean of per-task means over the 30 tasks of pass fraction (pass_count / num_tests), prompt tokens, completion tokens, api_errors, share of episodes with collateral_damage, share ending max_steps, episode_seconds, trimmed_steps.
    python3 fam1_aw_secondary.py OUT.md STATE_DIR"""
import glob, json, os, sys
import numpy as np
OUT, STATE = sys.argv[1:3]
R = [json.load(open(f)) for f in glob.glob(os.path.join(STATE, "records", "*.json"))]
arms = ["both", "code", "prose", "base", "seed"]; L = ["# AWX secondary (descriptive): mean over the 30 tasks of the task means", "", "arm | pass fraction | prompt tokens | completion tokens | api_errors | collateral damage share | max_steps share | episode seconds | trimmed steps"]
for a in arms:
    ts = sorted({r["task_id"] for r in R if r["arm"] == a}); rows = lambda t: [r for r in R if r["arm"] == a and r["task_id"] == t]
    m = lambda f: np.mean([np.mean([f(r) for r in rows(t)]) for t in ts])
    L.append(f"{a} | {m(lambda r: r['pass_count']/r['num_tests']):.3f} | {m(lambda r: r['prompt_tokens']):.0f} | {m(lambda r: r['completion_tokens']):.0f} | {m(lambda r: r['api_errors']):.2f} | {m(lambda r: float(bool(r['collateral_damage']))):.3f} | {m(lambda r: float(r['termination']=='max_steps')):.3f} | {m(lambda r: r['episode_seconds']):.0f} | {m(lambda r: r['trimmed_steps']):.2f}")
open(OUT, "w").write("\n".join(L)); print("\n".join(L))
