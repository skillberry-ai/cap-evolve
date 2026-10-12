# What the winning competitors did at search time, and what CapEvolve should adopt

Scope: read-only analysis. Nothing was run, edited or committed besides this file. All numbers are search-time on each method's own selection split (not held-out), so absolute levels are optimistic. The throwaway analysis script is `/tmp/ana_comp.py` (reads the run dirs below; not part of the repo).

Path shorthands: `S` = `/home/dev/projects2/campaign-scratch`, `R` = `/home/dev/projects2/cap-evolve-campaign/research/capevolve-paper`, `A/x` = `R/analysis/out/x`.

## 0. Findings in five lines

1. On Suite A, roughly 0.20 to 0.25 of every competitor's gain is a single, easily found fix: the seed prompt lets Gemma emit `<|tool_call>call:python_interpreter` instead of a fenced python block, which kills 16 to 27% of train rollouts with no output file. Every proposer finds it in its first edit (Meta-Harness hypotheses, `S/runs/E10/metaharness/s{0,1,2}/candidates.jsonl`; GEPA c1 prompt text, `S/runs/E10/gepa/s2/candidates/c1/prompt.md`). After that, Suite A is on a plateau of 0.80 to 0.85 on val-40, within one trial-noise SD (0.048) of each other.
2. The methods that cannot have a selection bias show the same gain as the methods that can. MIPRO (one full-val evaluation, k=1), ACE (k=1 to 2) and Trace2Skill (k=2) gain +0.20, +0.28 and +0.20 over the pooled seed (0.554). GEPA, EvoSkill, SkillOpt and Meta-Harness, with k=4 to 9 and shrinkage applied, gain +0.22 to +0.33. So the multi-candidate machinery adds at most about +0.05 to +0.10 over the first fix.
3. CapEvolve rule-P hill-climb did not lose on proposal quality. Its screened candidates scored 0.85 to 0.90 at best, equal to the competitors. It lost on gating: confirm stages cost about 240 rollouts each, and in A/hc seed 2, 11 of 12 candidates were vetoed for "coverage<0.95" after 3 val tasks hit infra errors (`A/searchtime/summary.md` gate table; `S/runs/E10/hill-climb/s2/.capevolve/run_*/events.jsonl`, event `promotion` with `stage: gate_veto`, screen z=2.23).
4. Suite B and C GEPA "gains" are within the expected max-of-k noise on 25-task and 10-task selection sets (B: +0.15 observed vs +0.13 expected from noise alone; C: +0.18 vs +0.16, with a ceiling at 1.0). They are not evidence of a real effect.
5. Rank for CapEvolve (section 5): (1) gate/infra yield fix (prerequisite, not a competitor mechanism), (2) cheap minibatch kill-screen with failure-focused sampling, (3) cross-trace consolidation of lessons, (4) shrinkage-corrected champion reporting, then Pareto, merge and edit-budget schedules at low value on this evidence.

Two reporting artifacts in `A/searchtime/summary.md` that matter for the paper: ACE's "seed score 0.800 / gain 0.000" is not a seed. ACE never evaluated the seed, so the row labels its first playbook as the seed (`S/runs/E10/ace/s0/candidates.jsonl`, candidate `epoch1_end`). Against the pooled seed its gain is +0.25 (s0) and +0.32 (s1). And GEPA's own seed evaluations are unusually low (0.525, 0.525, 0.425 vs pooled 0.554), which inflates its raw gain from 0.288 to 0.350 by regression to the mean.

## 1. Loop maps and efficiency (task 1)

### 1.1 Per-competitor loop

Sources for the design column: `S/baselines/deviations_{gepa,metaharness,evoskill,skillopt,trace2skill}.json`, `S/baselines/mipro/deviations.json`, `S/baselines/ace/deviations.json`, `S/runs/E10/wikiskill/s0/run_summary.json`. Every competitor uses the same artifact (`prompt.md` + `task_template.md`, except EvoSkill, which edits only an appended skills section), the same Gemma target and the same recalculated hard reward, with a 600-rollout hard cap.

