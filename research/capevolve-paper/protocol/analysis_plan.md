# Preregistered analysis plan (confirmatory runs)

_Author: independent methodology/statistics reviewer (stats-reviewer subagent), 2026-10-11. Saved verbatim by the coordinator because subagents cannot write .md report files._

Status: DRAFT for coordinator approval. Becomes binding when its SHA-256 and the final-task manifest hash are written to experiments/registry.jsonl BEFORE any untouched-final-set rollout is scored. Anything not specified here is exploratory and must be labelled so. Evidence: analysis/out/sim_*.md|json (scripts analysis/scripts/sim_*.py, run on the real core/cap_evolve code; pure stdlib, run with python3.12 -I). Items marked [PLACEHOLDER] must be re-estimated from the development pilot before freeze (edit constants in sim_mde.py).

## 1. Estimands
Arm a = an artifact (seed artifact, one-shot repair, or champion of method m under search seed s). y_a(t) = expected reward of a on task t over execution randomness; observed task score = mean of valid trials. All contrasts are paired on tasks.

| id | name | definition | supports | interval must include |
|---|---|---|---|---|
| E1 | fixed-task-set score | theta1(a) = (1/T) sum_t y_a(t) over THE untouched final set | "on this split a scores X, beats b by D" | execution randomness only |
| E2 | generalization to new tasks/families | theta2(a) = E_t[y_a(t)] over the population the final set was drawn from (new families for transfer suite) | "optimized artifacts transfer" | task sampling (family-clustered) + execution |
| E3 | optimization-pipeline variance | distribution of champion E2 score over search seeds for fixed method, budget, start | "method reliably improves", best-of-S vs typical | search-seed sampling (S searches) + tasks within each |
| E4 | cost | section 9 | amortized value | search-cost variance across seeds, deployment-cost sampling |

Primary headline per suite: E2 advantage of each method's champion over the seed artifact, reported with the E3 spread. E1 goes in benchmark tables but is never offered as evidence of generalization. ONE shared baseline measurement of the seed artifact serves every contrast on a suite (avoids the 76.5/76.8 and 38.5/38.6 discrepancies).

## 2. Data hierarchy
- Unit of inference: the task, clustered by family. Trials are only averaged within a task; every task has weight 1 regardless of trial count.
- Families: tasks sharing an instruction template, source workbook or generator; ids from the data steward's manifest, fixed before scoring.
- Search seed: one independent end-to-end optimizer run from the same starting artifact, split and budget. Final-set evaluation seeds are independent of search seeds.
- Crossed/paired design: every (arm, seed) champion scored on the same final tasks.
- S=3 seeds gives 2 df. Pipeline-level intervals use t(S-1) (4.30 at S=3). Seed-level percentile bootstraps are NOT the headline when S<8.

## 3. Estimators
Paired difference d(s,t) = ybar_A(s,t) - ybar_B(t), baseline row broadcast over seeds.

| estimand | point | SE | interval |
|---|---|---|---|
| E1 per arm | mean_t ybar(t) | sqrt(sum_t se_t^2)/T, se_t = trial SD/sqrt(n_t); needs n_t>=2 | normal +-1.96 SE |
| E1 contrast | mean_t d(t) | sqrt(sum_t(se_A,t^2+se_B,t^2))/T | normal |
| E2 contrast conditional on the S champions | mean over (s,t) of d | family-cluster-robust (CR1) SE of seed-averaged task deltas | t(C-1) if C<30 families else normal; cluster bootstrap as check |
| E2 pipeline contrast (claim about the optimizer) | mean over s of per-seed mean delta | variance of per-seed means (df=S-1) combined with task-cluster component | t(S-1) on per-seed means (headline); crossed "task+seed" bootstrap as companion |
| E3 spread | sample SD of per-seed champion E2 scores | n/a | chi-square df=S-1; at S=3 sigma in [0.52 s, 6.3 s]; always report the S raw values |

Implemented in analysis/scripts/paired_cluster_bootstrap.py (paired_cluster_bootstrap, signflip_pvalue, holm); families resampled jointly across arms and seeds. Self-test (12 families, 60 tasks, 3 seeds): percentile bootstrap covers 0.86, size 0.14; CR1 t covers 0.93, size 0.075; ignoring clustering covers 0.69. Rule: below 30 families the headline interval is cr_ci, not the percentile bootstrap.

