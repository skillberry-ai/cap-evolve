# CapEvolve gate and evaluation-budget design

Author: statistician/systems role. Read-only analysis: no running process touched, no repo code edited, nothing committed.
Simulation code and raw outputs sit next to this file (`gate_budget_sim.py`, `null_p.json`, `gate_budget_{single,multi,sweeps,sweeps2,merge,merge2}.json`). Reproduce: `python3 -I gate_budget_sim.py single|multi|sweeps|sweeps2|merge|merge2` (about 5 min on 60 cores, pure stdlib, imports the real `cap_evolve.promotion`).

## 0. Bottom line

1. At 49 tasks and 1 trial per task the paired SE is 0.077. The stock gate cannot tell a +0.10 edit from noise reliably, and rule P can resolve it only at 221 rollouts per candidate. No design can beat this by cleverness. The savings come from (a) stop re-measuring the incumbent for every decision (pooled incumbent), (b) stop spending confirmation rollouts on candidates a 12 to 36 rollout screen already shows to be losers, (c) put the efficacy claim on tasks the proposer never saw.
2. Recommended policy ("SH-C"): parallel rounds of K candidates. Rungs 1 and 2 are kill-only successive halving on a random 12 then 36-task-rollout subset of the feedback stratum F. Survivors get one fresh confirmation on a hidden confirm stratum C, against a concurrently measured incumbent control. At matched round false-accept rate (about 0.10) it needs about 550 rollouts per round of 8 against 990 for rule P as run, and about 1,000 rollouts per true champion against 1,640. It is also drift-robust and overfit-robust, which the stock gate and a naive merged pool are not.
3. The coverage veto that blocked 18 screen-passing candidates is an incumbent-side artefact (three seed tasks with `valid_trials=0`, never retried). Fix: retry then quarantine incumbent-side missing tasks, measure coverage on the evaluable set, replace the 0.95 veto with a tipping-point check, classify candidate-code faults as failures (framework-level traceback attribution, not only adapter tags).
4. Merging train and val into one gated pool is the wrong default: with a modest seen-task memorisation boost (rho = 0.10, worth +0.044 on seen tasks) a naive merged gate has round FWER 0.53 instead of 0.10. A hidden confirm stratum (F25/C24 on the 49-task pool) costs nothing in power and restores 0.11 to 0.13.
5. Do not change the frozen campaign arms. Everything below is opt-in (`promotion_rule: SH`) and for the product and the next paper revision.

## 1. Calibrated model and assumptions

Data: `null_pool_replay.md` pool, re-read from `campaign-scratch/runs/E22-null/chunk*.out`: 40 evaluations of the unmodified seed, 49 tasks, binary rewards (1,100 pass, 850 fail, 10 errored).

| item | value | source |
|---|---|---|
| task success p_i | empirical task means: 5 tasks at 1.0, 3 at 0.03, median about 0.5 | pool |
| mean p, E[p(1-p)] = V | 0.563, 0.147 | pool |
| eval-mean SD | 0.065 observed vs 0.071 binomial | `null_pool_replay.md` |
| one rollout paired delta SD | sqrt(2V) = 0.54, so SE(49 tasks, 1 trial each side) = 0.077 | derived |

Assumptions (each one is a way the simulation can be wrong):
- A1. Rollouts are independent Bernoulli(q_i) given the task. Supported by 0.065 vs 0.071; the SD says no detectable shared per-evaluation noise. Not supported: drift (first half 0.548, second half 0.580, +0.032, t about 1.5). Handled as an explicit scenario (section 3.3).
- A2. Candidate effect is diffuse: q = p + d*w/mean(w), w = 1-p for d>0, w = p for d<0 (same as `sim_common.apply_edit`). Sparse edits (a few tasks carry the effect) have lower power for every design equally; not re-run.
- A3. The incumbent estimate is `phat` = mean of m fresh trials per task, drawn once per incumbent and shared by every candidate of a round (so errors are correlated across candidates, as in reality). "Pooled incumbent" means m=4 fresh trials per task, 196 rollouts once per incumbent change, excluded from the per-decision costs below and charged once.
- A4. SE for the sequential designs is model-based, SE^2 = V*(1/n + sum_t j_t^2 / (m n^2)), where j_t is the number of candidate rollouts on task t. This keeps the incumbent's noise from being averaged away by repeated passes (a naive per-rollout sample SD understates SE by about 20% at n=147). In production V should be the pooled within-task Bernoulli variance of the run's own rollouts.
- A5. Stock and rule P replay the real `promotion.screen/confirm/paired_stats` code, 1 trial vs 1 trial screen.
- A6. Effect mixture for multi-candidate rounds: 55% null, 15% harmful (-0.05), 30% beneficial U(0.04, 0.14). "Good champion" means true effect at least 0.04.
- A7. The simulation is slightly more optimistic about false accepts than the pool: stock 0.158 vs pool 0.184 (pool interval 0.11 to 0.24, so inside), rule P as run 0.016 vs 0.026 (pool interval 0.008 to 0.046), frozen 0.005 vs 0.008, n_conf10 0.008 vs 0.016. All matched-FA comparisons below calibrate to the simulated rule-P-as-run rate (per candidate 0.018, round of 8: 0.113), not to the pool's, so they are internally consistent.

