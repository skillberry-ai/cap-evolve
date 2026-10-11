# Gemma 76.5 vs 76.8, GPT 38.5 vs 38.6, and the pooled CI method

## Problem
Three different aggregates of the same data circulate: draft 76.5 +/- 1.5 and 38.5; post 76.8 +/- 1.3 and 38.6; issue per-run 75.4/77.1/77.9. The draft's pooled bootstrap CIs are anti-conservative.

## Evidence
- 76.5 = mean over runs of paired (infra-dropped from both sides) finals: 75.00, 76.73, 77.90 (SD 1.46). 76.8 = champion over all champion-scored tasks: 75.36, 77.06 (279), 77.86 (SD 1.28). Both reproduce.
- 38.5 = mean of per-run paired baselines (38.57, 38.57, 38.35, last run drops 1 infra task); 38.6 = the single reused measurement (108/280). The baseline was measured once and reused, so its "SD" carries no variance information.
- Draft CIs [29.1, 36.8] and [45.5, 52.8] reproduce exactly but resample 827/839 pooled observations that are the same tasks x 3 runs; task-clustered bootstrap gives [26.9, 39.2] and [42.7, 55.5].
- Infra-as-failure sensitivity: Gemma finals 73.9/75.4/76.8.

## Impact
Small numerically (0.3 and 0.1 points) but the paper must pick and define one convention; SD over n=3 is not a pipeline-variance estimate with a fixed baseline and temperature-0 agent on a shared endpoint.

## Correction
Define the estimand (all 280 with infra as failures, or paired infra-valid). Use task-clustered bootstrap. Quote 43.5 and 38.6 (single baselines).

## Acceptance
One convention in paper and docs; CSV rows SB-G-02/05, SB-P-01/03 cited.