### 3a. Why not stats.combined_stderr
stats.py:35-53 returns sqrt(var(task means)/T + sum se^2/T^2). Variance of observed task means already contains within-task noise, so the second term adds it again. sim_stderr.md (mu .55, kappa 1.5, T=40/280):

| n trials | combined^2/Var(new tasks) | combined^2/Var(fixed tasks) | coverage combined vs new-task target | coverage between-only vs new-task target |
|---|---|---|---|---|
| 1 | 1.00 | 1.6 | .94-.95 | .94-.95 |
| 3 | 1.33 | 3.9 | .97 | .94-.95 |
| 5 | 1.24 | 5.4 | .96-.97 | .94 |
| 10 | 1.13 | 8.6 | .96 | .94-.95 |

New-task estimand: variance overstated 12-33% at kappa 1.5 (up to 63% at kappa 5, n=3), SE 6-28%; between-task term alone is correct. Fixed-task estimand: variance overstated 1.2-8.6x; only the within term is right. At n=1 the within term is 0 so combined_stderr silently equals between-only. Paired gate SE (gate.py:430-437) matches new-task contrast variance (ratio 1.00); unpaired `significant` mode (gate.py:461-462) uses 1.5-6.2x more variance. Rule: the paper never reports SplitResult.stderr. E2 SEs come from cluster-robust task-level deltas; E1 SEs use the within-only formula (n_t>=2) or the E1 interval is not reported.

## 4. Reporting vocabulary
- SD: spread of individual units, always labelled with its unit ("SD across tasks", "SD across search seeds, n=S"). Never used to express uncertainty about a mean.
- SE: SD of the ESTIMATOR over repeats of the sampling process named in the estimand (execution for E1; tasks/families for E2; seeds for E3). Always states which.
- CI: 95% interval from the section 3 estimator. Template: "mean paired difference +0.062, 95% CI [0.021, 0.103] (cluster-robust, 56 families, 280 tasks, 3 seeds averaged)". Not a statement about where the true value lies; not a prediction interval.
- Range/prediction interval: only for E3, raw per-seed values plus mean +- t*SD*sqrt(1+1/S), labelled with S.
- Dev-val numbers (gate deltas, val curves, posterior probabilities) are search diagnostics, never results; under the one-stage gate reported gains are ~4x the true gain on new tasks.
- Every table cell states n tasks, n families, n seeds, n trials/task; no table mixes estimands in a column.

## 5. Inference and multiplicity
- Comparison family frozen with this plan, one row per (suite, contrast): e.g. each of 4 search methods vs seed artifact, hill-climb vs agent-optimize, each method vs matched strongest-competitor arm, per primary suite. Unlisted contrasts are exploratory, no p-values in the abstract.
- Holm step-down at FWER .05 within a suite; each suite is its own family; a cross-suite claim needs both to pass.
- Primary test per contrast: two-sided cluster-robust t (cr_p_two_sided) at E2 level; sign-flip randomization p (signflip_pvalue) as pre-declared robustness check. If they disagree, report both; do not resolve post hoc.
- "Win" language only if Holm-adjusted p<.05 AND CI excludes 0 under the pessimistic missingness bound of section 6. Otherwise "no detectable difference at the MDE of X".
- Non-inferiority (cost/latency): margin fixed before freeze; claim needs one-sided 97.5% lower bound above -margin.
- Ablations: Holm within each ablation family or labelled exploratory.
- No result may be added, dropped or re-run based on outcome. A crashed/aborted search stays in the denominator; its champion is the seed artifact unless a candidate had already been accepted.

### 5-AMENDMENT 1 (2026-10-11 21:15 UTC; written before the search cutoff 2026-10-13 06:00 UTC; no final-set data seen)

Supersedes the sentence "each method vs matched strongest-competitor arm" above (it is data-dependent). Everything else in section 5 stands. Reason: review item A2 (TRIAGE.md); the first version had no pre-specified CapEvolve-vs-baseline test.

