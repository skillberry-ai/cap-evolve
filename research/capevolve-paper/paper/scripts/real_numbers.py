"""STUB.

CONTRACT (agreed with team-lead; the final-eval runner must write exactly this)
  path    /home/dev/projects2/campaign-scratch/final_eval/{A,B,C}/results_long.csv
  columns arm,seed,task,reward,family
    arm     registry key: hc ao gepa skillopt metaharness evoskill wikiskill trace2skill ace mipro harnesslens oneshot seed
    seed    search seed index (0,1,2); the seed arm uses 0
    task    final-set task id
    reward  mean over execution trials, in [0,1]
    family  cluster id (task family)
  One row per (arm, seed, task); a missing cell is an absent row, never a zero.
 Replaces mock_numbers.py after the final evaluation (cutoff 2026-10-13 06:00 UTC).

Contract: write the SAME files as mock_numbers.py, with source = "real":
  ../results_data.json     schema below; plots/make_plots.py and make_tables.py then drop the watermark and the \\pend wrappers
  ../numbers_pending.tex   an empty file (or only macros that are still genuinely pending); real macros go to ../numbers.tex via derive_numbers.py

Inputs it will read (paths are the ones in the design; confirm with paper-core / metrics-eng before the run)
  1. Final-evaluation long tables, one CSV per suite, columns  arm,seed,task,reward,family
         /home/dev/projects2/campaign-scratch/final_eval/{A,B,C}/results_long.csv
     one row per (arm, search seed, task) with reward = mean over execution trials; the seed arm has one row set (seed = 0);
     missing cells are absent rows, never zeros (analysis_plan.md section 6 bounds them).
  2. Paired statistics: analysis/scripts/paired_cluster_bootstrap.py
         python3 -I paired_cluster_bootstrap.py --long results_long.csv --arm-a <arm> --arm-b seed \\
                 --cluster-col family --level task+seed --out <arm>.json
     Headline interval = cr_ci (CR1, df = C-1) when clusters < 30 and seed_t_ci for the pipeline-level claim; the bootstrap is the check.
     Holm: within suite across the optimizer arms (analysis_plan.md section 5 comparison family).
  3. Cost and wall clock at B*: analysis/out/metrics/metrics_by_arm.csv and metrics_by_role.csv rebuilt by analysis/scripts/refresh_metrics.sh
     after the cutoff, restricted to rows with category == "main" and truncated at the matched checkpoint B* (last common rollout index
     in rollout_metrics.csv). Optimizer roles = {optimizer, proposer, reflection, reflector, curator}. Arms whose optimizer is not
     gateway-metered (Claude Code sessions) use state_optimizer_tokens from metrics_by_arm.csv.
  4. Anytime curves: runs/E10{,B,C}/<arm>/s<k>/candidates.jsonl (events: created / evaluated / accepted; fields rollout_index, score.mean,
     score.split). Curve = best selection-split score so far against rollout_index, mean and min/max over seeds.
  5. Per-family deltas for Suite A: same long table, grouped by the family column.

results_data.json schema (see mock_numbers.build()):
  {"source": "real", "suites": {S: {"params": {tasks, trials, seeds, bstar, clusters},
      "arms": {arm: {score, delta, lo, hi, p_holm, rollouts, tok_unc, tok_cr, tok_cw, usd, wall_h, missing, cells,
                     curve: {rollouts, mean, lo, hi} | null}},
      "families": {fam: {n_tasks, arms: {arm: {delta, lo, hi}}}}   # Suite A only
  }}}
All scores and deltas are fractions in [0, 1]; USD is the Sonnet list-price proxy and is a lower bound when any role is unpriced.

After running this:  python3 -I make_tables.py;  python3 -I plots/make_plots.py;  then rebuild with \\draftmodefalse.
"""
import sys

REQUIRED = [
    "final_eval/A/results_long.csv",
    "final_eval/B/results_long.csv",
    "final_eval/C/results_long.csv",
]


def main():
    from pathlib import Path
    root = Path("/home/dev/projects2/campaign-scratch")
    missing = [p for p in REQUIRED if not (root / p).exists()]
    if missing:
        print("real_numbers.py: final-evaluation inputs not present yet:", *missing, sep="\n  ")
        sys.exit(2)
    raise NotImplementedError("implement after the final-eval output format is frozen; see the module docstring")


if __name__ == "__main__":
    main()