| method | candidates per step | evaluation per candidate | selection / acceptance | what the proposer sees | what was actually done in budget |
|---|---|---|---|---|---|
| GEPA (gepa 0.1.4, `deviations_gepa.json`) | 1 child per step, one component (round-robin over the 2 files) | minibatch of 3 train tasks, parent and child both run (6 rollouts); full val-40 only if the child's minibatch sum strictly beats the parent's | parent sampled from the per-task (instance) Pareto frontier; child enters the pool if the minibatch improved; champion = argmax val mean over pool; no merge (`use_merge=False`) | the 3 minibatch transcripts (<=20k chars each) plus gold-safe scorer feedback, for the one component being edited | 13 to 19 proposals, 9 to 10 fully val-evaluated; own_budget 553 of 600 used (`S/runs/E10/gepa/s0/own_budget.json`); about 65 to 75% of rollouts are full-val evals |
| Meta-Harness (`deviations_metaharness.json`) | 2 per iteration, 4 iterations | 20 train tasks traced (rotating batch) plus val-40 per candidate (60 rollouts) | none; proposer chooses parents freely; champion = best val mean | a Claude Code agent with filesystem access to all prior candidates, their val aggregates and traces; seed traces on all 80 train; no val traces | 8 candidates; k=8 on val |
| EvoSkill (`deviations_evoskill.json`) | 1 skill per iteration | 4 failure-sampled train tasks (2 categories x 2) plus val-40 (44 rollouts) | frontier of 3; parent = best; child kept if it improves | failed transcripts plus a cumulative `feedback_history.md` of earlier proposals and outcomes; skills accumulate in the parent | 6 to 9 children in 332 to 452 rollouts |
| SkillOpt (`deviations_skillopt.json`) | 1 merged edit set per step, 8 steps | 40 train rollouts (analyst minibatches of 8), then val-40 | strict-improvement gate on full val; slow update at epoch end is force-accepted; top-k edits, learning rate 4 cosine to 2 | failure and success patches from analysts, hierarchically merged | 7 to 8 steps, 4 to 5 val evaluations; 3.6 to 5.1M non-cache optimizer tokens |
| Trace2Skill (`deviations_trace2skill.json`) | one-shot: 2 variants (error-only, error+success) | 120 seed rollouts (80 train, 40 val) then val-40 per variant | best of the 2 on val; no iteration | one LLM analyst call per failed trace; patches merged hierarchically (merge batch 5) | 200 rollouts total; k=2 |
| WikiSkill (`S/runs/E10/wikiskill/s0/run_summary.json`) | 1 per iteration, 3 to 4 iterations | all 80 train plus val-40 (120 rollouts) per iteration | accept if val beats incumbent | wiki ingest of the 80 train transcripts | 3 to 4 candidates |
| MIPRO v2 (`mipro/deviations.json`) | 10 to 18 instruction/demo proposals (no rollouts) | 8-task minibatch per TPE trial (30 trials), full val for the top combos | Optuna multivariate TPE; best fully evaluated | bootstrapped demos plus program/data summaries | 1 non-seed full-val evaluation |
| ACE (`ace/deviations.json`) | playbook grows per training sample | 1 epoch over train-80 (generate, reflect, curate), then val-40 | best checkpoint on val; only 1 to 2 checkpoints | reflector tags helpful/harmful bullets; curator edits | no seed evaluation; 1 to 2 val evaluations |

### 1.2 Candidates and gain per 100 rollouts (Suite A, means over 3 seeds)

Computed by `/tmp/ana_comp.py` from `S/runs/E10/*/s*/candidates.jsonl` and `A/searchtime/runs.csv`. "Gen" = candidates generated; "k" = non-seed full val-40 evaluations; "first gain @" = rollout index of the first non-seed full-val evaluation. Gain is measured against the pooled seed mean 0.554 (27 seed evaluations, section 2.1), not each run's own seed evaluation. "EB gain" is the empirical-Bayes shrunk gain (section 2.3). USD is optimizer cost from `runs.csv`.