## 2. Task 1: power curves

### 2.1 Single candidate, one decision (false accept at effect 0 and negative; false reject = 1 - accept at positive effect)

Probability of accepting, by true effect. "Matched" rows have their threshold bisected so that FA at effect 0 is 0.018 (rule P as run in this simulation).

| design | param | -0.05 | 0 | +0.03 | +0.05 | +0.08 | +0.10 | +0.15 | +0.20 | E rollouts at 0 | at +0.10 | looks at +0.10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stock (paired k=1, 49 roll.) | not matched | 0.051 | 0.158 | 0.263 | 0.349 | 0.487 | 0.584 | 0.794 | 0.928 | 49 | 49 | 1.0 |
| rule P as run (n_conf3 z1.282 dmin0) | | 0.000 | 0.016 | 0.071 | 0.146 | 0.327 | 0.472 | 0.767 | 0.925 | 95 | 221 | 1.6 |
| rule P frozen (z2.0 dmin.02) | | 0.000 | 0.005 | 0.025 | 0.066 | 0.191 | 0.322 | 0.691 | 0.914 | 95 | 221 | 1.6 |
| rule P n_conf10 z1.645 dmin.02 | | 0.000 | 0.008 | 0.090 | 0.219 | 0.454 | 0.579 | 0.796 | 0.931 | 202 | 624 | 1.6 |
| fixed n=98, pooled incumbent m=4 | z>=2.04 | 0.001 | 0.022 | 0.091 | 0.178 | 0.385 | 0.544 | 0.873 | 0.986 | 98 | 98 | 1 |
| group-sequential (looks 12/24/49/98/147, OBF + futility) | c=2.03 | 0.001 | 0.018 | 0.084 | 0.172 | 0.395 | 0.558 | 0.859 | 0.962 | 53 | 100 | 3.9 |
| SPRT (d1=0.10, beta=0.2, 6-roll. looks, cap 147) | A=3.19 | 0.001 | 0.017 | 0.075 | 0.162 | 0.366 | 0.536 | 0.877 | 0.986 | 64 | 93 | 15 |
| Bayes sequential (prior N(0,.05^2), P(d>.02)>=p*) | p*=0.898 | 0.001 | 0.019 | 0.082 | 0.165 | 0.387 | 0.556 | 0.894 | 0.992 | 140 | 107 | 18 |
| Hoeffding race, nominal alpha .05, cap 147 | | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 144 | 144 | 24 |
| empirical-Bernstein race, nominal alpha .05 | | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 144 | 144 | 24 |

Reading:
- Stock is not "powerful"; it buys its power with a 16% false accept rate (about 5% of harmful candidates also pass). At matched FA (0.018) the best designs reach 0.55 at +0.10 and 0.86 to 0.89 at +0.15.
- Pooling the incumbent is the single biggest efficiency lever: fixed n=98 matches rule P's FA with 98 instead of 221 rollouts at +0.10 and 0.54 vs 0.47 power; at +0.15, 0.87 vs 0.77.
- Group-sequential halves the cost again at the null (53 vs 98 rollouts) with identical power (0.558 at +0.10, 100 rollouts). SPRT and Bayes sequential are equivalent in power but need 15 to 18 sequential looks, which is bad for wall-clock; GS with 4 looks is the practical choice.
- Hoeffding and empirical-Bernstein races never decide within 147 rollouts. Hoeffding on d in [-1,1] needs radius below the effect: n >= 27/d^2 with the stitched union bound, about 2,700 rollouts for +0.10. Empirical Bernstein needs about 800 to 900. Not usable at the campaign's budgets; the variance-based boundaries above are the same idea with the right scale.
- Resolution limit, regardless of design: SE at 147 rollouts with m=4 is 0.042. Detecting +0.05 with 80% power at FA 0.018 needs about 650 rollouts per candidate. At budgets of 550 to 600 total, effects below +0.10 are not individually decidable; accumulating them via many accepted small gains is not supported by the data.

### 2.2 Rounds of K=8 candidates, one champion per round (shared incumbent)

All rows except "stock" are calibrated to the same round FWER (rule P as run: 0.113). Mixed rows use A6.

