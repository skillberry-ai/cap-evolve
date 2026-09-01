# Zero-shot skill transfer — train/test task list

**Status: not run.** This is a reference list of the 8 planned transfer-eval
fold-runs from [train_test_split_proposal.md](train_test_split_proposal.md),
for whoever runs them later. Nothing has been submitted.

## What this is

For each row: take the **winning skill** from the *train* task's completed
run and drop it unmodified into the *test* task's project (as
`seed_capability/`), then run cap-evolve with `--max-iterations 0` (baseline-only
mode — no optimizer loop) to score that skill zero-shot on the test task's own
val/test split. Compares against the test task's own native seed baseline
(from `results.json`).

Groups 1 and 2 from the proposal (highest priority). For group 1
(macroeconomic-analysis, 3-way LOO), all three tasks' winning skills are
identically named `xlsx`, so each combined-train fold was split into two
separate directed single-source transfers rather than merging skills under
one name.

## Priority 1 — finance-economics / macroeconomic-analysis

| # | train (skill source) | test (target) | project dir already built | worktree |
|---|---|---|---|---|
| 1 | shock-analysis-demand | shock-analysis-supply | `.capevolve/project_shock-analysis-supply_from_shock-analysis-demand` | c2 |
| 2 | shock-analysis-demand | weighted-gdp-calc | `.capevolve/project_weighted-gdp-calc_from_shock-analysis-demand` | c2 |
| 3 | shock-analysis-supply | shock-analysis-demand | `.capevolve/project_shock-analysis-demand_from_shock-analysis-supply` | c2 |
| 4 | shock-analysis-supply | weighted-gdp-calc | `.capevolve/project_weighted-gdp-calc_from_shock-analysis-supply` | c2 |
| 5 | weighted-gdp-calc | shock-analysis-demand | `.capevolve/project_shock-analysis-demand_from_weighted-gdp-calc` | c2 |
| 6 | weighted-gdp-calc | shock-analysis-supply | `.capevolve/project_shock-analysis-supply_from_weighted-gdp-calc` | c2 |

Own-skill baselines for comparison (from `results.json`):
shock-analysis-demand seed=0.0 / final_test=0.9;
shock-analysis-supply seed=0.0 / final_test=0.2;
weighted-gdp-calc seed=0.8 / best=1.0 (KILLED_ceiling, no final_test recorded).

## Priority 2 — mathematics-or-formal-reasoning / mathematical-optimization

| # | train (skill source) | test (target) | project dir already built | worktree |
|---|---|---|---|---|
| 7 | exam-block-sequencing | paratransit-routing | `.capevolve/project_paratransit-routing_from_exam-block-sequencing` | c3 |
| 8 | paratransit-routing | exam-block-sequencing | `.capevolve/project_exam-block-sequencing_from_paratransit-routing` | c3 |

Own-skill baselines: exam-block-sequencing seed=0.1 / best=1.0 (KILLED_ceiling);
paratransit-routing seed=0.0 / best=1.0 (KILLED_ceiling). Both hit the reward
ceiling on their own skill — for the transfer, "success" is not hitting 1.0
again, it's whether the *other* task's skill lifts these off their low seed at
all.

## How to run one later

From inside the relevant worktree (`c2` for #1-6, `c3` for #7-8), with
`scripts/ccc/run_ccc_experiment.sh` available (either from PR #412 once
merged, or a local untracked copy — see `HANDOFF_CCC.md`/`CCC_PODMAN_SETUP.md`
under [docs/how-to/ccc/](../../../docs/how-to/ccc/)):

```bash
bsub -q normal -M 64G -n 4 -W 2:00 -m <dedicated_host> \
    -J capevolve_transfer_<train>_to_<test> \
    -oo <logdir>/%J.stdout -eo <logdir>/%J.stderr \
    bash scripts/ccc/run_ccc_experiment.sh \
        --suite-id transfer_eval_v1 \
        --run-ts transfer_<train>_to_<test>_v1 \
        --max-iterations 0 \
        --spec ".capevolve/project_<test>_from_<train>/capevolve.<test>.yaml" \
        --project ".capevolve/project_<test>_from_<train>"
```

Notes:
- `-m <dedicated_host>` is required — podman graphroot is per-user, not
  per-pid, so packing two of these on the same host corrupts state. Pick 8
  distinct hosts (check free capacity with `bhosts -w`).
- `-q normal` — the only submittable non-idle queue on this cluster
  (`x86_1h` does not exist here).
- Record results under `results.json` with a distinct `source:` tag
  (e.g. `source: transfer-eval-v1`), per the convention in `C4_HANDOFF.md`.
- Kill by exact job ID only if something needs stopping — never a wildcard
  bkill, since sibling sessions share the UID.