**5A. Primary (confirmatory) family, per suite.** All contrasts paired by task, cluster-robust (CR1 t, section 3) at the matched checkpoint B*, Holm within the suite. CapEvolve arms are hc (hill-climb, rule P) and ao (agent-optimize, rule P). Tier 1 baselines are the matched-budget Tier 1 arms actually run on the suite; "cheap" arms are not in the primary family.
- Suite A (12 rows): {hc, ao} x {seed, GEPA, SkillOpt, Meta-Harness, WikiSkill, EvoSkill}. No one-shot control on A.
- Suite B (8 rows): {hc, ao} x {seed, one-shot, GEPA, HarnessLens}.
- Suite C (6 rows): {hc, ao} x {seed, one-shot, GEPA}. Suite C is development-exposed: reported with p-values but never the sole basis of a generalization claim.
A baseline row that has an incomplete seed under the B* rule (B* rule in decisions.md) leaves the family and the Holm denominator shrinks accordingly; the reason is reported. No arm is added after the cutoff.

**5B. Secondary families (own Holm each, reported as secondary):** (i) every Tier 1 and cheap baseline vs seed, per suite (A 8 rows, B 2, C 1); (ii) hc vs ao, and each CapEvolve arm vs each cheap arm (Suite A: ACE, MIPROv2, Trace2Skill). Superiority is the only hypothesis; no equivalence claim is made without a pre-stated margin.

**5C. Exploratory (no p-values in abstract or headline):** E12 (stock gate vs rule P, Suite C only), Tier 2 arms, footprint and merge ablations, any contrast not listed above.

**5D. Secondary analysis: native end-of-run artifacts.** For each arm, the artifact the method would deploy at the cutoff under its own native rule, with budget NOT matched (arms with budget-coupled schedules, e.g. SkillOpt cosine learning-rate schedule, GEPA max-metric-calls, iteration-capped arms, are named in the paper). Same rows as 5A, own Holm family per suite, labelled "unmatched budget". The primary analysis stays at matched B*. If the two analyses disagree in sign or in significance for a 5A row, both are reported side by side and the primary stands.

**5E. Unit of the rule-P false-promotion rate.** The probabilities in section 8 and in the paper (0.040 for B, 0.113 for C, 0.068 for A at option c) are P(at least one false promotion in one search), where a search screens about 7 to 10 candidates; the per-candidate rate is roughly 0.6 to 1.3% (1-(1-P)^(1/N)). They are simulation results under stated assumptions, not guarantees.

**5F. Observed variance replaces the assumed MDE inputs (section 7 is superseded for B and C).** `analysis/out/mde_observed.md` re-estimates trial noise and between-task variance from the unmodified seed artifact on the search splits: Suite A val-40 (6 evaluations; within-task variance 0.088; observed evaluation-to-evaluation SD of the split mean 0.088 vs 0.047 binomial, i.e. an evaluation-batch SD of about 0.075), Suite B opt-49 (15 trials/task; within var 0.148, SD of true p 0.31, kappa 1.5) and Suite C opt-20 (9 trials/task; within var 0.124, kappa 0.9). Measured paired null SD (0.55 B, 0.50 C) matches sqrt(2 x within var). The between-task SD tau of the true advantage cannot be identified from baselines; MDEs are tabulated for tau in {0, 0.10, 0.15, 0.25}. Consequence: with 3 seeds and final sets of 70 / 40 / 20 tasks the conditional (artifact-level) MDE at tau = 0.15 is 0.12 (A, n=1), 0.16 / 0.125 / 0.11 (B, n = 1 / 2 / 3) and 0.22 / 0.17 / 0.15 (C); pipeline-level MDEs are 0.24, 0.31 and 0.41 (n=1), and under the Holm first-step level they are larger still. Suites B and C are therefore descriptive transfer-of-protocol suites; Suite A is only informative for large effects. All arms of a suite must be scored interleaved in random order in one window, because the Suite A batch effect would otherwise raise the conditional MDE at T=70 from 0.12 to about 0.27.