| policy | round FWER (all-null) | P(champion is good) | P(champion null or harmful), mixed | E true gain per round | E apparent minus true (winner's curse) | rollouts per round | rollouts per good champion | sequential stages |
|---|---|---|---|---|---|---|---|---|
| stock x8 | 0.500 | 0.641 | 0.114 | +0.066 | +0.077 | 392 | 612 | 1 |
| rule P as run x8 | 0.113 | 0.603 | 0.022 | +0.065 | +0.027 | 990 | 1,640 | 2 |
| group-sequential x8 (per candidate) | 0.108 | 0.667 | 0.020 | +0.072 | +0.046 | 499 | 748 | 4.8 |
| successive halving 8>4>2 + fresh confirm (zc 1.51) | 0.098 | 0.592 | 0.022 | +0.063 | +0.029 | 358 | 606 | 4 |
| Thompson allocation (budget 300) + fresh confirm (zc 1.18) | 0.120 | 0.626 | 0.023 | +0.067 | +0.017 | 380 | 607 | 9.9 |
| Hoeffding race | 0 | 0 | 0 | 0 | n/a | 1,152 | inf | 24 |

Reading:
- At equal round FWER, successive halving and Thompson cost 2.7x fewer rollouts per good champion than rule P with about the same quality (0.59 to 0.63 vs 0.60). Group-sequential is the quality leader (0.667) at 1.3x the cost of SH.
- Thompson buys nothing over SH here (same cost, 10 stages vs 4) and needs a prior; reject for wall-clock.
- Stock x8 looks cheap only because half of all null rounds crown a null candidate (FWER 0.50) and 11% of mixed rounds crown a null or harmful one. Its "rollouts per good champion" is not comparable.
- Winner's curse (apparent gain of the crowned candidate over its true effect): stock +0.077, GS +0.046 (the stopping-time bias of using the screening data), rule P and SH +0.03 (max over a few fresh confirmations), Thompson +0.017.

### 2.3 Sensitivity of SH to its knobs (zc recalibrated each time; round FWER 0.09 to 0.13)

| variant | P(good champion) | rollouts/round | rollouts per good |
|---|---|---|---|
| incumbent trials m = 1 / 2 / 4 / 8 | 0.39 / 0.50 / 0.59 / 0.66 | 327 / 346 / 358 / 364 | 846 / 687 / 604 / 550 |
| rung 1 = 12 / 16 / 24 tasks | 0.59 / 0.61 / 0.64 | 358 / 393 / 459 | 604 / 649 / 712 |
| confirm n = 49 / 98 / 147 / 196 | 0.51 / 0.59 / 0.64 / 0.67 | 269 / 358 / 448 / 538 | 526 / 604 / 698 / 799 |

m=4 and n_conf=98 to 147 sit at the knee. m=1 (what the stock gate effectively does) loses a third of the power.

### 2.4 Time drift (a +0.03 platform shift between the incumbent's measurement and a later candidate; the pool shows +0.032 across halves)

| confirmation uses | drift | round FWER | P(good champion) | rollouts/round |
|---|---|---|---|---|
| historical pooled incumbent | 0 | 0.098 | 0.59 | 358 |
| historical pooled incumbent | +0.03 | 0.30 | 0.71 | 366 |
| historical pooled incumbent | +0.05 | 0.48 | 0.74 | n/a |
| concurrent control, 2 trials/task (+98 rollouts) | +0.03 | 0.099 | 0.52 | 472 |
| concurrent control, 2 trials/task | +0.05 | 0.105 | 0.53 | n/a |
| concurrent control 3 trials/task, n_conf=147 | +0.03 | 0.098 | 0.61 | 617 |

A pooled historical incumbent triples the false accept rate under a drift the data already show. Pooling is valid for ranking (rungs 1, 2) and invalid for the efficacy claim; the claim needs a concurrent control. This is why rule P re-measures the incumbent at confirmation, and why the recommended design keeps that, at 96 rollouts instead of 147.

## 3. Task 2: evaluation-budget policy (hill-climb and agent-optimize)

### 3.1 Policy "SH-C" (one policy, two drivers)

State per run: pool split into feedback stratum F and confirm stratum C (section 5). Incumbent baseline on F: 4 fresh trials per task (e.g. 100 rollouts at |F|=25) for ranking only; replaced whenever the incumbent changes (it is the previous confirmation's F-side data if available).

Round of K candidates (K = 8; K = 6 when total budget is at most 600):
1. Rung 1. Each candidate: 12 rollouts, one per task, on a random 12-subset of F (same subset for all candidates and the incumbent baseline). Kill-only. Keep the top K/2 by paired z with mean > 0. Cost 12K = 96.
2. Rung 2. Survivors: 24 more rollouts, on F tasks not yet used where possible. Keep the top K/4 (at least 1) with cumulative mean > 0. Cost 24 * K/2 = 96. Rungs never accept.
3. Control. Once per round, if any survivor exists: measure the incumbent concurrently on C, 4 trials per task (96 rollouts at |C|=24).
4. Confirmation. Each survivor: 147 fresh-seed rollouts on C (6 trials per task at |C|=24), none of the rung data reused. Accept the one with the best paired mean among those with z >= 1.5 (one-sided alpha 0.067 per test, at most 2 tests per round, round FWER about 0.09 to 0.13 as simulated). dmin = 0.02 on the confirm mean.
5. If nothing survives rung 2 or passes, the round is a no-op and costs only rungs 1 and 2 (192 rollouts).
6. K=1 (one candidate pending, hill-climb serial mode): use group-sequential with looks at 12, 24, 49, 98, 147, boundary 2.03*sqrt(147/n) on z, futility at z < -0.5, 0, 0.3, 0.7 after looks 1 to 4 (section 2.1). This needs the same hidden C-confirmation for its final look in the F/C design.

Agent-optimize uses the same rungs, driven by the framework: the agent proposes workdirs and calls one framework tool (`evaluate_rung`, a successor to `screen.py` and `gate_check.py`) that enforces the rung budgets, returns only `kill|advance|accept|unconfirmed` plus aggregate numbers on F, and never returns C task traces or ids. `subsample.screen_decision` is already kill-only; its "bias toward promote" is replaced by the halving rule above.

### 3.2 Simulated effect on the three quantities requested (K=8, mixed rounds, matched round FWER about 0.10)

Variant simulated: F25/C24, 147 confirmation rollouts, concurrent control m=4, zc 1.49, rho 0.10 and drift 0.03 (`gate_budget_merge2.json`).

| quantity | rule P as run | SH-C (recommended) | change |
|---|---|---|---|
| rollouts per round of 8 | 990 | 532 to 576 | -42% to -46% |
| rollouts per good champion | 1,640 | about 1,000 | -39% |
| rollouts per decision of any kind | 124 per candidate | about 70 per candidate | -44% |
| round FWER (all null) | 0.113 | 0.093 to 0.127 | same by calibration |
| P(champion good) | 0.603 | 0.556 to 0.561 | -4 points |
| P(champion null or harmful) | 0.022 | 0.019 to 0.029 | same |
| winner's curse, apparent minus true | +0.027 | +0.030 | same; remove by a final re-measure (section 5.4) |
| robust to +0.03 drift | yes | yes (control) | |
| robust to rho = 0.10 memorisation | no (confirms on seen tasks) | yes | |
| sequential stages | 2 | 4 | +2 |

If the control and n_conf are raised to 196 and m=4 (cost 618 to 672 per round), P(good) reaches 0.58 to 0.59 and rollouts per good champion about 1,100, still 33% below rule P.

Wall-clock. On Suite B the stage latency is dominated by throughput, not parallelism: the observed evaluations were 49 rollouts in 5,300 to 8,200 s (E10B hc s0: seed 5,300, cand_0001 5,472, cand_0002 6,392, cand_0003 8,239), and a 147-rollout confirmation took 28,600 to 31,200 s per side. A rule-P confirmation of one candidate therefore cost about 16 h of a roughly 30 h search. At about 21 to 33 rollouts per hour, a round of 8 costs about 30 to 47 h under rule P as run (990 rollouts) versus 16 to 27 h under SH-C (530 to 580). Parallelising across candidates helps only until the endpoint's rate ceiling (the decisions log notes about 116 calls/min); beyond that, wall-clock is proportional to rollouts, and the 42 to 46% saving carries over directly. The two extra sequential stages add at most 2 stage-latencies (the 12-rollout rung is about one 10-minute rollout when workers are free).

False accepts: unchanged by calibration at about 0.10 per round (about 0.013 per candidate), against 0.50 for stock. Calibrating to a stricter target is a knob (zc), not a redesign.

Tradeoff to state honestly: SH-C finds a good champion 4 points less often than rule P per round, because the halving rungs also kill some small true gains (effects around +0.04 look like noise at 12 to 36 rollouts). It finds it with 44% fewer rollouts, so per unit budget it finds more.

### 3.3 Budget check per evaluation call (all drivers)

Today the budget is read only at iteration boundaries (`harness.py:4638`, `gepa.py:545`, `skillopt.py:272`), and `update_spent(metric_calls=...)` is called after the rollouts finish (`harness.py:668`). Confirmation (2 x 147 on B) is charged after it ran. Evidence: Suite B hc used 637, 564, 637 rollouts against a 550 budget (`searchtime/summary.md`), +16%.

Policy:
- Reserve before dispatch. `RunDir.reserve_metric_calls(n)` takes the state lock, refuses (raises `BudgetExhausted`) if `spent + reserved + n > max_metric_calls`, otherwise records a reservation; `update_spent` converts it, a failed evaluation refunds it.
- The caller decides what a refusal means: a rung returns `unfunded` and the round ends; a confirmation returns `unconfirmed_budget`, which is never an accept (do not accept a screen-only candidate because the money ran out); the loop stops with reason `budget_reserved`.
- The same check for `max_usd` using a conservative estimate (rolling mean cost per rollout x n x 1.3).
- Round planner: before a round starts, compute the worst-case cost (96 + 96 + 96 + 2 x 147 = 582 at K=8) and shrink K until it fits. Expected cost is below the worst case.
- Budget-scaling rule for the whole run: baseline on F (4 trials x |F|) plus rounds. At B=550 and |F|=25: 100 + one round of K=6 (about 72 + 72 + 96 + 147 = 387 worst case) fits; two rounds do not. Budgets below about 400 rollouts cannot decide at all and should run SH rungs only and report "no champion resolvable at this budget".

## 4. Task 3: coverage and infrastructure errors

### 4.1 What actually happened (from the run directories)

E10 hill-climb Suite A seed 2: 14 candidates, 12 screened, 11 vetoed with `coverage<0.95 (92%)`. Their screen z were 2.2, 2.7, 3.0, 4.4, 2.5, 3.0, 2.7, 3.2, 3.0, 3.7, 2.7 (mean deltas +0.16 to +0.35). Cause, from `baseline.json`: the incumbent's own baseline has three tasks (50768, 9726, 55979) with `valid_trials=0, errored=True` and they were never re-run, so every candidate's joint coverage is 37/40 = 92.5%, forever. The stock gate's default `min_coverage` is 0.6; the E10 spec set `promotion_min_coverage` and `gate_min_coverage` to 0.95 (`capevolve.yaml:25,28`) and `gate_coverage: joint`. Across A hc, C hc and E31, 18 screen-passing candidates were vetoed (A s0: 1, A s2: 11, C s1: 3, E31: 3) against 7 that reached confirmation. Another A s2 candidate had coverage 0% (an adapter error: `agent view dir ... is not empty`), a genuine infrastructure failure that correctly yielded no verdict.

So the veto is not measuring the candidate. The remedies:

### 4.2 Principled treatment

Think in terms of missingness mechanism:

| mechanism | example | right treatment |
|---|---|---|
| exogenous, same on both arms (infra: 429, image pull, adapter setup) | the 3 seed tasks | missing completely at random: drop the task from the pair; costs only power (SE scales 1/sqrt(n_valid)); a veto is never needed for bias |
| exogenous but persistent on one side (the incumbent's) | the 3 seed tasks | retry; if still missing, quarantine the task from the evaluable set for this run, with an auditable event |
| candidate-induced (exception in the candidate's tool, candidate-induced timeout, malformed template) | `task_template` drops a placeholder; SB-5 in E05 | a measured failure: reward 0.0 (the policy `fail`, already implemented) |
| unknown (cannot attribute) | generic `trial k raised` | missing, but bounded by the sensitivity check below |

Why attribution matters in numbers: a candidate that crashes on 10% of tasks, all of which the incumbent passes at its mean rate 0.56, hides a regression of about 0.056 when those trials are dropped. That is the size of the effect the gate is trying to resolve.

Rules, in order:
1. Retry missing incumbent-side tasks once or twice at baseline and at every incumbent change (cost: number of missing tasks x trials, typically 3 to 10 rollouts). Retrying a candidate's missing tasks is also allowed, capped at 2 attempts, because the unit is `valid_trials=0`.
2. Tasks still missing on the incumbent after retries are quarantined: removed from the evaluable set E for the run, logged with `task_quarantined`. E replaces `planned_val_ids` as the coverage denominator.
3. Coverage is joint coverage on E: the fraction of E that is valid on both sides. Hard floor 0.75 (nothing can be inferred below that), no 0.95 veto.
4. Differential missingness: candidate-side errors on tasks the incumbent has valid and the candidate lost, in excess of the incumbent-side error count on E by more than max(2, 5% of |E|), are counted as failures (the candidate "broke" them), as the backstop for adapters that do not tag.
5. Tipping-point check replaces the veto between 0.75 and 1.0. Impute the m missing pair-deltas at -0.5 (a half-task regression) and recompute the screen z. If the screen still passes, proceed on available cases. If it flips, status `unresolved_missing`: spend the m x n_trials rollouts to re-run the missing tasks (at most 2 attempts); only then fall back to rule 4 and judge. A veto is then at worst a short retry rather than a lost candidate. For the E10 s2 candidates (m=3 of 40): imputing -0.5 for the three missing tasks moves the weakest candidate (mean +0.162, z 2.23) to mean +0.11 and z about 1.5, still above k_se = 1, and the stronger ones stay far above it, so none would have waited (estimated by hand from the logged screen means and SEs, not re-run).
6. Attribution of candidate-induced errors (the other half of the problem):
   - `trials.py:57-58` converts every exception into `Rollout(error=...)` with no kind. Add framework attribution: capture the traceback and mark `error_kind="candidate"` if any frame's file is under the candidate workdir (`run_dir/work/<cid>`), or the exception is a `TimeoutError` raised after the candidate's own step budget. Adapters may override.
   - The tau2 adapter never sets `error_kind` (grep: only the SpreadsheetBench adapter does), so on Suites B and C `errored_trial_policy: fail` is a no-op: the harness itself warns "reclassified 0 trials". Make the adapter tag the cases it can (tool-call schema errors from a candidate-edited tool definition, template render failures).
   - `harness.py:497` and `harness.py:757` already implement the `fail` reclassification; they need no change, only richer input.
   - The default for `errored_trial_policy` should be `fail` for any adapter that declares `supports_error_kind = True`, `drop` otherwise.

Minimum coverage parameters: `promotion_min_coverage` default 0.6 on the confirmation (kept), new `min_joint_coverage` 0.75 on E, tipping imputation -0.5, at most 2 retries.

## 5. Task 4: merging train and val into one optimised and gated pool

### 5.1 What the merge does to selection bias

There are two separate biases, and they behave differently.

1. Winner's curse (selection among noisy candidates and among the stopping time). Simulated in section 2.2: for the crown of a round of 8, the apparent gain over the true gain is +0.077 under a stock gate and +0.03 under a fresh confirmation. It shrinks as 1/sqrt(N): merging 49 and 25 tasks to 74 reduces the SE of a one-trial screen from 0.077 to 0.063 (inflation shrinks roughly in proportion; not simulated separately). It is the smaller problem, and it is cured by fresh rollouts in confirmation, which even rule P already does.
2. Adaptive overfitting (the proposer reads the traces of the same tasks the gate scores). The edit can fix those specific failures (a memorised rule, a hard-coded parameter) without helping unseen tasks. This is not removed by fresh seeds, because the tasks are the same; it only disappears when the confirmation tasks were never seen. It is also not measurable from the null pool, so I parametrise it: a candidate gets a per-candidate boost rho_j ~ U(0, 2 rho) on seen tasks, q <- q + rho_j (1 - q), zero effect on unseen tasks. At rho = 0.10 the mean extra apparent effect on seen tasks is 0.10 x 0.44 = +0.044, as large as a real +0.04 improvement.

Simulation (K=8, 49-task pool, all other settings as SH, threshold calibrated at rho = 0 to round FWER 0.10; `gate_budget_merge.json`):

| scheme | n_conf | zc | rho | round FWER | P(good) | P(null or harmful) | rollouts/round |
|---|---|---|---|---|---|---|---|
| naive merged pool (gate = feedback tasks, 49) | 98 | 1.51 | 0 | 0.102 | 0.58 | 0.024 | 359 |
| | | | 0.05 | 0.258 | 0.65 | 0.064 | 372 |
| | | | 0.10 | 0.531 | 0.67 | 0.143 | 380 |
| F33/C16, confirm on C only | 98 | 1.41 | 0 / .05 / .10 | 0.109 / 0.125 / 0.126 | 0.57 / 0.57 / 0.56 | 0.024 / 0.028 / 0.032 | 355 / 369 / 378 |
| F33/C16 | 147 | 1.39 | 0 / .05 / .10 | 0.116 / 0.129 / 0.127 | 0.61 / 0.61 / 0.60 | 0.024 / 0.027 / 0.031 | 442 / 462 / 474 |
| F25/C24 | 98 | 1.39 | 0 / .05 / .10 | 0.117 / 0.129 / 0.141 | 0.61 / 0.62 / 0.60 | 0.029 / 0.031 / 0.034 | 353 / 368 / 376 |
| F25/C24 | 147 | 1.38 | 0 / .05 / .10 | 0.116 / 0.130 / 0.140 | 0.65 / 0.65 / 0.65 | 0.024 / 0.028 / 0.031 | 440 / 460 / 472 |

(F/C rows use a historical m=8 baseline on C and no drift; the drift-proof recommended variant is in 5.3.)

Key facts:
- With zero memorisation the merged pool is as good as any: the pooled screen gets its power. With memorisation 0.05 the round FWER goes from 0.10 to 0.26; at 0.10 to 0.53, and 14% of mixed rounds crown a null or harmful candidate.
- A hidden confirm stratum is almost free. F25/C24 at n=147 has the highest P(good) of all rows (0.65) and a FWER that rises only from 0.116 to 0.140 at rho=0.10, because the screen's seen-task boost can only increase the number of candidates tested on C, never fake an effect on C.
- The cost is that screening uses a smaller pool (25 tasks instead of 49), which the table shows to be harmless because the rungs only rank.

### 5.2 Schemes considered

| scheme | unbiased internal estimate? | verdict |
|---|---|---|
| Naive merged pool, gate = feedback tasks | No (winner's curse and adaptive overfit) | reject as default |
| k-fold cross-fitting (propose on folds not f, gate on fold f, rotate) | Only for the first candidate. A parent accepted on fold B was built from traces of A, so its gate on A is contaminated; contamination accumulates along the lineage. Cross-fitting is valid for independent proposals, not for hill-climb lineages | reject |
| Reusable holdout / Thresholdout (noisy answer, bit only) | Approximately, the leak is bits of accept or reject | reduces to the hidden stratum below with extra noise; no extra value at 10 to 30 queries |
| Hidden confirm stratum C inside the pool, with bits-only access | Yes for the confirmation; selection among at most 2 survivors per round leaves a small winner's curse (+0.03) | recommended |
| Small reserved holdout H outside the pool (the sealed test, as today) | Yes, once | keep for the final report; it is not an internal estimate |

### 5.3 Recommendation, with numbers

Pool = train + val (Suite B: opt-49 plus sel-25 = 74 tasks; Suite A: 80 + 40 = 120). Draw once, seeded, stratified by the seed's pass rate (tertiles): C = 48% of the pool, F = 52%. For Suite B's opt-49 alone: F=25, C=24.
- F: the proposer sees traces and per-task rewards. Rungs 1 and 2 run here. Baseline 4 trials per task.
- C: the proposer sees nothing but aggregate accept or reject and one pooled number, never task ids or traces. Confirmation only, fresh seeds, concurrent control with 4 trials per task (96 rollouts per round when a survivor exists).
- Confirm n = 147 (6 trials per task), zc = 1.5, dmin = 0.02. Simulated with rho=0.10 and drift 0.03: round FWER 0.093 / 0.113 / 0.127 (rho 0, rho 0.1, rho 0.1 + drift), P(good) 0.558 / 0.555 / 0.561, rollouts per round 532 / 567 / 576, winner's curse +0.03 (`gate_budget_merge2.json`). Dropping the concurrent control instead costs nothing at zero drift but needs zc = 2.21 to hold the FWER under +0.03 drift and loses power (0.48).
- SE of one confirmation: 0.045. A decision resolves effects of about +0.09 with 80% power at this FWER (+0.07 at 50%).

Unbiased internal estimate of the final gain. After the search, re-measure the champion and the seed on C with fresh seeds, n_fin = 4 trials per task per side (192 rollouts). That estimate is conditionally unbiased for the effect on C's tasks (selection touched C only through bits), so the +0.03 curse disappears. Report with an interval that adds the task-sampling term: for a diffuse edit the per-task effect SD is about 0.15, so sd/sqrt(24) = 0.03 for generalisation to new tasks. It replaces the optimistic selection-split numbers of `searchtime/summary.md`.

Leak diagnostic: for each accepted candidate record d_F (the effect on F from rung data) and d_C (the confirmation); the F minus C gap estimates rho(1 - p). A persistent gap above 0.04 means the proposer is memorising; the remedy is to shrink what F-traces reveal (task-specific ids and expected outputs), not to enlarge C.

Cost of the scheme versus the status quo: none in rollouts, a one-time loss of 24 tasks from the proposer's feedback.

## 6. Task 5: parameters and code changes

### 6.1 Parameters

| key | value | notes |
|---|---|---|
| `promotion_rule` | `SH` (new, opt-in; `P` unchanged) | |
| `sh_k` | 8 (6 if budget at most 600) | candidates per round |
| `sh_rung1_n`, `sh_rung2_n` | 12, 24 | rollouts per candidate, random F-subsets |
| `sh_keep` | K/2 then K/4, requires mean > 0 | |
| `sh_conf_n` | 147 (196 for the high-power variant) | on C, fresh seeds |
| `sh_ctrl_m` | 4 trials per task on C | concurrent control |
| `sh_z_conf` | 1.5 (one-sided, <=2 tests per round) | calibrated to round FWER about 0.10 |
| `promotion_dmin` | 0.02 | |
| `sh_incumbent_trials` | 4 | F baseline, ranking only |
| `confirm_fraction` | 0.48, stratified by seed pass rate | |
| `min_joint_coverage` | 0.75 on evaluable set; `promotion_min_coverage` 0.6 kept | replaces the 0.95 veto |
| `missing_impute` / `missing_retries` | -0.5 / 2 | tipping-point check |
| `errored_trial_policy` | `fail` when the adapter declares `supports_error_kind` | |
| budget | reserve before every evaluate call; round planner shrinks K to fit worst case | |
| single-candidate mode (K=1) | group-sequential, looks 12/24/49/98/147, c=2.03, futility -0.5/0/0.3/0.7 | |

The existing `k_se` of rule P's screen stays 1.0 when P is used; SH does not use it (rungs are kill-only).

### 6.2 Code changes (file:line against the current tree)

1. `core/cap_evolve/promotion.py:24` `RULES = ("P",)` becomes `("P", "SH")`. `promotion.py:28-52` `PromotionParams`: add the `sh_*` fields and `from_spec` parsing. New pure functions next to `paired_stats` (`promotion.py:55`): `pooled_se(n, task_counts, v, m)` implementing A4; `halve(rung_stats, keep)`; `confirm_with_control(cand_task_means, ctrl_task_means, n_planned, z_conf, dmin, m_ctrl)`. `promotion.py:80-93` `confirm`: keep as is for P.
2. New `core/cap_evolve/racing.py` (pure, stdlib): `Rung`, `plan_round(budget_left, k)`, `run_round(evaluate, ...)` with the cost accounting that `reserve` needs, and the group-sequential boundary function for K=1.
3. `core/cap_evolve/rundir.py:303-330` and `:368-383`: add `reserve_metric_calls(n)` and `release_metric_calls(n)` under the same `_file_lock(self._state_lock)`, persisted in `state.json` as `reserved`; `budget_exhausted` (line 374) counts `spent.metric_calls + reserved`. `Budget` (line 94) gets `max_metric_calls` semantics unchanged.
4. `core/cap_evolve/harness.py:318-356` (`evaluate_candidate`): call `run_dir.reserve_metric_calls(len(tasks) * n_trials)` right after `tasks` is resolved (about line 370) and raise `BudgetExhausted` before any rollout; release on exception; `harness.py:668` converts the reservation into spend.
5. `core/cap_evolve/harness.py:3329-3340` (`_fresh_deltas` in `run_step`): before the two confirmation evaluations check `run_dir.can_afford(2 * len(ids) * promo.n_conf)`; if not, return status `unconfirmed_budget` (new stage in `promotion.PromotionResult`, `promote=False`), never accept. `harness.py:4638` keep the loop check, add the round planner.
6. `core/cap_evolve/harness.py:1189-1209` (`planned_val_ids`, `joint_coverage`): `planned` defaults to the evaluable set (`run_dir` state key `quarantined_tasks`); add `harness.retry_missing(adapter, run_dir, result, tag, max_attempts=2)` called after `baseline(...)` (`harness.py:859`) and after each incumbent change and each candidate evaluation (about `harness.py:3283`). `harness.py:3285-3292`: replace the pass-through of `coverage` into `gate.decide` with the tipping-point check (`gate.py:397-410` keeps the hard floor, now `min_joint_coverage` 0.75).
7. `core/cap_evolve/gate.py:397-410`: the `INDECISIVE` message distinguishes `unresolved_missing` (retryable) from `below floor`. `core/cap_evolve/loop.py:34` `has_valid_trials` unchanged.
8. `core/cap_evolve/trials.py:57-58`: attribute exceptions by traceback (frames under the candidate workdir) and set `Rollout.metadata["error_kind"]="candidate"`; `harness.py:497` and `:757` already consume it.
9. `templates/adapters/tau2_bench/adapter.py`: set `error_kind` ("candidate" vs "infra") on the failure paths it owns, and `supports_error_kind = True`. Same for the other adapters that do not (only SpreadsheetBench does today).
10. `core/cap_evolve/splits.py:26-60` (`Splits`): add a `confirm` role carved out of the pooled split with the stratified draw, persisted and sealed like `test`; `Splits.ids("feedback")` excludes it. `harness.py:1139-1142` (`pop_promotion`) and `PROMOTION_KEYS` (`harness.py:1124`) get the new keys. The proposer's view builder (`OptimizerContext`, trajectories and guidance writers) must filter C; the evaluate tool returns only bits for C.
11. `core/cap_evolve/subsample.py:272` (`screen_decision`): add `mode="halve"` (kill-only, no promote bias) so the AO `screen.py` shares the rungs.

### 6.3 Tests (all in `core/tests/`, pure unit tests with seeded fakes, in the style of `test_promotion_rule_p.py`)

- `test_promotion_sh.py`
  - `pooled_se` equals a brute-force Monte Carlo SE within 5% for n=12, 49, 147 and m=1, 4.
  - Null calibration: on a seeded Bernoulli world (p from `null_p.json`) the round FWER at the shipped zc is below 0.15 (K=8, 4,000 rounds), and the K=1 group-sequential per-candidate FA below 0.03.
  - Rungs never return `accept`; confirmation never reuses rung seeds or rollouts (assert disjoint `trial_offset` ranges).
  - Under +0.03 drift with a stale incumbent the control path keeps FWER below 0.15 and the no-control path exceeds 0.25 (documents why control exists).
  - Hoeffding-style bounds are not shipped (assert no code path with `range=2` radius).
- `test_budget_reserve.py`
  - Two threads reserving more than the remainder: exactly one succeeds; refund on failure restores the balance.
  - `evaluate_candidate` raises `BudgetExhausted` before dispatching any rollout (fake adapter counts calls = 0).
  - A rule-P confirmation that does not fit yields `unconfirmed_budget`, `promote=False`, and a screen-passing candidate is never accepted on budget exhaustion.
  - Replay of the B hc case: budget 550, the old code overshoots to about 637, the new code never exceeds 550.
- `test_coverage_quarantine.py`
  - Fixture with the E10 A s2 shape: incumbent has 3 tasks with `valid_trials=0`, 11 candidates with z in 2.2 to 4.4. Retry succeeds on 1 of 3: coverage computed on E; no candidate vetoed.
  - Still missing after 2 retries: tasks quarantined (`task_quarantined` event), coverage 1.0 on E.
  - Candidate-side 20% missing: floor 0.75 gives `INDECISIVE` below 0.75, tipping check flags between 0.75 and 1.0 when the imputed z flips.
  - Differential missingness: candidate errors in excess of the incumbent's count by more than max(2, 5%) are counted as failures.
- `test_error_attribution.py`
  - An exception raised inside a module loaded from the candidate workdir gets `error_kind="candidate"` and reward 0.0 under `fail`; an exception from the adapter or a `ConnectionError` stays missing.
  - Quantify: a candidate that crashes on 10% of tasks the incumbent passes loses at least 0.05 under `fail` and is flat under `drop` (documents the hidden regression).
- `test_confirm_stratum.py`
  - C and F are disjoint, stratified by pass rate, deterministic from the seed; C ids and traces never appear in any optimizer-visible file (scan `INSTRUCTIONS.md`, `guidance/`, `trajectories/`); the evaluate tool's return for C has only bits and aggregates.
  - Leak diagnostic: a synthetic memorising candidate (boost on F, none on C) produces an F-minus-C gap above 0.04 and is rejected by the confirmation.

## 7. What was not measured, and what could overturn this

- The overfit boost rho is a parameter, not data. No held-out score exists yet (final evaluation starts after 2026-10-13 06:00 UTC); the first real estimate of rho(1 - p) will be the gap between selection-split and held-out gains for the stock-gate arms (A: +0.29 to +0.35 on val-40). If the gap is near zero, the hidden stratum is insurance rather than necessity, and it still costs nothing in power.
- Edit effects were diffuse. A sparse edit concentrated on a few tasks lowers every design's power, kill-only rungs most (a 12-task random rung can miss all affected tasks). Mitigation within the design: rung-1 subsets may include the incumbent's failing tasks via `select_screen_subset`, but then the rung is no longer a random subset and the pooled phat must come from the same tasks; not simulated.
- Candidates are independent in the simulation apart from the shared incumbent. Proposals from one parent are positively correlated in practice, which raises the effective round FWER above the independent calculation.
- Throughput numbers come from E10B's hc cells at the then-current gateway load.
- The simulated rule P has lower FA than the pool (0.016 vs 0.026). If the pool is right, rule P's comparison row is slightly worse for P than shown, which strengthens the conclusion.
- Action needed before any of this runs in the campaign: nothing; the frozen arms keep `P`. For the product, implement behind `promotion_rule: SH` and run `sim` vs a Suite B replay.