| arm | rollouts | gen | k | gen/100 | first gain @ | champion | raw gain (own seed) | gain vs pooled | EB gain | EB gain per 100 rollouts | optimizer USD | EB gain per USD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GEPA | 600 | 16.0 | 9.3 | 2.67 | 86 | 0.842 | 0.350 | 0.288 | 0.254 | 0.042 | 1.64 | 0.155 |
| Meta-Harness | 600 | 8.0 | 8 | 1.33 | 221 | 0.917 | 0.308 | 0.363 | 0.330 | 0.055 | 0.79 | 0.418 |
| EvoSkill | 412 | 8.0 | 8 | 1.94 | 85 | 0.842 | 0.292 | 0.288 | 0.244 | 0.059 | 1.94 | 0.126 |
| SkillOpt | 564 | 7.7 | 4.7 | 1.36 | 147 | 0.808 | 0.242 | 0.254 | 0.222 | 0.039 | 9.91 | 0.022 |
| Trace2Skill | 200 | 2.0 | 2 | 1.00 | 160 | 0.750 | 0.233 | 0.196 | 0.175 | 0.088 | 6.76 | 0.026 |
| WikiSkill | 483 | 3.7 | 3.7 | 0.76 | 163 | 0.775 | 0.242 | 0.221 | 0.181 | 0.037 | 1.19 | 0.152 |
| MIPRO | 275 | 13.0 | 1 | 4.73 | 219 | 0.758 | 0.183 | 0.204 | 0.204 | 0.074 | 0.59 | 0.346 |
| ACE | 326 | 0.5 | 1.5 | 0.15 | 233 | 0.838 | n/a (no seed eval) | 0.283 | 0.265 | 0.081 | 6.39 | 0.041 |
| CapEvolve hc, rule P | 600 | 6.7 | 2.7 screens | 1.1 | 160 | best screen 0.875 | 0.091 | n/a | n/a | n/a | 1.20 | n/a |
| CapEvolve hcstock (E12A) | 600 | 12.0 | 12 screens | 2.0 | 160 | best screen 0.900 | 0.319 | 0.313 | n/a | n/a | 2.00 | n/a |

Notes on the table:
- MIPRO and ACE cost the least or gain the most per rollout because they have almost no val selection. MIPRO's 4.7 candidates per 100 rollouts are instruction proposals that never get rollouts, so "candidates per 100 rollouts" is not comparable across methods; the comparable quantity is full-val evaluations per 100 rollouts (GEPA 1.55, Meta-Harness 1.33, EvoSkill 1.94, hcstock 2.0, SkillOpt 0.83).
- Time to first gain separates the designs: EvoSkill 85 and GEPA 86 rollouts (4 or 6 cheap rollouts plus one val-40), against 160 for CapEvolve's hill-climb (80 train baseline traces plus a 40-task screen) and 221 for Meta-Harness (120 seed plus 60 per candidate, 2 candidates per iteration).
- The per-USD ranking reverses the per-rollout ranking: SkillOpt, Trace2Skill and ACE spend 4 to 12 times the optimizer tokens of the others for the same plateau.

## 2. Selection bias (task 2)

### 2.1 Noise model for Suite A