**5G. Rule-P operating point at the actual task counts.** `analysis/out/sim_budget_{A,B,C}.md` (real `promotion.screen/decide`, 550 counted search rollouts on B and C, 600 on A, up to 10 candidates, observed difficulty). Option c (n_conf 3, z_conf 1.282, dmin 0) has P(>=1 false promotion per search) 0.040 (B, screen on opt-49), 0.113 (C, opt-20), 0.068 (A, val-40) and power at a true +0.08 edit of 0.33, 0.17 and 0.40. Option n_conf 5 / z 1.645 is not used because one confirmation costs 2 x T x n_conf rollouts: 400 of 600 on A, 490 on B (more than the 452 left after the baseline and one screen, so no promotion is ever possible: power 0), 200 on C; on A and C it lowers the expected true gain of the champion relative to option c (A +0.0007 vs +0.0014; C +0.0015 vs +0.0024) together with the false-promotion rate.

## 6. Missingness and invalid rollouts
The harness averages only valid trials (harness.py:587-601), drops a task from a paired vector when either side has zero valid trials (harness.py:1060-1065), and the coverage guard (harness.py:3022, gate.py:397) looks only at the candidate side and whole tasks. Simulation (sim_footprint.md d): dropped candidate-induced errors turn a null edit into 52-89% acceptance while coverage stays >=0.96.
1. Classification by a frozen deterministic classifier (error class, exit code, exception-type allowlist), applied blind to arm and reward, published with the code. Anything unclassified counts as a failure.
2. Exogenous failures (provider 429/5xx, gateway timeout with provider-side evidence, container pull failure, host OOM not attributable to the artifact): retried up to R=3 further attempts, same policy and cap on EVERY arm; retries triggered by error class only, never by a prior outcome; cost charged to the arm. A trial exhausting R is a missing cell.
3. Artifact-induced failures (exception in artifact code, malformed/missing output, tool crash caused by the artifact, exceeding per-task wall-clock/turn/token cap) count as a trial with reward 0; never dropped from the task mean.
4. Complete-case primary analysis over tasks with >=1 valid trial in BOTH arms only if (a) missing fraction <=5% per arm and (b) missing counts not associated with arm (Fisher exact p>=.10). Otherwise report the contrast with bounds only.
5. Bounds always shown next to the primary estimate: pessimistic = missing cells of the evaluated arm scored 0 and of the comparator arm scored 1; optimistic = the reverse. A contrast is "robust" only if the pessimistic-bound CI excludes 0. Wide bounds are shown, not hidden.
6. Inner-loop min_coverage=0.6 may stay as a search-time safeguard but computed on the paired intersection, not the candidate side only. Confirmatory evaluation requires >=95% of (arm, task) cells valid after retries; otherwise re-execute the suite or declare it invalid for the headline.
7. Per-arm report: attempted, retried, exogenous-missing, artifact-failed counts by class.

## 7. Minimum detectable effect and budget planning
Model (sim_mde.py; Monte Carlo check var .000530 vs formula .000544): Var(theta_hat) = DEFF*tau^2/T + sigma_s^2/S + DEFF*(tau_int^2 + noise/n)/(T*S); alpha .05 two-sided, power .80. [PLACEHOLDER] inputs until the pilot reports them: tau=0.15 (SD across tasks of true per-task advantage), tau_int=0.10 (seed x task interaction), sigma_s=0.03 (SD of champion quality across seeds), trial noise 0.297/n (mu .55, kappa 1.5), family size 5 with ICC .10 (DEFF 1.4). Sensitivity in sim_mde.md.

MDE in absolute reward points, S=3:

| T | n | artifact-level (the 3 champions) | Holm m=3 | pipeline-level t(2) | Holm m=3 |
|---|---|---|---|---|---|
| 40 | 3 | .127 | .147 | .261 | .423 |
| 40 | 5 | .112 | .129 | .234 | .379 |
| 100 | 3 | .080 | .093 | .180 | .292 |
| 100 | 5 | .071 | .082 | .164 | .267 |
| 280 | 3 | .048 | .055 | .131 | .212 |
| 280 | 5 | .042 | .049 | .123 | .200 |

