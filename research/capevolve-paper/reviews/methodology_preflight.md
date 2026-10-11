# Methodology preflight review

_Reviewer: independent methodology/statistics (stats-reviewer subagent), 2026-10-11. Saved verbatim by the coordinator._

Scope: planned protocol (CapEvolve_Paper_Plan.md; the prior literature review is untrusted and not relied on) checked against the code at base e3cb513. Evidence: analysis/out/sim_*.md.

## Verdict
The plan's intent is right, in particular its warnings against calling a 0.95 posterior a frequentist guarantee and against test reuse. The repository does not enforce those safeguards. Three results change how numbers must be interpreted: (1) the default hill-climb gate accepts at least one null edit in a 10-iteration search more than half the time (k=1: 0.54-0.58) and 83-86% of the time at the historical 0.2-0.3; (2) reported dev-val gains are about 4x the gain on new tasks; (3) two default code paths (footprint masking, dropping errored trials) can turn a harmful or null edit into an accepted one at 50-90%. A well-run confirmatory campaign is still possible, but only if the rules below hold and the headline comes only from the untouched set.

## 1. Three-way data separation
Enforced: the gate refuses any split except val (gate.py TrainGateError); test is scored once per RUN DIRECTORY (splits.py:43-50, seal-on-success).

Not enforced:
- The seal is per run, not global. harness.py:860-880 (reuse_baseline) copies splits.json and forces test_used back to unused; any run-dir copy resets it. Every method/seed run scores the same test tasks, each legitimately "once"; across runs nothing detects choosing the best seed/method/budget after seeing test (forking paths).
- act.py finalize --seal-anyway REASON scores test for a champion that failed its confirmation gate; the baseline is scored on test in every run, so baselines get multiple test measurements (source of 76.5 vs 76.8 style discrepancies).
- Val is used for gating, parent selection, champion selection and best-of-seeds. sim_gate (f), n=5: k=1 measured gain +0.055 vs true +0.014 on new tasks, 32% of accepted candidates truly non-positive; k=0.3 +0.074 vs +0.022.
- "Untouched" needs provenance. The plan itself says the 280-task SpreadsheetBench test may have influenced development; if so it is a dev split and a truly untouched family-level set is needed. Variants of one instruction must stay in one split (family leakage).
- Evaluator access: the plan requires the evaluator to be inaccessible to candidate edits in the final campaign. I did not verify this in code; splits.json lives in the run dir. repo-auditor should confirm what the optimizer workspace can read.

## 2. Untouched final campaign
- Valid only if executed once from a frozen manifest; any change to tasks, scorer or evaluator after any look at final data invalidates it for that purpose.
- Provider drift is a confound: interleave final scoring of all arms (randomized order) in a short window; record model snapshot ids and timestamps per rollout.
- Trial seeds are deterministic (trials.py:56, base_seed + k); many providers ignore seeds, so trials may not be independent of a prior measurement. Confirmation and final evaluation must use new seeds (act.py finalize continues the ledger trial index, good); verify provider sampling actually varies with seed.
- The ledger pools trials by content hash across tags (eval_index), so trials from different times/provider states can be pooled into one posterior. Record timestamps; pool only within a drift-free window.

## 3. Test reuse across runs
The plan's matrix is 4 methods x 2 suites x 3 seeds scored on one shared test set per suite. Required: a campaign-level ledger of every test-scoring event (artifact hash, evaluator hash, time); a frozen artifact manifest is scored once; all registered arms reported whether or not they look good.

## 4. Posterior threshold mistaken for a frequentist guarantee
- posterior.py accepts when P(D>0.02)>=0.95 under per-task Beta priors centered on the parent. It is a heuristic with simulated operating characteristics, not a 5% false-accept bound.
- Measured null acceptance (sim_posterior, any of 4 looks): 0.4-2.2% for mid-range tasks; 3.3% at mild heterogeneity; 20% when most tasks are near ceiling (mu .8, parent n=5), 42% with parent n=3, 4% at parent n=10, 1% at n=20.
- Mechanism: the parent posterior understates ceiling tasks (Jeffreys prior) while extra candidate trials push the candidate posterior toward 1 under a prior centered on an uncertain parent. The claim "validated under repeated looks" in code comments is therefore unsupported in these regimes; I could not find a reproduction of research/design/sim_eval.py, so do not cite it without re-running.
- The default promote gate (reward_gated) is different: floor 0.031 and z=2.73 (objectives.py:41,92,176,359) => reward-superior accept needs mean delta >0.085 at any sample size; +0.10 powered at only 0.27-0.45. Hill-climb's effective bar is ~0.04, so hill-climb vs agent-optimize confounds method with gate strictness.
- Paper wording: "decision rule with simulated operating characteristics under the stated data-generating process", never "95% confidence" or "5% error".

