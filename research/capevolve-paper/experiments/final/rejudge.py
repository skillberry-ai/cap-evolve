#!/usr/bin/env python3
"""rejudge.py: exploratory extra (a) of the final evaluation: re-judge the NL assertions of saved tau2 simulations with another judge.

    <tau2 venv python> -I rejudge.py --suite B --root FINAL_EVAL_ROOT/B --judge-model openai/azoai/gpt-4.1-2025-04-14 \
        --gateway http://127.0.0.1:4112/v1 [--tag-exp FINAL-B-rejudge] [--limit N]

No new target or simulator rollouts: every primary rollout saved its tau2 simulation record (raw/attempts/*/a*/native_sims/cand/eval/results_*.json,
CAPEVOLVE_NATIVE_SIMS=1), so only tau2's evaluator is re-run on the stored trajectory with the judge replaced
(tau2.evaluator.evaluator_nl_assertions.DEFAULT_LLM_NL_ASSERTIONS).  Tasks without NL assertions keep their reward (the judge is not involved).
The environment-side checks run on the PRISTINE domain constructor (no candidate tools are applied in this process), as in the primary scorer.
Writes <root>/extra_rejudge/rejudge_trials.csv (same columns as results_trials.csv plus reward_primary, judge_model, nl_changed) and
results_long.csv.  It is exploratory and outside the Holm family (decisions.md 2026-10-11 21:30).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fe_common as C  # noqa: E402

WT_TAU = Path(os.environ.get("TAU_WT", "/home/dev/projects2/wt-tau"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", required=True, choices=["B", "C"])
    ap.add_argument("--root", required=True)
    ap.add_argument("--judge-model", default="openai/azoai/gpt-4.1-2025-04-14")
    ap.add_argument("--gateway", default="http://127.0.0.1:4112/v1")
    ap.add_argument("--tag-exp", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--all", action="store_true", help="re-evaluate every trial, not only tasks with NL assertions (mechanics test; rewards must reproduce)")
    ap.add_argument("--mode", default="B", help="B (B* artifacts) or END")
    a = ap.parse_args(argv)
    root = Path(a.root)
    tag_exp = a.tag_exp or ("FINAL-%s-rejudge" % a.suite)
    cfg_example = {"B": "tau2_retail", "C": "tau2_airline_c"}[a.suite]
    domain = {"B": "retail", "C": "airline"}[a.suite]
    sys.path.insert(0, str(WT_TAU / "core"))
    sys.path.insert(0, str(WT_TAU / "examples" / cfg_example / "adapters"))
    from pathlib import Path as P  # noqa: F401
    from tau2.data_model.simulation import Results
    from tau2.evaluator.evaluator import EvaluationType, evaluate_simulation
    import tau2.evaluator.evaluator_nl_assertions as nl

    nl.DEFAULT_LLM_NL_ASSERTIONS = a.judge_model
    recs = C.jsonl(root / "raw" / "rollouts.jsonl")
    done = [r for r in recs if r.get("terminal") and r.get("final_status") == "done" and a.mode in (r["mode"], "ALL")]
    if a.limit:
        done = done[:a.limit]
    out_rows = []
    for r in done:
        ad = Path(r["attempt_dir"])
        sims = sorted(ad.glob("native_sims/*/*/results_*.json"))
        row = {"arm": r["arm"], "seed": r["seed"], "task": r["task"], "trial": r["trial"], "family": r.get("family"), "reward_primary": r["reward"],
               "judge_model": a.judge_model, "nl_changed": 0, "reward": r["reward"], "rejudged": 0, "job_id": r["job_id"]}
        if sims:
            res = Results.load(sims[-1])
            task = next((t for t in res.tasks if str(t.id) == str(r["task"])), None)
            crit = getattr(task, "evaluation_criteria", None) if task else None
            has_nl = bool(crit and getattr(crit, "nl_assertions", None))
            if (has_nl or a.all) and res.simulations:
                nl.DEFAULT_LLM_NL_ASSERTIONS_ARGS = {"api_base": a.gateway, "api_key": "%s-s%d:%s:judge" % ("tag:" + tag_exp + "-" + r["arm"], r["seed"], r["arm"])}
                sim = res.simulations[0]
                ri = evaluate_simulation(sim, task, EvaluationType.ALL, False, domain)
                row["reward"] = float(ri.reward)
                row["rejudged"] = 1
                row["nl_changed"] = int(abs(float(ri.reward) - float(r["reward"])) > 1e-9)
        out_rows.append(row)
    d = root / "extra_rejudge"
    d.mkdir(parents=True, exist_ok=True)
    cols = ["arm", "seed", "task", "trial", "reward", "family", "reward_primary", "rejudged", "nl_changed", "judge_model", "job_id"]
    with open(d / "rejudge_trials.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)
    agg = {}
    for x in out_rows:
        agg.setdefault((x["arm"], x["seed"], x["task"]), []).append(x)
    with open(d / "results_long.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arm", "seed", "task", "reward", "family", "n_trials", "reward_primary"])
        for (arm, seed, task), xs in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][1], str(kv[0][2]))):
            w.writerow([arm, seed, task, sum(x["reward"] for x in xs) / len(xs), xs[0]["family"], len(xs), sum(x["reward_primary"] for x in xs) / len(xs)])
    print("rejudged %d of %d trials with NL assertions -> %s" % (sum(x["rejudged"] for x in out_rows), len(out_rows), d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