At n=5 pipeline-level MDE is .142/.098/.071 at S=5 and .105/.070/.048 at S=10 for T=40/100/280. Method-vs-method (tau .10, artifact-level, n=5, S=3): .095/.060/.036.

Reading: (1) with 3 seeds no pipeline-level claim below ~12 points is powered at any plausible T (t(2)=4.30 is the binding constraint). Either claim only the artifact-level estimand and say so, or buy seeds (S=5 roughly halves pipeline MDE) at smaller per-search budget. (2) Method-vs-method gaps of 2-5 points are undetectable at T<=100; descriptive unless T>=280 and artifact-level estimand. (3) Final-eval rollouts per suite = (4 methods x S + C controls) x T x n; S=3, C=2: 1,680 (T40,n3), 4,200 (T100,n3), 11,760 (T280,n3). campaign.yaml caps the WHOLE campaign at 10,000 target rollouts; two suites at T=100,n=3 use 8,400 (84%) before any search rollouts. Coordinator should raise the cap, cut arms (one shared baseline; one-shot repair one seed only), cut n to 2 on the final set, or accept the left-hand MDE columns.

## 8. Promotion and selection rules feeding the confirmatory analysis
Search-time gates are heuristics; confirmatory numbers come only from the untouched final set. Every method uses the SAME promotion rule P:
1. Screen on dev-val with the paired gate k_se=1 on the full UNMASKED delta vector (footprint_gate=False).
2. Confirm: re-evaluate candidate and incumbent with fresh trials (new seeds, n_conf>=10/task) on the same dev-val tasks. Promote iff mean delta >=0.02 and delta/SE_paired >=2.0 (z=1.645 instead raises null promotion from 3.7% to 7.7% per 10-iteration search).
3. The incumbent's confirmation measurement is the baseline for the next iteration.
4. Per-method budget stated in evaluation calls, including confirmation calls.
5. Deployed artifact = last promoted candidate, not the best-looking dev score seen.

Operating characteristics (T=40, screen n=5, 10 iterations; sim_promotion.md): P(>=1 false promotion) 0.57 one-stage k=1 vs 0.04-0.08 under P; power +0.08: 0.85 vs 0.68-0.73; +0.10: 0.92 vs 0.87-0.90.

## 9. Cost accounting
All money metered from provider usage logs. Unpriced endpoint = "unknown", excluded from sums, sum flagged "lower bound", never treated as 0.
- Optimization cost C_opt(m,s): everything spent to produce champion (m,s): proposer + target rollouts on dev data (incl. screening and confirmation) + judges/simulators/diagnostics; tokens, USD, rollouts, wall hours; per seed with mean +- SD over seeds. Failed/aborted searches included.
- Cost per usable champion for "run S searches, deploy the best on dev" = S * mean C_opt; its accuracy is subject to best-of-S winner's curse, so it gets its own final-set row, not the per-seed mean.
- Deployment cost c_a: metered target cost of one deployed task attempt on the untouched final tasks under the same retry policy: mean over tasks of mean trial cost INCLUDING failures and retries; also cost per success c_a/p_a (ratio estimator, family-cluster bootstrap CI).
- Net value per task v(a) = R*p_a - c_a for a task reward R declared in advance (R=0: cost-only view, compare c_a at equal accuracy within the non-inferiority margin).
- Break-even volume V*(m,s) = C_opt(m,s) / (v(champion) - v(baseline)) tasks, defined only when the lower CI bound of the value difference is >0; otherwise "no break-even established" with the denominator's interval. Its CI combines the family-cluster bootstrap of the denominator with the empirical spread of the numerator over seeds; never a delta method when the denominator CI includes 0.
- Optimizer-model cost and deployed-target cost in separate columns; a combined column only when both are fully priced. Optimization cost and deployment savings are never netted into one number without both components shown.

## 10. Freeze list
Before any untouched-final scoring, hash and record: this plan; final-task manifest with family ids; model registry (provider, model id, snapshot/date, temperature, max tokens); evaluator and scorer code; the section 6 classifier; the section 5 comparison family; content hashes of all artifacts to be scored incl. the single baseline; analysis scripts at the commit used. Deviations after freeze go in decisions.md with reason and effect on interpretation; deviating analyses are labelled exploratory.