## 5. Other hazards found in code
- Footprint masking is ON by default (harness.py:2837, footprint_gate: bool = True). The footprint comes from a text search of rollouts, so outcome-dependent footprints are possible. A genuinely harmful edit (true -0.043) is accepted 0.84 when the footprint misses its regressions vs 0.01 unmasked; a null edit with an outcome-dependent footprint 0.89; paired_se_floor barely mitigates.
- Dropped errored trials (harness.py:587) bias the delta upward when failures surface as errors; the coverage guard is blind to it (analysis plan section 6).
- Coverage uses the candidate side only (harness.py:3022).
- The loop re-uses one parent measurement across candidates, so false accepts are dependent; accepted noise propagates into the next baseline.
- combined_stderr double counts within-task noise (analysis plan 3a); reported val +- SE is wrong for both estimands.
- Three search seeds give 2 df; E3 (pipeline variance) is essentially unestimable (sigma in [0.52 s, 6.3 s]).

## Required protocol rules
- R1 A held-out set counts as "untouched" only with a provenance record (creation date, exposure history, family ids); any set that influenced method development is reclassified as dev.
- R2 The three splits (optimization, model-selection, untouched final) are family-disjoint; variants of one instruction stay together.
- R3 One campaign-level ledger of test-scoring events; a frozen artifact manifest is scored once; all registered arms and seeds are reported.
- R4 The test seal is also enforced outside the run dir; no run-dir copy or reuse_baseline may reset it for the final campaign.
- R5 One shared baseline measurement per suite serves all contrasts; --seal-anyway results are labelled "no accepted change".
- R6 The final evaluator and test labels are inaccessible to optimizer workspaces; audit and record actual read permissions.
- R7 Freeze (hash) the analysis plan, task manifest, model registry, evaluator, classifier, comparison family and artifact hashes before final scoring.
- R8 Interleave final scoring across arms in randomized order; record model snapshot ids and timestamps.
- R9 Use new seeds for all confirmation and final evaluations; verify the provider honours seeds.
- R10 All confirmatory methods use the same promotion rule P (analysis plan section 8) and the full unmasked delta vector (footprint_gate=False).
- R11 Report gain only from fresh re-measurement of the seed and the final champion; never report dev-val gains or gate deltas as results.
- R12 Gate strictness is a controlled factor: match it across methods, or report each gate's operating characteristic and ablate.
- R13 Never call posterior thresholds frequentist guarantees; publish simulated operating characteristics (incl. ceiling-heavy and unbalanced-n cases).
- R14 Count candidate-induced errors as failures; retry exogenous errors symmetrically with a fixed cap; classify blind to arm and outcome.
- R15 Compute coverage on the paired intersection; require >=95% valid cells for confirmatory evaluation, with pessimistic/optimistic bounds.
- R16 Never use combined_stderr; use cluster-robust task-level paired SEs, the within-only formula for fixed-task statements, and require n_t>=2.
- R17 With <30 families the headline CI is the cluster-robust t interval, not the percentile bootstrap.
- R18 Control FWER with Holm over a frozen comparison family; everything else is exploratory.
- R19 Pipeline-level (E3) claims need S>=5 seeds; with S=3 report raw per-seed values and make only artifact-level claims.
- R20 Decide the budget with the MDE table; the campaign's 10,000-rollout cap is inconsistent with a 280-task, multi-arm, multi-trial final evaluation.
- R21 Report failed and aborted searches; never drop a seed after seeing its result.
- R22 Cost accounting follows analysis plan section 9; unpriced endpoints are "unknown", never 0.