- Pooled seed val-40 score across 27 independent evaluations of the identical seed prompt (GEPA, Meta-Harness, EvoSkill, SkillOpt, Trace2Skill, WikiSkill, MIPRO, hill-climb): mean 0.554, SD 0.045 (values in each arm's `candidates.jsonl` and `A/searchtime/runs.csv`, column `seed_score`).
- Independent estimate from per-task repeats: 9 seed evaluations of the same 40 tasks (`S/runs/E10/{gepa,evoskill,trace2skill}/s*/rollouts_metrics.jsonl`, first val group). Per task, the pass rate is 14 tasks always pass, 8 always fail, 18 mixed. Trial-noise SD of a 40-task mean = sqrt(sum p(1-p) * n/(n-1)) / 40 = sqrt(3.74)/40 = 0.048. The two estimates agree, so I use sigma = 0.047. This is well below the binomial 0.079 because the task set is fixed and 22 of 40 tasks are deterministic.
- Consequence: because every candidate is scored on the same 40 tasks, selection noise here is trial noise (0.048), not task-sampling noise. Task-sampling error cancels in paired gains but not in absolute levels, and the val-to-test shift of the chosen prompt is not measurable until the test cutoff.
- For Suite B (tau2 retail), the E22 null pool gives per-evaluation SD 0.065 at 49 tasks, essentially binomial (0.071) (`A/null_pool_replay.md`). Scaled to 25 tasks, sigma is about 0.091. Six seed evaluations on sel-25 give SD 0.083 (`A/searchtime/summary.md`, seed rows and GEPA seed scores).

### 2.2 Expected max-of-k noise gain

For k candidates with equal true value, E[max noise] = c_k * sigma, with c_k for k = 2, 3, 4, 5, 6, 8, 9, 10 equal to 0.56, 0.85, 1.03, 1.16, 1.27, 1.42, 1.49, 1.54. This is the upper bound on the selection bias: it is reached only if all k candidates are truly equal.

| arm | k | upper bound on selection bias (c_k * 0.045) |
|---|---|---|
| GEPA | 9 to 10 | 0.067 to 0.069 |
| Meta-Harness | 8 | 0.064 |
| EvoSkill | 6 to 9 | 0.057 to 0.067 |
| SkillOpt | 4 to 5 | 0.046 to 0.052 |
| WikiSkill | 3 to 4 | 0.038 to 0.046 |
| Trace2Skill | 2 | 0.025 |
| MIPRO, ACE | 1 to 2 | 0 to 0.025 |

### 2.3 Empirical-Bayes shrinkage (the central estimate)

Per run, take the non-seed full-val scores x_j, their mean m and variance v, and shrink the champion by B = max(0, (v - sigma^2)/v): EB = m + B * (champion - m). When the observed spread is smaller than noise (EvoSkill s0, s2; GEPA s2; WikiSkill s1, s2; Trace2Skill), B = 0 and EB = m, which is conservative. Lineage correlation between parent and child makes the true candidate spread smaller than the observed one, so this slightly over-shrinks.

Result, gain over pooled seed 0.554 (full per-run rows are printed by `/tmp/ana_comp.py`):

| arm | raw champion gain vs own seed | champion vs pooled seed | minus max-of-k bound | EB-shrunk |
|---|---|---|---|---|
| GEPA | +0.350 | +0.288 | +0.220 | +0.254 |
| Meta-Harness | +0.308 | +0.363 | +0.299 | +0.330 |
| EvoSkill | +0.292 | +0.288 | +0.224 | +0.244 |
| SkillOpt | +0.242 | +0.254 | +0.204 | +0.222 |
| Trace2Skill | +0.233 | +0.196 | +0.171 | +0.175 |
| WikiSkill | +0.242 | +0.221 | +0.177 | +0.181 |
| MIPRO | +0.183 | +0.204 | +0.204 | +0.204 |
| ACE | n/a | +0.283 | +0.271 | +0.265 |

Which gains are likely real:
- Real on val, about +0.18 to +0.33. The ordering of competitors after shrinkage is not resolvable: with 3 seeds and sigma 0.048, the SE of a 3-seed mean gain is about 0.03 to 0.04, and the spread between arms (0.175 to 0.33) is mostly Meta-Harness being high.
- Meta-Harness is the one with visible winner's curse. Its proposer saw each candidate's val aggregate and selected parents on it. In s0, `example_calibration` scored 0.975 while its own children scored 0.85 to 0.875 (`S/runs/E10/metaharness/s0/candidates.jsonl`), so EB lowers it from 0.975 to 0.924. Its 0.917 mean champion is the least trustworthy absolute level.
- Low-k methods are the cleanest evidence. MIPRO's champion is chosen by TPE on 8-task minibatches and then scored once on val, so its val score is an unselected estimate: +0.20 (s0), +0.30 (s1), +0.05 (s2), mean +0.18 to +0.20, with SE about 0.07 per run. ACE's playbook is +0.25 and +0.32 unselected. These match the multi-candidate methods after shrinkage.
- Plateau check. In E12A hcstock (`S/runs/E12A/hcstock/s{0,1,2}/.capevolve/run_*/candidates.jsonl`), the children of the best parent score 0.835, 0.858, 0.850 on average against parent scores 0.85, 0.875, 0.875. Children do not beat the parent on average, and the best child of 12 (0.875, 0.925, 0.90) is again about a max-of-k draw above the plateau. GEPA lineages show the same: after c1 or c2, children score 0.65 to 0.875 around a mean of 0.76 to 0.82.

Therefore: the first accepted edit is worth about +0.20 to +0.25; everything after it, on this model and benchmark, is worth at most +0.05 to +0.10 and is of the same size as the selection bias. This also means Suite A cannot distinguish search algorithms by search-time gain, only by cost to the plateau.

### 2.4 Suite B and C GEPA

- Suite B, GEPA on sel-25: champions 0.76, 0.76, 0.72 vs the sel-25 seed arm 0.60 (`A/searchtime/summary.md`; candidate lists in `S/runs/E10B/gepa/s*/candidates.jsonl`). Observed gain +0.147 (mean). Expected max-of-k noise with k = 8 to 9 and sigma 0.09: 1.42 to 1.49 x 0.09 = +0.13. The residual is about +0.02, well inside noise. GEPA scores in the pool wander from 0.40 to 0.76 around the seed (s1: 0.40, 0.40, 0.52, 0.60, 0.60, 0.64, 0.68, 0.76, 0.52, 0.56).
- Suite C, GEPA on sel-10: champions 1.0 in all three seeds from seed scores 0.8, 0.8, 0.9. With 10 tasks, sigma is about 0.11 and 6 to 10 evaluations per run reach 10/10 by luck with high probability (a p=0.9 prompt hits 10/10 with probability 0.35 per evaluation). Observed +0.18 vs expected noise +0.16. Not evidence.
- E20 shows the same selection-split effect inside one suite (`A/searchtime/summary.md`, rows D): E20-GEPA on sel-25 gains 0.04, 0.24, 0.12; E20-P on opt-49 gains 0.30, 0.13, 0.13. No ordering, and the splits differ.
- Statement for the paper: "only GEPA gained on Suite B" is a statement about which arm picks the best of about 9 noisy evaluations on a 25-task selection set. The summary's own caveat already forbids ranking across methods on these numbers.

## 3. Why rule-P hill-climb looked weak on Suite A

- Its proposals were as good as the competitors'. Best screened candidate per seed: 0.875, 0.85, 0.90 (A/hc), versus hcstock 0.875, 0.925, 0.90 and GEPA 0.85, 0.875, 0.80 (`S/runs/E10/hill-climb/s*/.capevolve/run_*/candidates.jsonl`; E12A candidates files).
- Cost. Screen = 40 rollouts, confirm = n_conf 3 x 2 arms x 40 = 240 rollouts, so a single promoted-then-confirmed candidate used 280 of 600 rollouts; hc seed 0 used 4 candidates, seed 1 used 2 (`A/searchtime/summary.md`, gate table). Time to first gain is 160 for hill-climb versus 85 for EvoSkill and GEPA.
- Infra vetoes. `baseline_incomplete` 37 of 40 tasks scored in s2, so every later screen had coverage 0.925 < min_coverage 0.95 and was declared indecisive even where the screen had z = 2.23 (event `promotion` / `gate_veto` in the s2 `events.jsonl`). 43 of 520 val rollouts and 5 of 80 train rollouts in s2 are `error_kind: infra` (`rollouts_metrics.jsonl`). Competitors' adapters retried infra errors and refunded them (`S/runs/E10/gepa/s0/own_budget.json`: `infra_retries_refunded: 9`).
- The paper-relevant consequence: the A/hc 0.171 / 0.103 / 0.000 line measures gate and infra handling, not the proposer. Stock gate at about +0.3 (hcstock, `A/searchtime/summary.md`) is the same as GEPA's raw gain (+0.35) and above its EB gain (+0.25).

## 4. Candidate mechanisms and how they fit CapEvolve (task 3)

Constraint kept throughout: nothing below names a benchmark, a file or a failure class; everything operates on per-task reward vectors, trajectories and capability files that the framework already exposes. Existing CapEvolve code that already implements the competitor mechanism is listed, because for several the work is turning it on in the default path, not writing it. I have not verified which of these modules the default hill-climb path calls; that needs a code check by whoever implements.

### 4.1 Minibatch evaluation with reflective mutation

- Competitor evidence: GEPA's pre-filter costs 6 rollouts per proposal and found its first good candidate at rollout 86. EvoSkill spends 4 failure-sampled rollouts per proposal (first gain at 85). Both reach 0.72 to 0.80 on val at the first evaluation (`S/runs/E10/gepa/s*/candidates.jsonl`, `S/runs/E10/evoskill/s*/candidates.jsonl`).
- Limits of the evidence: it buys time-to-first-gain, not a higher plateau. GEPA's 3-task minibatch with strict improvement on a sum passes 47% to 77% of proposals (9/19, 10/13, 9/16 per the summary), so the filter is weak; most of its power comes from the later full-val gate.
- Fit: CapEvolve already has `cap_evolve/subsample.py` (variance-aware kill-only screen on a val subset) and `cap_evolve/gepa.py` (minibatch, reflective dataset, round-robin component focus, eval cache, budget). The surface-agnostic form is: parent and child are run on the same small task subset (tasks drawn from currently failing plus a random holdout of passing, as `select_screen_subset` already does); the subset may kill, never accept; acceptance remains the full-val paired gate. No benchmark-specific input.
- Needed change: make the kill-screen part of the default hill-climb ladder and charge it to the same rollout budget. `core/tests/test_round_requires_screen_ladder.py` suggests the screen ladder is already required for some path; confirm which.

### 4.2 Pareto front over tasks

- Competitor evidence: only GEPA uses it, and its merge was disabled in the campaign (`deviations_gepa.json`: `use_merge=False`). Parents in GEPA s0 were c0, c1, c0, c1, c2, c2, c5, c4, c7: the frontier re-selects the seed for new branches, which helps exploration but did not produce a better champion than a single lineage in these runs.
- Headroom check for complementarity: the union of two candidates' per-task passes exceeds the single-candidate mean by 0.07 to 0.10 (GEPA 0.068 to 0.075; EvoSkill 0.070 to 0.100; `S/runs/E10/{gepa,evoskill}/s*/rollouts_metrics.jsonl`, val groups with >=36 tasks). Pure trial noise predicts sum p(1-p)/40 = 0.081 to 0.094 for the union of two evaluations of one prompt. Observed complementarity is no larger than noise would give, so there is no demonstrated specialist structure on Suite A. This is weak evidence (GEPA's rollout files give only 2 to 6 complete val groups per run).
- Fit: `cap_evolve/pareto_archive.py` and `selection.py` (`pareto_per_instance` picker) exist. It is surface-agnostic by construction, since it works on per-task reward vectors.

