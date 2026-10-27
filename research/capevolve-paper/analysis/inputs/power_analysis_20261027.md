# Power / sample-size analysis (read-only; no paper edits)

Data: tau2 airline raw trials (MERGED, K2GATEWIN windows; 20 test tasks; CapEvolve = GATE-K2 s0,s1,s3 at 10 trials; comparators 3 seeds x 10 trials; baseline 20 trials) and AppWorld TEST_ALL (5 trials, 168 tasks, 56 scenarios). Scripts: /tmp/pa/*.py. I reproduce the paper's estimates, SEs and raw p exactly (e.g. SkillOpt +0.0617, SE 0.0299, p 0.0534).
Needs scipy (installed with pip for this run).

## 0. Method
For a paired contrast over C tasks, Var(mean diff) = (1/C) * [ noise/k + P + T ], with
- noise/k (a): trial noise of the two task means, shrinks as 1/k (k = trials multiplier over today's 10).
- P (c): search x task variance, shrinks as 1/S (S = searches per method). Estimated from the 3 searches of CapEvolve and of the comparator (rough; 3 searches).
- T (b): true task-by-method heterogeneity of the effect; shrinks only with more tasks C.
Power is noncentral-t at the OBSERVED estimate (optimistic, winner's curse). "Shrunk" = 0.75 x observed effect.
Noise is estimated as the within-cell variance of trials / n; (P+T) is the remainder of the observed variance of the per-task difference.

## 1. Non-significant tau2 comparisons, variance decomposition
Share of the variance of the per-task difference (so of SE^2), CapEvolve (3 searches) minus comparator (3 seeds).

| Comparison | Est | SE | raw p | Holm p (m=10) | (a) trial | (c) search | (b) task | SE if trials->inf | p at SE(inf) |
|---|---|---|---|---|---|---|---|---|---|
| minus SkillOpt | +0.062 [-0.001,0.124] | 0.030 | 0.053 | 0.174 | 38% | 38% | 25% | 0.0237 | 0.017 |
| minus Trace2Skill | +0.080 [-0.004,0.164] | 0.040 | 0.061 | 0.174 | 23% | 15% | 62% | 0.0353 | 0.035 |
| minus EvoSkill | +0.077 [0.003,0.150] | 0.035 | 0.042 | 0.174 | 25% | 16% | 59% | 0.0304 | 0.021 |
| minus GEPA (full) | +0.077 [0.006,0.148] | 0.034 | 0.036 | 0.174 | 30% | 25% | 45% | 0.0283 | 0.014 |
| minus ACE | +0.095 [0.008,0.182] | 0.042 | 0.035 | 0.174 | 20% | 16% | 63% | 0.0373 | 0.020 |
| minus WikiSkill | +0.113 [0.028,0.199] | 0.041 | 0.012 | 0.071 | 21% | n/a | n/a | 0.0363 | 0.003 |
| minus GEPA | +0.088 [0.026,0.150] | 0.030 | 0.0075 | 0.060 | 38% | n/a | n/a | 0.0233 | 0.0003 |
| minus MIPROv2 | +0.127 [0.038,0.216] | 0.042 | 0.0077 | 0.060 | 19% | n/a | n/a | 0.0383 | 0.002 |
| minus baseline (headline) | +0.133 [0.041,0.226] | 0.044 | 0.007 | | 23% | n/a | 77% (c+b) | 0.0387 | 0.003 |

Pipeline-level interval [-0.059, 0.325] (t2): its width is the t_{0.975,2}=4.30 multiplier on SE_pipe (0.044 task, s_search 0.010). Trials cannot move it; only S can:

| S searches | 3 | 4 | 5 | 6 | 8 | 10 |
|---|---|---|---|---|---|---|
| half-width | 0.192 | 0.142 | 0.123 | 0.114 | 0.105 | 0.100 |
| lower bound (gain 0.133, same s_search, same task SE) | -0.058 | -0.008 | +0.010 | +0.019 | +0.028 | +0.033 |

(Task SE would also shrink a little with more searches, so these are conservative.) So 5 to 6 CapEvolve searches make the pipeline-level CI exclude 0 if s_search stays near 0.010. This is the only way to that claim.

Retention 0.41 vs 0.28 (bootstrap [-0.20, 0.43]): the half-width (0.31) is 2.4x the effect; it is driven by task and search-task resampling of both groups, and the pooled-published side alone spans [-0.09, 0.81]. Extra trials on the 30 search tasks or 20 test tasks cannot fix it; roughly 5 to 6x more tasks and searches for the 8 comparators would be needed. I recommend treating it as descriptive.

## 2. Power and required sample (tau2, tasks fixed at 20)
Columns: power at alpha 0.05 with k = 1 (today), 3 (30 trials), inf; power at the Holm-relevant alpha 0.0125 (the rank where these rows land, 4 comparisons left) with k=inf; trials needed; tasks needed (C) for 80% power at 0.05 and at 0.0125 (k=3).

| Comparison | pow k=1 | k=3 | k=inf | pow k=inf @0.0125 | k needed for 80% @0.05 | tasks needed 0.05 (k=1 / k=3) | tasks needed @0.0125 (k=3) |
|---|---|---|---|---|---|---|---|
| SkillOpt | 0.50 | 0.62 | 0.70 | 0.46 | never | 39 / 30 | 43 |
| Trace2Skill | 0.47 | 0.54 | 0.58 | 0.34 | never | 42 / 36 | 51 |
| EvoSkill | 0.54 | 0.62 | 0.67 | 0.43 | never | 35 / 30 | 43 |
| GEPA (full) | 0.57 | 0.67 | 0.73 | 0.50 | never | 33 / 27 | 38 |
| ACE | 0.58 | 0.64 | 0.68 | 0.44 | never | 33 / 29 | 41 |
| gate: NAIVE | 0.48 | 0.53 | 0.57 | 0.33 | never | 42 / 36 | 52 |
| gate: NONE | 0.43 | 0.86 | 1.00 | 1.00 | k=3 | 47 / 18 | 25 |

Conclusion: for the five close comparators trials alone never reach 80% power at the observed effect (task/search heterogeneity dominates), and under Holm even infinite trials reach only 34 to 50%. Expected Holm rejections out of 10 (simulation, tasks resampled, effects = observed): k=1 4.3, k=3 5.7, k=inf 6.4; with 75% shrunken effects 1.6, 2.5, 3.0. With 40 tasks (k=3): 9.4 of 10 at observed effect; 7.0 shrunk.

Per-comparator Holm-pass probability (observed effect): HarnessLens .65/.84, Meta-Harness .65/.86, GEPA .50/.69, MIPROv2 .53/.66, WikiSkill .45/.58, ACE .33/.42, GEPA(full) .31/.44, EvoSkill .29/.41, SkillOpt .29/.41, Trace2Skill .27/.36 (k=1 / k=3).

More tasks: airline has 50 tasks total (30 search + 20 test), all used; there are no unused airline tasks. More tasks need another domain, which needs new searches for every arm (retail test split of 40 sealed tasks exists in the separate Suite B; that is independent, not an extension of this table).

## 3. Gate ablations and tau2 component ablations (arm vs CapEvolve search 1, single search each)

| Contrast | est (s1 minus arm) | SE | raw p | trial share | task+search share | SE k=3 | p k=3 | SE k=inf |
|---|---|---|---|---|---|---|---|---|
| Gate NONE | +0.050 | 0.0267 | 0.076 | 99% | 1% | 0.0156 | 0.005 | 0.003 |
| Gate NAIVE | +0.130 | 0.0649 | 0.060 | 20% | 80% | 0.0604 | 0.045 | 0.058 |
| Policy only | +0.095 | 0.0444 | 0.046 | 50% | 50% | 0.0362 | 0.017 | 0.031 |
| Tools only | +0.090 | 0.0486 | 0.080 | 45% | 55% | 0.0406 | 0.039 | 0.036 |
| Grader output only | +0.090 | 0.0552 | 0.119 | 32% | 68% | 0.0491 | 0.082 | 0.046 |
| Minimal Claude Code | +0.085 | 0.0549 | 0.138 | 34% | 66% | 0.0484 | 0.095 | 0.045 |
| Trace and reward | -0.025 | 0.039 | 0.53 | | | | | no power (true effect near 0) |

Reading: Gate NONE is essentially all trial noise, so 30 trials on both sides settles it (80% power needs k=3). Gate NAIVE and the component arms are dominated by search-to-search and task-level variance; with k=3 they are borderline raw and none survives a 5-way correction (needs p<0.01). More searches per arm (3 each) would shrink the P term by 3 but costs ~$117 and 17 h per search; five arms x 2 extra searches = 10 searches (~$1.2k). A pooled test of the four "remove a component" arms (tools, policy, grader only, minimal Claude Code) against search 1 gives -0.090, SE 0.043, p 0.052 (adding Claude Code + CapEvolve prompt: -0.091, p 0.039); a free single-contrast summary, but post hoc and sharing search 1 as reference.

## 4. AppWorld (TEST_ALL, 5 trials, 168 tasks/56 scenarios)
Trial-noise share of SE^2 computed from the pass-count distributions (5-trial per-task Bernoulli variance) vs the published scenario-clustered CI; SE in TGC points.

| Other minus CapEvolve | Delta | CI | raw p | Holm-78 | Holm m=10 (tau2-style family) | noise share | SE (5 tr) | SE (10 tr) | SE (20 tr) | SE (inf tr) |
|---|---|---|---|---|---|---|---|---|---|---|
| Trace2Skill | +0.7 | [-4.8,6.2] | 0.81 | no | 0.81 | 28% | 2.81 | 2.60 | 2.49 | 2.38 |
| GEPA-Full | -2.1 | [-7.3,2.9] | 0.40 | no | 0.80 | 34% | 2.60 | 2.37 | 2.25 | 2.12 |
| SkillOpt | -4.0 | [-9.3,0.8] | 0.11 | no | 0.44 | 35% | 2.58 | 2.34 | 2.22 | 2.08 |
| ACE | -4.0 | [-9.9,1.3] | 0.14 | no | 0.44 | 28% | 2.86 | 2.65 | 2.54 | 2.43 |
| GEPA | -5.1 | [-10.1,-0.4] | 0.038 | no | 0.19 | 37% | 2.47 | 2.23 | 2.10 | 1.96 |
| EvoSkill | -6.7 | [-11.9,-1.7] | 0.011 | no | 0.065 | 36% | 2.60 | 2.35 | 2.22 | 2.08 |
| WikiSkill | -8.8 | [-14.9,-2.5] | 0.0066 | no | 0.046 | 27% | 3.16 | 2.94 | 2.82 | 2.70 |
| MIPROv2 | -9.8 | [-16.1,-3.8] | 0.0014 | no | 0.011 | 24% | 3.14 | 2.95 | 2.84 | 2.74 |
| Meta-Harness | -14.9 | | <1e-4 | yes | <0.001 | | | | | |
| HarnessLens | -31.4 | | <1e-4 | yes | <0.001 | | | | | |

(Holm m=10 computed from the raw p in aw_testall_vs_cape.csv; p for the two largest gaps are bootstrap-floor values.) Trials do nothing useful on AppWorld: even infinite trials give SE 2.0 to 2.7, so SkillOpt/ACE (delta 4) would sit at t about 1.9, p about 0.06. The floor is the 168 tasks (56 scenarios). Only more tasks help. Trace2Skill (+0.7 against CapEvolve) and GEPA-Full (-2.1) are ties: no experiment will show CapEvolve better, and the honest claim is "within noise of the best".

Free re-analysis: the paper's tau2 family is the ten comparisons of CapEvolve. On AppWorld the same family (m=10) lets MIPROv2 (0.011) and WikiSkill (0.046) pass as well as Meta-Harness and HarnessLens; EvoSkill 0.065 misses. The 78-pair Holm exists to cover all pairs of a session; the claim in the text concerns only CapEvolve vs each comparator, so the m=10 family matches the claim and the tau2 convention (state the choice).

test_challenge option (417 tasks, 3.5 x test_normal's 168, unseen difficulty, no new searches): at 2 trials the standalone SE for a CapEvolve-vs-X contrast is about 2.0 TGC (3 trials 1.8; 1 trial 2.5, assuming the same per-task heterogeneity and ignoring scenario clustering, which will make it worse); combined with test_normal, SE about 1.5 to 1.6. With delta 4 (SkillOpt, ACE) that is t about 2.5 to 2.7, power near 0.5 to 0.65 at Holm(10) rank 7 or 8 (alpha 0.0125 to 0.0167); for GEPA-Full (2.1) power under 0.3. Risks: ordering could change on harder tasks (CapEvolve could drop below Trace2Skill); the harder split also lowers pass rates, so noise share changes. Treat as a robustness/generalization result, not a significance fix.

AppWorld ablations (2 trials, one search each): four are already Holm-significant. Policy-only -0.9 [-6.5, 4.8] is an equivalence claim: to show |diff| < 3 points one would need SE about 1.5 (current about 2.9) = about 4x the cells; not worth it. Do not claim it "matches" beyond "indistinguishable".

## 5. Plans, cost, and expected result
Rates: tau2 1,200 jobs in about 30 min at 48 workers = about 40 rollouts/min (2,400/h). AppWorld: the 10,920-cell window ran at about 343 cells/h (ETA note at 4,172 done: 19.7 h left), i.e. about 32 h at that worker count; the 2,688-cell ablation windows took about 7 to 8 h (about 360 cells/h). Wall times scale with workers if the API allows.

| # | Plan | Needs | Rollouts / cost | Wall | Expected outcome |
|---|---|---|---|---|---|
| 0 | Re-analysis only: (i) AppWorld Holm over the 10 CapEvolve comparisons; (ii) tau2 Westfall-Young permutation maxT (sign-flip of the 20 task differences) instead of Holm; (iii) one pooled "CapEvolve vs mean of 9 comparators" test | nothing | 0 | minutes | (i) 4 of 10 AppWorld comparators significant (not 2). (ii) sign-flip maxT adjusted p: HarnessLens .013, Meta-Harness .013, GEPA .026, MIPROv2 .027, WikiSkill .042, ACE .125, GEPA(full) .125, EvoSkill .144, SkillOpt .19, Trace2Skill .21: 5 significant instead of 2 (a bootstrap maxT is worse, .052 to .27; it is not robust at n=20, report only if chosen a priori). (iii) +0.091 [SE 0.032], p=0.0096 (9 three-seed comparators, equal weights). All are post hoc choices of the multiplicity method: disclose. |
| 1 | Gate NONE + NAIVE + search 1 to 30 trials (20 extra each, on frozen artifacts) | eval only | 3 x 400 = 1,200 (or 1,600 with a fresh seed-check) | about 30 min | NONE: SE 0.027 to 0.016; if the +0.05 holds, CI [0.017, 0.083], p about 0.005 (80% power). NAIVE: SE 0.065 to 0.060; p about 0.045, CI upper bound just below 0 only if the +0.13 holds; likely stays "suggestive". |
| 2 | Add the 5 component ablation arms to 30 trials (on top of plan 1, which already includes search 1) | eval only | 5 x 400 = 2,000 | about 50 min | Policy-only p 0.046 to about 0.017; tools .080 to .039; grader only .12 to .08; minimal CC .14 to .095. Raw only; no arm survives a 5-test correction. Tightens CIs (half-width 0.093 to 0.076 policy only), no new claim. |
| 3 | CapEvolve 3 champions + baseline to 30 trials (comparators stay at 10) | eval only | 4 x 400 = 1,600 | about 40 min | Common reference in all 10 contrasts: noise term x0.67. SkillOpt SE .0299 to .0280 (p .053 to .043); Trace2Skill .0401 to .0386. Holm-expected rejections 4.3 to about 5.0. |
| 4 | Plan 3 plus all 9 comparators x 3 seeds to 30 trials | eval only | (3 + 27 + 1) x 400 = 12,400 | about 5.2 h | Holm-expected rejections 4.3 to 5.7. SkillOpt p .028, GEPA(full) .020, EvoSkill .027, ACE .024, Trace2Skill .044 (raw); none expected to pass Holm. Low value per rollout. |
| 5 | 3 more CapEvolve searches (S=6), paired with 20-trial test scoring (6 searches x 10 trials) | NEW searches | 3 x ~$117 = ~$350 plus 3 x 200 test rollouts = 600 | about 17 h (parallel) | Pipeline CI lower bound about +0.02 (if s_search stays about 0.010): the only way to a pipeline-level significance claim and it also shrinks the P term (15 to 38% of SE^2) in every comparator contrast. Comparators stay at 3 seeds. |
| 6 | Add 3 searches for each of SkillOpt, GEPA(full), EvoSkill, ACE, Trace2Skill (S=6 on both sides) | NEW searches | 15 searches, $18 to $281 each (~$0.7k to 1.2k) plus 3,000 test rollouts | 17 h (parallel) | With plan 5: SkillOpt SE .0236 (p about .017, power .70 raw, .46 at 0.0125); not enough alone. Not recommended. |
| 7 | AppWorld test_challenge: CapEvolve + Trace2Skill, GEPA-Full, SkillOpt, ACE, GEPA + seed, 2 trials | eval only (frozen) | 7 x 417 x 2 = 5,838 cells | about 17 h at 343 cells/h (8 h at 2x workers) | Pooled with test_normal: SE about 1.5 to 1.6; SkillOpt/ACE contrasts power about 0.5 to 0.65. Value is generalization to unseen difficulty and 3.5 x tasks. 1 trial costs 2,919 cells (8.5 h) with SE about 2.5. |
| 8 | More tau2 tasks: another domain (retail/telecom) with new searches for CapEvolve and each comparator | NEW searches | 3 searches x 10 methods ($2k+, weeks) | many days | With 40 tasks and k=3, 9.4 of 10 Holm rejections at observed effect (7.0 at 0.75 effect). Only credible route to settle the close comparators; out of scope of cheap options. |

## 6. Ranking by (significance gained) / cost
1. Plan 0 (free): AppWorld Holm family m=10 (2 to 4 significant), pooled test p=0.0096, optional permutation maxT. No data cost, but state as post hoc.
2. Plan 1 (1,200 rollouts, 30 min, frozen): turns Gate NONE into a clear result, tightens NAIVE. Best significance per rollout.
3. Plan 3 (1,600 rollouts, 40 min, frozen): CapEvolve and baseline at 30 trials; helps every contrast a little and lets the baseline contrast tighten to about +/-0.085. Add to the same job as plan 1; cheap. (Plans 1+2+3 together: about 4,400 rollouts incl. search 1 shared, about 1.9 h.)
4. Plan 2 (2,000 rollouts, 50 min): component ablations to 30 trials. Descriptive tightening; do it only together with plan 1 since search 1 is the shared reference (already included).
5. Plan 5 (3 new CapEvolve searches, ~$350, 17 h): the only fix for the pipeline-level interval; high value for the "not just three lucky artifacts" claim; new searches.
Not worth it: plan 4 (12,400 rollouts for about +1.4 expected rejections), retention (needs several x more tasks and searches), AppWorld more trials (SE floor 2.0 to 2.7), AppWorld policy-only equivalence. Plans 6 and 8 are new searches with poor value per dollar (plan 8 is the structural fix). Plan 7 is worth doing for robustness only if there is time; do not promise significance.

Plan 3/4 expected outcomes are analytic approximations (noise term only, comparator noise unchanged in plan 3), not simulated. Caveats: power uses the observed effect (optimistic); the P/T split relies on 3 searches per arm and is noisy (T ranges from 25 to 63%); trial variance assumes the 10-trial cell variances are homogeneous; AppWorld shares assume a Bernoulli task model and ignore scenario clustering; CIs/posteriors for the gate comparison are for 20 tasks with one NAIVE and one NONE search.