### 4.3 Merging

- Competitor evidence: Trace2Skill and SkillOpt merge patches (hierarchical merge of per-trace or per-minibatch patches), which is merging of edits, not of candidates; GEPA's candidate merge was off. No competitor evidence for candidate merge exists in this campaign.
- Fit: edit-level merge (many small localized patches into one edit) is the relevant form and is part of 4.5. Candidate merge needs two candidates edited in disjoint regions and a conflict check, which CapEvolve's `footprint.py` partly provides. Defer.

### 4.4 Skill or playbook accumulation

- Competitor evidence: EvoSkill (skills accumulate in the parent; cumulative `feedback_history.md`), ACE (playbook with helpful/harmful counters, one epoch, gain +0.25 and +0.32 with no val selection), WikiSkill. ACE shows accumulation alone reaches the plateau band (0.80 to 0.875) in 196 to 238 rollouts, but the cost is high (about $6.4) and ACE's second checkpoint was lower than the first in s0 (0.725 vs 0.80; `S/runs/E10/ace/s0/candidates.jsonl`), so more accumulation is not monotone.
- Fit: CapEvolve already carries cross-iteration state (`memory.py` rejected memory and history; LEDGER.md and JOURNAL.md injected by `harness._augment_instructions`). A benchmark-agnostic version is a structured, bounded "lessons ledger" with per-lesson helpful/harmful counts updated from per-task outcomes (ACE's counters need only task-level pass/fail), shown to the proposer and pruned when counts turn harmful. Edit surfaces already listed in `A/searchtime/summary.md` ("skill_files", "process_docs", "reference") are where it would live.

### 4.5 Cross-trace consolidation (Trace2Skill pattern)

- Competitor evidence: highest EB gain per 100 rollouts (0.088 vs 0.037 to 0.059 for the loops) with zero iterations: one analyst call per failed trace, then a hierarchical merge into one patch, evaluated once. Its candidates scored 0.70, 0.725, 0.725 (error) and 0.675, 0.80, 0.75 (combined) with no val loop. Cost per USD is poor (about $6.8, 2.1M non-cache tokens), but the cost is optimizer tokens, not rollouts, and rollouts are the scarce resource in the campaign.
- Fit: as a candidate generator inside CapEvolve's proposer, not a new algorithm: N independent single-trace analyses (parallelizable, cheap model) produce small patches, a merge step deduplicates and picks the patches supported by multiple traces, and the result is one candidate screened by the normal gate. It is surface-agnostic because it consumes trajectories and emits a diff to whatever files the capability declares. It also addresses CapEvolve's own instruction ("diagnose EVERY failure cluster", `S/runs/E10/hill-climb/s0/project/optimizer/INSTRUCTIONS.md`) in a way that does not rely on one long agent context.

### 4.6 Curriculum / failure-focused sampling

- Competitor evidence: EvoSkill samples only failures (2 categories x 2 tasks); GEPA's `skip_perfect_score` and epoch-shuffled batches; Meta-Harness rotates 20-task train batches. All three reached 0.80 to 0.875. Hill-climb's feedback comes from one up-front 80-task train trace (80 of 600 rollouts); I did not verify which split its later iterations read (`harness._copy_step_trajectories` copies the parent's per-tag rollouts for `split`).
- Fit: sampling policy for the cheap train-side evaluation: sample tasks the parent fails or is unstable on (from per-task reward history the framework already stores in `eval_index.jsonl`), plus a small random holdout of passes (as in `subsample.select_screen_subset`), so regressions are visible. No benchmark knowledge required.

### 4.7 Other competitor features, for completeness

- Textual learning rate (SkillOpt, `lr_schedule.py` already exists): SkillOpt has the lowest EB gain per 100 rollouts of the iterative loops (0.039) at the highest cost ($9.91). No evidence that an edit budget helps.
- MIPRO-style instruction/demo search: demos are benchmark-shaped (here, worked examples), and its gain comes from a single full-val evaluation; the TPE stage on 8-task minibatches spends 240 rollouts and ends at +0.05 to +0.30. No transferable mechanism beyond "evaluate many, full-evaluate one", which is equivalent to 4.1 with k=1.

## 5. Ranking by expected value for CapEvolve (task 4)

Expected value = (plausible gain on the paper's metric) x (strength of evidence here) / (implementation and rollout cost). "Gain" means search-time gain on plateau-limited tasks like Suite A, and rollouts saved on others.

| rank | item | evidence in this repo | expected effect | cost / risk |
|---|---|---|---|---|
| 0 (prerequisite) | Gate yield: treat infra-missing tasks as missing-at-random (paired delta on the intersection, retry and refund lost rollouts) instead of vetoing; reduce confirm cost | A/hc s2: 11 of 12 candidates vetoed, best screen 0.90; A/hc s0 and s1 spent 280 of 600 rollouts on one confirm; `summary.md` gate table; `events.jsonl` `gate_veto` | recovers about +0.2 to +0.3 on seeds that currently return the seed; no change to competitors | low code cost; touches honesty-critical gate, so needs the null-pool replay (`A/null_pool_replay.md`) re-run to confirm the false-accept rate is unchanged |
| 1 | Minibatch kill-screen plus failure-focused sampling, in the default hill-climb ladder (4.1 + 4.6) | GEPA/EvoSkill first gain at 85 to 86 rollouts vs 160 (hcstock, hc) and 221 (Meta-Harness); screens in hcstock cost 40 rollouts per candidate where a 6-rollout kill-screen would cost 15% as much | 2 to 4x more proposals per rollout; same plateau on A, plausible gain on harder suites; cannot raise a plateau by itself | low; modules exist (`subsample.py`, `gepa.py`); weak 3-task filters pass 47 to 77%, so use the variance-aware subset, not a bare sum |
| 2 | Cross-trace consolidation as a proposer mode (4.5) | Trace2Skill: best EB gain per 100 rollouts (0.088), fixed protocol failure in one shot at 200 rollouts total; EvoSkill and GEPA reach the same band in 330 to 600 | reaches the first-fix band in about a third of the rollouts | medium; extra optimizer tokens ($6.8 for Trace2Skill; use a cheaper analyst); gain is a one-step gain, not shown to continue |
| 3 | Shrinkage-corrected champion reporting and re-evaluation of the returned champion (not a competitor feature) | Meta-Harness 0.975 vs its children 0.85 to 0.875; GEPA seed score 0.425 inflating raw gain by 0.06; max-of-k bounds 0.05 to 0.07 | keeps the paper from reporting winner's-curse levels; makes cross-method search-time numbers comparable | low; one analysis script plus a final re-evaluation of the champion and seed under the same trials |
| 4 | Lessons ledger with helpful/harmful counts (4.4) | ACE +0.25 to +0.32 unselected, but non-monotone and costly | modest; mostly stops the proposer from repeating rejected ideas, which CapEvolve's LEDGER/JOURNAL partly does | medium |
| 5 | Per-task Pareto parent selection, candidate merge (4.2, 4.3) | no demonstrated complementarity beyond noise on A (union gain 0.07 to 0.10 vs noise-only 0.08 to 0.09); merge was off in GEPA | unknown; matters only when candidates specialize | implemented already; run as an ablation, not a default |
| 6 | Textual learning-rate / edit budget (SkillOpt) | lowest EB gain per 100 rollouts and per USD of any loop | none shown | implemented already; keep off |

Two things that this evidence cannot settle:
- Whether any of 1 to 5 raises the plateau. All eight competitors plus hcstock sit at 0.80 to 0.85 on val-40 after the protocol fix, and the 8 always-fail tasks (20% of val) cap it near 0.80 to 0.90 for this model. Differences above the plateau need either a harder suite or the held-out test; Suite B and C are noise-dominated at their selection-set sizes.
- Generalization of any search-time gain. Everything here is selection-split; the test split is not evaluated until the cutoff. Prompt edits that fix a format bug generalize; Meta-Harness's val-driven parent choice and GEPA's 9-way val argmax are the two places where val overfit is most plausible.

## 6. Reproduction pointers

- Per-run numbers behind sections 1.2 to 2.3: `python3 /tmp/ana_comp.py` (reads `S/runs/E10/{gepa,metaharness,evoskill,skillopt,trace2skill,wikiskill,mipro,ace}/s{0,1,2}/candidates.jsonl`, `S/runs/E12A/hcstock/s*/.capevolve/run_*/candidates.jsonl`, `S/runs/E10/hill-climb/s*/.capevolve/run_*/candidates.jsonl`, `A/searchtime/runs.csv`).
- Seed-noise estimate (section 2.1): first val group of `rollouts_metrics.jsonl` in gepa, evoskill and trace2skill, 9 seed evaluations, 40 tasks.
- Union-of-candidates check (4.2): val groups with at least 36 scored tasks in `rollouts_metrics.jsonl` for gepa and evoskill. GEPA's files contain only 2 to 6 complete groups per run (fewer than the candidate count), so treat it as indicative.
- Protocol-failure evidence: `hypothesis` field of the first Meta-Harness candidates (13/80, 22/80 and about 13/80 train tasks with no output file); `S/runs/E10/{skillopt/s1/candidates/step_0001,trace2skill/s0/candidates_frozen/error,evoskill/s0/candidates/iter-skill-1,wikiskill/s0/candidates/it001}/prompt.md` all contain the fence/tool-call rule.
