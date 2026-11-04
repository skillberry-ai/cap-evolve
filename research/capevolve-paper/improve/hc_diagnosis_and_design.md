# CapEvolve hill-climb: where the budget went, why gains were small, and what to change

Scope: read-only diagnosis of the hill-climb (hc) runs. Nothing was run, stopped, edited or committed besides this file. All numbers are SEARCH-TIME on the run's own val/selection split, so they are optimistic and not comparable across methods. I did not open any `rollouts/test` file or any `FINAL` score; the final-eval window is sealed until 2026-10-13 06:00 UTC (`analysis/out/searchtime/summary.md` caveat), so nothing here is a held-out claim. Anything I could not verify is marked **[UNVERIFIED]**.

Path shorthands: `S` = `/home/dev/projects2/campaign-scratch`, `R` = `/home/dev/projects2/cap-evolve-campaign/research/capevolve-paper`, `C` = `/home/dev/projects2/cap-evolve-campaign/core/cap_evolve`, `A/st` = `R/analysis/out/searchtime`. Run dirs are `S/runs/<exp>/<arm>/s<k>/.capevolve/run_*`. Throwaway scripts live in `/tmp/hcdiag/` (`timeline.py`, `steps.py`, `acct.py`, `load.py`, `sim.py`); they read the run dirs and `events.jsonl` `step`/`promotion`/`eval_start`/`evaluate` records, and are not part of the repo. `sim.py` runs under `S/venv/bin/python -I`.

---

## 0. Findings in ten lines

1. **Evaluation is 90-99% of wall-clock; the proposer is 1-5%.** Per-iteration proposer time is a median of 38-91 s (`step.optimizer_seconds`) against 0.6-2.0 h for the screen. Wall time is a function of rollouts per hour, not of the optimizer.
2. **Rule-P confirmation costs 6x a screen** (candidate 3 trials plus incumbent re-measured 3 trials = `6N` rollouts versus `N`). It consumed 14.2 h of 28.9 h (49%) of the mean Suite B hc search, and 5.7 of 8.8 h on Suite D rule P. Confirmed candidates were rejected in 7 of 15 confirmations.
3. **Two gate-plumbing defects destroyed most of the A/C yield, not the proposer.** (a) The coverage veto: baseline infra errors on 3 of 40 tasks made joint coverage 92.5% forever, so 11 of 12 screened candidates (z = 2.2 to 4.4, one at 0.90 vs 0.568 with 13 fixed / 0 broke) were vetoed (A hc s2, 440 of 600 rollouts). (b) Budget straddling: a screen pass triggers a 240-294 rollout confirmation without checking the remaining budget; the cap then truncates it, and the truncated confirmation is recorded as a `confirm_reject` (A hc s0 cand_0004: n=0; A hc s1 cand_0002: n=14 of 40).
4. **On Suites B/D the single-trial noise equals the effect size.** Nine draws of the identical seed on B val-49 have mean 0.596 and SD 0.053; two identical draws differ on 14.3 of 49 tasks (6.6 "broke", 7.6 "fixed"). The ledger the proposer reads reports 5-9 broke / 4-9 fixed per candidate, which is the null rate. Rule P as shipped has a 22% chance to promote a true +0.06 edit on B (51% at +0.10), by my calibrated simulation (section 2.5).
5. **The incumbent baseline is one draw, reused for every candidate.** B hc s1's seed draw was 0.653 (true about 0.596). All ten candidates were compared with a lucky baseline and screen-rejected; 539 rollouts and 27 h produced nothing. Re-scored against the pooled seed, cand_0001 is +0.118 (z 1.96).
6. **Proposer diversity collapses.** B hc s1 cand_0003 to cand_0010 are near-copies of the same bounded guards (13-59 changed lines; the proposer's own transcript says "re-shipped the tool guards from cand_0005 ... looks like run-to-run noise"). A hc s2 re-discovered the same format fix 11 times because nothing was ever promoted. Only 6-24 tool calls per proposer session.
7. **The proposer sees the same evidence every time**: the parent's single val draw (`_copy_step_trajectories`, `harness.py:2563`), with an n=1 ledger that labels every flip causal. Train data is only used for a baseline bookend (80 rollouts, 13% of the A budget, about 6 h serial).
8. **Parallelism actually used:** harness `workers=1` in all B/C/D hc runs (the `cap-evolve run` command never forwards `--workers`, `cli.py:960-966`); adapter-internal concurrency 6 (`TAU2_MAX_CONCURRENCY`). A used `--workers 4` for the loop but ran the 120-rollout baseline at `workers=1` (9.3 h of a 24.9 h search).
9. **Competitors' mechanics that matter at equal cost** are: no 6x confirmation (every proposal gets one val evaluation), the proposer reading fresh TRAIN failures rather than the val traces the gate scores, and a population/frontier. A teammate's parallel analysis (`R/improve/competitor_mechanisms.md`) finds that much of the Suite A gain is one easily found format fix and that multi-candidate machinery adds at most about +0.05 to +0.10; the evidence here agrees.
10. **Merging train and val** increases gate power (N 49 to 147 lifts P(promote | +0.06) from 0.22 to 0.55) but removes the only data the proposer has not seen, and would make selection and acceptance share tasks. The existing design already lets the proposer see val traces, so the validity problem pre-exists; the better move is the reverse (traces from train, gate on val) or a rotating partition of the pool (section 5).

---

## 1. Task 1: where the rollouts and the wall-clock went

### 1.1 Wall-clock breakdown (mean over 3 seeds, hours)

Source: `events.jsonl` `eval_start`/`evaluate` (`seconds`), `step.optimizer_seconds` (script `/tmp/hcdiag/timeline.py`). "Other" is process gaps, restarts and infra repairs.

| group (exp) | iterations / search | wall | baseline | candidate screens | confirmations | final | proposer | other |
|---|---|---|---|---|---|---|---|---|
| A hc rule P (E10/hill-climb) | 4, 2, 14 | 24.9 | 9.3 | 7.1 | 6.5 | 0.0 | 0.08 | 1.94 (s2 had a 5 h restart after the agent-view-dir defect) |
| A hc stock (E12A) | 12, 12, 12 | 15.9 | 6.0 | 9.9 | 0 | 0 | 0.11 | 0 |
| B hc rule P (E10B/hc) | 2, 10, 2 | 28.9 | 1.5 | 12.3 | **14.2** | 0.3 | 0.10 | 0.62 |
| C hc rule P (E10C/hc) | 9, 8, 10 | 25.1 | 1.3 | 13.5 | 9.8 | 0.2 | 0.26 | 0.01 |
| C hc stock (E12C) | 10, 10, 10 | 18.4 | 1.3 | 15.7 | 0 | 1.2 | 0.25 | 0.01 |
| D rule P (E21/ruleP) | 6, 2, 2 | 8.8 | 0.6 | 2.1 | **5.7** | 0.3 | 0.10 | 0.01 |
| D stock P / PT / T (E20) | 10 each | 7.1 / 8.2 / 8.4 | 0.6 | 5.8-7.3 | 0 | 0.3-0.6 | 0.17-0.30 | 0.01 |
| D stock 1S (E21) / NOHIST (E26) | 10 each | 7.7 / 5.7 | 0.8 / 0.4 | 6.3 / 4.4 | 0 | 0.4 / 0.3 | 0.25 / 0.51 | 0.01 |

Proposer share of (proposer + screen) time, from `step` events: A 0.9-1.1%, B 0.9%, C 1.6-1.9%, D 2.8-4.5%, E26 NOHIST 10.3% (it is shorter because the proposer sees no history; `proposer 178 s median`).

Per-iteration timing (median): proposer 38 s (A), 66 s (B), 62 s (C), 47-91 s (D); screen evaluation 1.02 h (A, workers 4), 2.0 h (B), 1.53 h (C), 0.56-0.70 h (D). Rollout throughput implied: B 49 rollouts / 5,300 s = 33 per hour per search (median individual tau rollout 2,277 s under load, `R/decisions.md:295`); D 84 per hour; A 11.7 per hour at `workers=1` for the baseline, 16-82 per hour at `workers=4`.

### 1.2 Parallelism actually used

| suite | harness `workers` | adapter concurrency | evidence |
|---|---|---|---|
| A baseline | 1 | per rollout | `events.jsonl` `eval_start.workers=1` for seed val (3.4 h) and seed train (5.9 h) in all three A hc seeds |
| A candidate loop | 4 | per rollout | `parallel` event `workers: 4`; `eval_start.workers=4` |
| B, C, D hc | **1** | `TAU2_MAX_CONCURRENCY=6` inside the tau adapter (`S/runs/E10B/hc/s0/env.sh`) | every `eval_start.workers=1`; no `parallel` event |

`cap-evolve run` builds the hill-climb command at `cli.py:960-966` with `--max-iterations --n-trials --gate-mode --k-se --store` and nothing for workers. `skills/algorithms/hill-climb/scripts/run.py:90` only sets `harness.DEFAULT_WORKERS` from `--workers` (default 1); `harness.py:54` documents "every published number was measured serially". The campaign decision that "all runners parallelize within a search (~6 concurrent rollouts)" (`R/decisions.md:29`) is thus true only through the adapter on B/C/D. Whether more workers would shorten B wall time is **[UNVERIFIED]**: `decisions.md:299` says the gateway has 24 gpt-oss in-flight slots shared across all searches, so B may be gateway-bound.

### 1.3 Rollouts by purpose (on-disk rollout files; script `/tmp/hcdiag` inline in this analysis)

Per candidate: screen = `N` rollouts (40 on A, 49 on B/D, 20 on C, 1 trial). Confirmation = `2 x 3 x N` = 240 / 294 / 120 rollouts, so **a promoted candidate costs 7 screens and a confirm-rejected one costs 7 screens for no state change**. The per-search budget is 550-600 rollouts, so the whole search is about 11-12 screens, or 1.9 candidates carried through confirmation on B.

Sum over 3 seeds (planned = rollout files actually written):

| suite | baseline | screen-rejected | promoted (screen+confirm) | confirm-rejected (screen+confirm) | coverage-vetoed | cap-truncated or no verdict |
|---|---|---|---|---|---|---|
| A hc | 120 val + 240 train | 80 | 560 (2 candidates) | 0 genuine | **480** | 2 truncated confirmations recorded as `confirm_reject` (about 120 and 200 real rollouts) |
| B hc | 147 | 588 | 0 | 686 (2 candidates) | 0 | **392** (s0 and s2 cand_0003: screen + 3-trial `__conf` done, `__confbase` never ran) |
| C hc | 60 | 400 | 280 | 280 | 60 | 0 |
| D rule P (E21) | 147 | 245 | 1,372 (4 promoted) | 343 | 0 | 0 |

Budget overrun (counted rollouts vs the spec cap): B hc s0/s2 637 vs 550 (+16%); D rule P 687 / 785 / 785 vs 550 (+25% to +43%) (`A/st/summary.md`, `S/runs/E21/ruleP/*/logs`). The check is `run_dir.budget_exhausted()` at the top of the loop only (`harness.py:4637`, `rundir.py:368-383`); `spent.metric_calls` is debited after each evaluate (`harness.py:668`). A has an external hard cap (`rollout_counter.json` `max 600`) which truncates silently, producing the wrong verdicts in 3.2.

### 1.4 Waste classes

| class | rollouts per search | evidence | verdict |
|---|---|---|---|
| Train baseline bookend (A) | 80 of 600 (13%), about 6 h serial | `eval_start split=train tag=seed`; audit says train is "only evaluated by baseline and finalize bookends" (`R/audit/algorithm_audit.md:57`) | pure waste for search |
| Coverage-vetoed (A s2) | 440 | 11 `gate_veto` steps, z = 2.2 to 4.4 | gate artifact |
| Coverage-vetoed (C s1, s0 A) | 60, 40 | `stage gate_veto` | gate artifact |
| Straddlers | A 120-200; B 196 each in s0, s2 | section 3.2 | process defect |
| Confirm-rejected, genuine | 343-392 on B (2 per search) | confirm means +0.048 (z 1.04), +0.014 (z 0.35) | principled, but 6x screen cost |
| Duplicate re-discovery from a non-advancing parent | A s2 14 candidates, B s1 10 | section 3.1 | search-design waste |
| Candidate-induced infra drops (D) | 107 of 6,323 tau2 rollouts | `R/audit/silent_env_failures.md:101-106` | biases Δ and triggers coverage vetoes |

---

## 2. Task 2: why gains were small or absent

### 2.1 What each outcome is caused by (rule P hc, 9 A/B/C searches)

| search | search-time gain | root cause (evidence) |
|---|---|---|
| A s0 | +0.171 | cand_0004 (screen +0.133, z 2.6 vs the new 0.741 incumbent, val 0.875) was truncated by the 600 cap and recorded `confirm_reject` with n=0 (`events.jsonl` promotion, `fresh_from_trial 1006`). |
| A s1 | +0.103 | cand_0002 (screen +0.158, z 2.5, val 0.85) confirmed at n=14 of 40 (coverage 0.35, mean -0.047) then `confirm_reject`. |
| A s2 | 0.000 | 11 of 12 candidates vetoed: "only 92% of val tasks produced a valid score (< 95% required)". The 3 missing tasks (`50768`, `9726`, `55979`) are in the SEED baseline only, as `sandbox exec failed: 500 Server Error ... Infrastructure error` (`rollouts/val/*__seed__t0.json`); every candidate has all 40 rollouts. Because the baseline is never re-measured, joint coverage is 37/40 = 0.925 forever. |
| B s0, s2 | 0.000 | cand_0001/0002 screened +0.06 to +0.10, confirmed to +0.048 (z 1.04) / +0.014 (z 0.35): small true effects. cand_0003 (3-trial mean 0.673 / 0.626 vs pooled seed 0.596) never got a verdict (straddler). |
| B s1 | 0.000 | seed draw 0.653 was +0.057 above its mean; 10 candidates, all screen-rejected against it. |
| C s0 | +0.150 | cand_0003 promoted (conf +0.108, z 3.1). Then 6 screen-rejects against a 0.708 incumbent draw. |
| C s1 | 0.000 | cand_0005/0006/0007 vetoed at 90% coverage (screen Δ +0.33, +0.17, +0.28; z up to 2.6). Seed has 2 of 20 tasks unscored. |
| C s2 | +0.134 | cand_0005 promoted. |

Counterfactual, if just the coverage and truncation defects were fixed (**[UNVERIFIED]**, since I did not rerun): A s2 and C s1 move from 0 to roughly the +0.2 other seeds reached, and A s0 / s1 would likely promote cand_0004 / cand_0002 (val 0.875 / 0.85 vs returned 0.75 / 0.692). That is 4 of 9 searches changing outcome.

### 2.2 Proposer edit quality and diversity

Evidence is `candidates/`, `work/cand_*/PROCESS.md`, and the Claude transcripts under `claude_cfg/projects/*cand-*/*.jsonl`.

- **A (Gemma, system prompt).** Candidates 0001-0003 of s0 each add a "Reply format (strict)" block forbidding `<|tool_call>call:python_interpreter` syntax (14-19 changed lines). This is the same easy fix every competitor found in its first edit (`R/improve/competitor_mechanisms.md` §0.1). cand_0002 also added an "Ordered procedure" block and was the only one to lose (-0.222, 12 broke). So hc found the high-value edit right away; the problem was keeping it (3.2), and 14 repeat discoveries in s2.
- **B (tau retail tools + policy), s1.** `diff -r candidates/seed candidates/cand_00xx`: 102, 62, 57, 59, 49, 48, 53, 16, 17, 13 changed lines. cand_0003 to cand_0010 contain the same set: same-item exchange guard, `_check_country('USA')` guard, cancel docstring warning. The proposer's PROCESS lines read: "guards identical to cand_0003/0001", "Iteration 6: re-ship bounded tool guards (cand_0005 set), no policy", "Minimal iteration (budget exhausted)". The cand_0006 transcript shows 6 Bash calls, no trace reading, and the final message: "Each one fixed a different handful of tasks and broke a different handful ... which looks like run-to-run noise." The system had no way to act on that realisation.
- **Breadth.** Edits are mostly "bounded guards" (narrow) after the proposer concludes prose edits "broke passing tasks" (cand_0002 explicitly drops the policy rules because cand_0001 "broke 103,34,78,82,99"). Those 5 "broke" tasks are noise (next item), so a good edit class was abandoned on a phantom regression.
- **Proposer effort.** 6-24 tool calls and 38-178 s per session (`optimizer_seconds`); the PROCESS.md template is mostly unfilled in A (`Ranked issue list` table empty). This is not evidence of a weak model; it is evidence the loop gives it a small, repetitive job.

### 2.3 The information the proposer gets is noise-dominated

- `_copy_step_trajectories` copies only the parent's tag (`*__seed__t0.json` when the parent is the seed), i.e. 49 rollouts from ONE draw, identical for every iteration while the parent does not advance (`harness.py:2563-2620`; `work/cand_0006/trajectories` lists 49 `__seed__t0` files).
- `_classify_moves` (`harness.py:1690-1723`) with `move_is_resolved` (`harness.py:1578-1602`) uses per-task SE from trials. The docstring says that at one trial per task "every per-task SE is 0 ... classifies exactly as it always did", i.e. every flip is a resolved broke/fixed. The LEDGER therefore states that the ledger "list[s] only tasks whose move EXCEEDED 2.SE" while at n=1 it lists all.
- Null reference, computed from identical-capability seed draws (`rollouts/val/*__seed__t0.json` and `*__confbase__t100x.json`): pairwise flips between two draws of the same seed are **14.3 of 49 tasks on B (broke 6.6, fixed 7.6; 9 draws)**, **15.4 of 49 on D (7.7 / 7.8; 18 draws)**, **4.6 of 20 on C (2.3 / 2.4; 15 draws)**. B hc s1 candidates report n_fixed 4-9 and n_broke 5-9 (`A/st` step events), indistinguishable from the null. Tasks on B val: 4 always fail, 8 always pass, 37 flaky out of 49.
- Where an accepted edit's gain really came from (fresh 3-trial confirmation, tasks improved in at least 2 of 3 trials, `rollouts/val/*__conf__*` vs `*__confbase__*`): A s0 cand_0003 +0.117 from 3 robust fixes / 1 robust break (18 tasks changed at all); A s1 cand_0001 +0.125, 6 / 1 (22 changed); C s2 cand_0005 +0.133, 4 / 1 (9 changed); D ruleP s0 cand_0006 +0.122, 9 / 0 (25 changed); D ruleP s2 cand_0002 +0.109, 6 / 0. Real gains are 3-9 robustly fixed tasks (6-18% of the split) with 0-2 robust breaks, hidden inside 18-28 tasks that merely changed. The screen's claimed "9 fixed 3 broke" is 1.5-3x the robust count.

### 2.4 Gate behaviour

| aspect | evidence |
|---|---|
| Coverage vetoes | A s2 11, A s0 1, C s1 3-4, D E21-1S s2 7 (86-94%), E31 ruleP all (85%). `gate.py:397-406` returns `indecisive`; the denominator is `planned_val_ids` (`harness.py:1189`) and the numerator excludes tasks invalid on EITHER side (`joint_coverage`, `harness.py:1194-1207`). Parent-side infra misses are permanent because the baseline is never re-run. Spec keys `gate_coverage: joint`, `gate_min_coverage: 0.95` were set in every rule-P project. |
| Truncated confirmation mislabelled | `promotion.confirm` returns `pass False` when coverage < `min_coverage` (`promotion.py:80-92`), and `decide` labels that `confirm_reject` (`promotion.py:118-123`) with `accepted=False` in `run_step` (`harness.py:3350-3360` area). The rejected-edit memory then tells the proposer that the edit "did not work" (an indecisive step would not be recorded, `harness.py:~3395`). |
| False rejections by noise | In B, confirmed means were +0.048 and +0.014 against pooled-seed deltas of +0.057 and about 0.0: shrinkage of 50-87% from screen to fresh trial is the winner's curse, so these are mostly correct rejections. The false rejection is in the screen: B s1 cand_0001 is +0.118 (z 1.96) against the pooled seed. |
| Noise | Per-draw SD of a 49-task mean is 0.051-0.053 (empirical SD of 9 seed draws 0.053; prediction from within-task Bernoulli variance 0.130/49 -> 0.051). |
| Power (calibrated Monte-Carlo, section 2.5) | Rule P as shipped on B: P(promote) = 0.02 / 0.08 / 0.22 / 0.52 / 0.81 at true effect +0.00 / +0.03 / +0.06 / +0.10 / +0.15. |

### 2.5 Power simulation (how likely rule P is to promote a real improvement)

Method (`/tmp/hcdiag/sim.py`): per-task success probabilities `p_i` are the mean of the 9 seed draws on B val-49; the candidate raises `p_i` by an effect `d` (mean over tasks) spread proportionally to headroom; outcomes are Bernoulli; screen is 1 trial vs one existing parent draw, `mean > 1.0 SE`; confirmation is 3 trials each side, `z >= 1.282`, `dmin 0` (exactly the spec: `promotion_n_conf 3`, `z_conf 1.282`). 2,000-3,000 repetitions per cell.

| true effect | P(promote), N=49 (shipped) | cost / candidate | cache incumbent in confirm | sequential confirm + cache | 3-draw baseline (150 extra once) | P(promote) N=98 | N=147 |
|---|---|---|---|---|---|---|---|
| 0.00 | 0.020 | 96 | 0.011 / 82 | 0.014 / 75 | 0.018 / 101 | - | - |
| +0.03 | 0.077 | 129 | 0.077 / 107 | 0.062 / 95 | 0.091 / 144 | 0.122 | 0.160 |
| +0.06 | 0.224 | 169 | 0.222 / 132 | 0.201 / 122 | 0.287 / 192 | 0.413 | 0.551 |
| +0.10 | 0.517 | 229 | 0.505 / 165 | 0.482 / 161 | 0.615 / 264 | 0.772 | 0.898 |
| +0.15 | 0.813 | 293 | 0.796 / 198 | 0.796 / 197 | 0.893 / 317 | - | - |

Reading: edits on B have true effects of about +0.03 to +0.08 (3-trial means 0.626-0.673 vs 0.596), where shipped power is 8-35%. With 14 B candidates, 0 promotions has probability roughly 0.9^14 = 23%, so the B outcome is unremarkable; the design cannot see this effect size at 49 tasks. Assumes independent Bernoulli noise and uniform effect spread **[model assumption, not measured]**.

### 2.6 Exploration versus exploitation, and parent improvement rate

- Single incumbent, no population: `hill_climb_loop` forks `run_dir.best_id` every iteration (`harness.py:4619`, "Parent is always the current best"). When nothing is promoted (A s2, B s1, C s1) every candidate is a sibling of the seed with the same evidence (2.3).
- Child beats the parent's single draw: A hc 94% (mean +0.181, because the seed prompt has the format bug), A stock 42% (+0.016), B hc 36% (-0.008), C hc 56% (+0.063), C stock 13% (-0.068), D stock P/PT/T 23/47/37% (-0.053/+0.007/-0.008), D rule P 90% (+0.075), D E21-1S 60% (+0.023), NOHIST 50% (-0.005). A fraction near 40-50% with mean about 0 is the signature of noisy comparisons against a fixed parent draw, as in the null. (Script `/tmp/hcdiag/steps.py`, computed from `step.val` and `step.parent_val`.) After a promotion the parent score is a fresh 3-trial mean (`harness.py:4660-4662`), which fixes the parent-luck problem only from the second iteration.
- Rule P succeeded where there is real headroom and the cost fits: D ruleP promoted 5 of 7 confirmed candidates (+0.102 / +0.136 / +0.256 search gain) but ran only 6 / 2 / 2 iterations because each confirmation cost 294 rollouts.

---

## 3. Task 2 detail: the two process defects

### 3.1 No-advance repetition
Parent stays at the seed unless promoted, so a gate that never promotes (A s2, B s1) converts the budget into N near-identical samples. A s2: cand_0001, 0004-0013 all `val 0.725-0.90`, 9-13 fixed, 0-2 broke, i.e. the same format fix re-found 11 times; B s1 as in 2.2.

### 3.2 Budget straddling
`budget_exhausted()` is only evaluated at the top of each iteration (`harness.py:4637`). A screen pass then invokes `promotion.decide(..., _fresh_deltas, ...)` at `harness.py:3329-3345`, which runs `evaluate_candidate(... n_conf)` twice (`tag=<cid>__conf`, `<cid>__confbase`) without asking whether `2*n_conf*N` rollouts remain.
- Suites with an external cap (A): cap fires mid-confirmation, remaining rollouts error, coverage drops, `confirm_reject` (A s0 n=0, A s1 n=14 / coverage 0.35).
- Suites without (B/C/D): the run overruns by 16-43% and the final candidate's confirmation may run only on one side (B s0, s2 cand_0003: 147 candidate rollouts present, zero baseline rollouts; no promotion record, no step record).

---

## 4. Task 3: mechanisms that explain competitors' search-time gains at similar optimizer cost

Sources: `S/baselines/deviations_{gepa,metaharness,evoskill}.json`, `S/baselines/EvoSkill/src/loop/runner.py:263-364` and `registry/manager.py:378-395`, `A/st/summary.md` (arm table), and the teammate's `R/improve/competitor_mechanisms.md` (not re-derived here). Optimizer cost at 600 rollouts on A is comparable (non-cache tokens / USD): GEPA 0.42-0.60M / $1.4-2.1; Meta-Harness 0.16-0.21M / $0.67-0.94; EvoSkill 0.39-0.79M / $1.3-2.3; hc rule P 0.09-0.65M / $0.34-2.47; hc stock 0.50-0.53M / $1.9-2.2. So optimizer spend does not explain the gap; rollout allocation does.

| mechanism | GEPA 0.1.4 | Meta-Harness | EvoSkill | CapEvolve hc rule P | effect on search-time gains |
|---|---|---|---|---|---|
| Evaluation per proposal | 3-task train minibatch for parent + child (6 rollouts), full val (40) only if minibatch sum improves strictly | 20 train tasks traced + val-40 | 4 train failures + val-40 | val-N screen; then 6N confirm on a screen pass | GEPA: 19 proposals / 9 full-val in 600 rollouts. Meta-Harness 8 / 8. EvoSkill 6-9. hc: 2, 4, 14 screened, 0-2 confirmed. Proposals evaluated per 100 rollouts: GEPA 3.2, MH 1.3, EvoSkill 1.5-2.0, hc rule P 0.3-2.3, hc stock 2.0 |
| Acceptance | none beyond the minibatch gate; child joins the pool | none (all candidates evaluated, argmax val) | joins frontier of 3 if it beats the lowest member (`manager.py:378-395`) | paired k_se=1, then fresh confirm | Competitors accept on noisy evidence and select by max, which inflates search-time gain by roughly the expected max of k noisy draws (for k=9-12 and SD 0.05-0.08, about +0.08 to +0.12), per the teammate's EB analysis. This is a measurement advantage in the table, not necessarily a generalisation advantage **[UNVERIFIED on test]** |
| What the proposer reads | fresh minibatch traces from TRAIN (reflective dataset, <=20k chars per transcript) | seed traces on all 80 train + rotating 20-task train batch; val gives aggregates only | failures from a round-robin train sample (`runner.py:278-331`) + `feedback_history.md` | the parent's val traces (one draw), same files each iteration | Fresh failures each iteration give diversity and avoid fitting the gate's tasks. hc re-reads identical evidence (2.3) |
| Population | per-task Pareto frontier, parent sampled from it | proposer free to read every prior candidate | frontier size 3, parent selection configurable | single incumbent | Prevents a lucky or unlucky parent draw from deciding the whole search |
| Candidates per iteration | 1 | 2 | 1 | 1 | Meta-Harness best-of-2 from shared evidence |

Which mechanisms explain gain at similar optimizer cost, ranked by evidence: (1) cost per decision: no 6x confirmation, so 2-4x more proposals reach evaluation; (2) fresh train traces for the proposer; (3) no brittle coverage/veto plumbing; (4) population or frontier (weakest evidence at this noise level, because per-task wins at one trial are noise, 2.3). MIPRO, ACE and Trace2Skill with k=1-2 evaluations reach +0.20 to +0.28 on A, so on Suite A a large share of any method's gain is the easy format fix, not search machinery.

---

## 5. Task 5: merging train and val into one optimization pool

What hc does today: the proposer reads val traces, the gate scores val, and train is evaluated once for a bookend (audit `algorithm_audit.md:56-57`; `hill_climb_loop` builds the focus order from `read_splits().val`, `harness.py:4600`). So selection and acceptance ALREADY share tasks; the confirmation uses fresh trials (`harness.py:3331-3335`, `trial_offset=fresh_from`) on the same tasks.

Effect of the merge on gate validity:

1. **Power rises, a lot.** Pool 98 or 147 vs 49: P(promote | true +0.06) goes 0.22 to 0.41 to 0.55; P(promote | +0.10) 0.52 to 0.77 to 0.90 (section 2.5). Cost per candidate grows with N (screen N, confirm 6N), so promote-per-rollout efficiency improves less (+0.06: 169 rollouts/candidate at 22% = 770 per promotion at N=49; 423 at 41% = 1,030 at N=98; 700 at 55% = 1,270 at N=147). Larger pool wins on power per search, loses on cost per promotion unless confirmation is made cheaper (4.2, 4.3).
2. **Validity.** The paired-SE test treats the candidate as independent of the tasks' noise. It is not: the proposer targets observed failures, so (a) screen evidence on seen failing tasks measures memorisation of the seen traces, (b) fresh TRIALS (rule P) remove the trial-noise winner's curse but not the task-selection one. This pre-exists (val traces are visible), but the merge removes train, the only tasks not yet seen, and so removes the only chance of an unadapted check. Expected consequence: a larger proportion of the pool becomes "fixed by construction", inflating search-time and promotion rates. Test remains the unbiased judge.
3. **Cross-iteration exposure.** Even if each iteration partitions the pool, the incumbent lineage carries fixes learned from earlier folds, so a later gate on an earlier-seen fold is not held out. This is why a simple K-fold rotation is not enough.

How to keep a held-out selection signal (ordered by cost):

- **(a) Keep the split, change who reads what (recommended).** Proposer reads fresh TRAIN failures (rotating minibatch of 3-20 tasks, as GEPA / MH / EvoSkill do); gate and confirmation use VAL, from which the proposer sees only aggregate and a failing-task count. Cost: 3-20 extra parent rollouts per iteration (7-40% of a screen). This restores held-out semantics for the gate at no loss of N.
- **(b) Pool with an internal holdout.** Pool P = train + val; fix a holdout H (about 40-50 tasks) never traced to the proposer; R = P \ H is used for traces and a cheap screen; confirmation runs on H. Power at confirmation equals today's val (N about 49) but the confirm is on tasks the lineage has not adapted to; P(promote) is unchanged from the shipped design. A larger H (about 70) buys power at the cost of R.
- **(c) Resampled subsets with exposure tracking.** Record exposure per task (ids named in `DIAGNOSIS.json` `clusters[].tasks`, ids in `trajectories/`, tasks in LEDGER `broke`/`fixed`); gate each candidate on a random subset of the pool weighted toward lowest-exposure tasks, and report separately the paired Δ on exposed vs unexposed tasks. The framework already has footprint masking (`gate_footprint`, default off in these specs, `algorithm_audit.md:127-139`) and DIAGNOSIS parsing (`harness.py:_validate_diagnosis_json`). Moderate effort; gives a diagnostic of adaptation rather than a guarantee.
- **(d) Shrinkage of the champion's reported score**, using the empirical-Bayes correction already in the teammate's analysis, so merged-pool search-time numbers are not read as generalisation.

Recommendation: do (a) first, because it is also the competitors' design and costs no N. Use pooling (b) only if a fixed holdout of at least 45 tasks survives.

---

## 6. Task 4: improvements, ranked by expected gain per unit of cost and effort

Ranking uses: expected change in promotions or search-time gain from the cited runs, rollout cost, and effort (S = under 50 lines, M = 50-300, L = more).

### Rank 1. Adaptive coverage handling (S, near-zero rollout cost)
- **Mechanism.** Joint coverage is limited by the parent's missing tasks, which never get retried. (i) After a baseline or a promotion, re-run only the infra-missing cells of the incumbent (3 rollouts on A) until coverage is at least `min_coverage` or retries are exhausted. (ii) Define the veto on the paired tasks relative to the tasks where the PARENT has valid data: a candidate missing tasks the parent has is an infra problem; a parent hole with the candidate valid is just a smaller paired set and the paired test is still valid on 37 tasks (the SE reflects n). (iii) Use `min_coverage` as a floor on the candidate-side coverage, plus a floor on n paired (e.g. 20).
- **Where.** `harness.py:1189-1207` (`joint_coverage`, `planned_val_ids`), call site `harness.py:3310-3318` (`coverage=jcov if sw["coverage"] == "joint"`), `gate.py:397-406`, baseline path that emits `baseline_incomplete` (`harness.py:904`). Re-measure missing cells with `evaluate_candidate(..., ids=missing, tag="seed")` (`ids` parameter exists, `harness.py:327`).
- **Expected effect.** A s2: 11 vetoed candidates screened at +0.16 to +0.35; C s1: 3-4 vetoed at z up to 2.6; A s0 cand_0001; E21-1S s2 7. Four of nine rule-P A/B/C searches change outcome (2.1). Projected mean A/C gain from about 0.10 to about 0.20 (**[UNVERIFIED]**, requires rerun).
- **Risks.** Ignoring a parent hole can hide a candidate that fixes the infra failure; bounded by the n_paired floor and by reporting both coverages. Retried baseline cells make later candidates comparable to the incumbent only if retries use fresh seeds and are flagged.
- **Test.** Unit test: parent with 3 invalid of 40, candidate fully valid, z 3 -> not indecisive. Replay A s2 `events.jsonl` offline through the gate with the new rule (cand_0006: Δ +0.351, SE 0.0796, n 37, passes). Property test that two-sided missing data still returns `indecisive`.

### Rank 2. Budget-aware screening and confirmation (S/M, saves 120-200 rollouts per straddled search)
- **Mechanism.** Per-evaluation budget check plus a reservation: before starting a screen, require `remaining >= N + 2*n_conf*N * P(pass)` (or simply `N + conf_cost`); before `_fresh_deltas`, require `remaining >= 2*n_conf*N`, else (a) shrink `n_conf` to what fits (minimum 1), or (b) mark the candidate `pending_confirm` (a distinct stage, never `confirm_reject`, never written to rejected memory), and let the final iteration spend the reserved budget confirming the best pending candidate. A truncated confirmation (coverage below `min_coverage` because of the cap) must return `indecisive`, not reject.
- **Where.** `harness.py:4637` (loop-top check), `harness.py:318-400` (`evaluate_candidate`, add a guard using `run_dir.spent.metric_calls` already updated at `harness.py:668` and `run_dir.budget.max_metric_calls`), `harness.py:3329-3338` (`_fresh_deltas`), `promotion.py:80-92, 118-123` (void -> `indecisive`), `harness.py:3350-3360` (do not append a void confirmation to rejected memory), `rundir.py:368-383` (add `remaining_metric_calls()`).
- **Expected effect.** Removes the 3 mislabelled or missing verdicts (A s0 cand_0004, A s1 cand_0002, B s0 and s2 cand_0003) and the 16-43% overruns (D rule P ran 687-785 vs cap 550). Likely turns A s0 / s1 returned champions from 0.750 / 0.692 into about 0.875 / 0.85 if they promote (**[UNVERIFIED]**).
- **Risks.** Reserving budget shortens the loop by one screen; shrinking `n_conf` lowers confirmation power (z needs about the same effect with fewer trials). Mitigate by letting the last candidate use the reserve only for the best pending one.
- **Test.** Unit test with `max_metric_calls` = screen + 0.5 * confirm cost: expect `pending_confirm`, no event that rejects, rollouts counted never exceed cap + epsilon. Offline replay of A s0 events.

### Rank 3. Remove noise from the evidence loop: n=1 ledger fix, pooled multi-draw per-task rates, shared-baseline pooling (M, 0-150 rollouts)
- **Mechanism.** (i) In `_classify_moves`, when `n_trials < 3` (per-task SE undefined), report no `broke`/`fixed` claims; replace with a count and the null-expected flip count (about 14 of 49 on B), or use a Bernoulli SE `sqrt(p(1-p)/n)` with `p` the pooled pass rate from all draws of this capability. (ii) Maintain an `evidence_pool` per capability hash (the evidence ledger already keys on `cap_hash` + `env_fp`, `eval_index.py`): all seed and incumbent draws, so trajectories and `flaky/solid/always-fail` labels shown to the proposer are based on at least 3 draws. The confirmation `__confbase` trials of the unchanged incumbent already provide these for free. (iii) For the screen baseline, use the pooled mean of all draws of the incumbent (on B: 9 draws SD 0.053 vs single draw 0.053; pooled over 3 draws, SD about 0.031), which also removes the common-baseline luck (B s1).
- **Where.** `harness.py:1690-1723` (`_classify_moves`), `harness.py:1578-1602` (`move_is_resolved`), `harness.py:1648` (`_candidate_task_impact`), LEDGER text at `harness.py:1900-1950`, `harness.py:2563-2620` (copy trajectories from multiple draws, add `pass_rates.json`), `harness.py:1224` (`_paired_deltas` to accept a pooled baseline).
- **Expected effect.** Simulation: a 3-draw baseline lifts P(promote) from 0.22 to 0.29 at +0.06 (0.52 to 0.62 at +0.10) for +150 once (+3 screens); also eliminates the lucky-baseline failure of B s1 (re-scored against pooled seed, cand_0001 is z 1.96). The ledger change stops the proposer discarding good edit classes on phantom regressions (cand_0002's removal of policy rules, B s1). No rollout cost for (i) and (ii).
- **Risks.** Pooled baselines must come from identical capability and split; an interrupted incumbent re-measure biases if selectively resampled. Keep draw seeds explicit (`trial_offset`) and log them.
- **Test.** Replay B hc s1: with a pooled baseline the null ledger should show 0 "resolved" moves; assert the pooled SD shrinks; assert LEDGER no longer prints causal lists at n<3. Simulation `/tmp/hcdiag/sim.py` extended with the pooled-baseline arm (already in the table above).

### Rank 4. Cheaper confirmation: reuse the incumbent's fresh draws and make the test sequential (M, saves about 25-40% of confirmation cost)
- **Mechanism.** The incumbent's confirmation measurement (`__confbase`) is independent of any later candidate's selection, so reuse it for all later candidates against the same incumbent instead of re-running 3 trials each time. Run candidate trials sequentially (1 trial, then 2 more only if the first fresh trial's paired mean is positive) with a pre-specified overall error (e.g. an O'Brien-Fleming or Pocock boundary at 2 looks, or an SPRT on the mean paired delta), keeping `z_conf 1.282` overall.
- **Where.** `harness.py:3326-3346` (`_fresh_deltas`: cache `held["par"]` keyed on incumbent id; evaluate candidate trials in a loop with an early stop), `promotion.py:80-127` (`confirm` gets a sequential variant), `harness.py:4660` (the incumbent's baseline for the next iteration remains the pooled draws).
- **Expected effect.** Simulation: at +0.10, cost per candidate 229 to 165 (cache) and 161 (sequential + cache), power 0.517 to 0.505 / 0.482 (about -1 to -3 points); at the null, 96 to 82 / 75. Over a 550-rollout search that is about one extra candidate screened per confirmation avoided. The per-search budget used by confirmations falls from 49% (B) to about 35%.
- **Risks.** Reusing incumbent trials correlates all candidates' confirmations through the same incumbent draws (a common-noise risk; mitigate by topping up the incumbent with one extra fresh trial each time). Sequential tests need a documented alpha-spending schedule; `analysis_plan.md` section 8 is frozen for rule P, so this must be a new named rule (e.g. P2), not a silent change.
- **Test.** Extend `/tmp/hcdiag/sim.py` (done above) to check false-promotion at null stays at or below 2%; unit tests that cached incumbent draws are not those used in the screen; replay D ruleP.

### Rank 5. Proposer context: fresh train traces, contrastive pairs, and diversity pressure (M/L, 3-20 rollouts per iteration)
- **Mechanism.** (i) Give the proposer fresh failures from TRAIN (rotating minibatch) in addition to or instead of the val traces: run the parent on k train tasks each iteration (GEPA k=3, EvoSkill 4, MH 20). (ii) Provide contrastive pairs: for each flaky task, one passing and one failing parent trace from the pooled draws (the pooled evidence of Rank 3 supplies these at no cost), plus `ledger` diffs for tasks with at least 2 consistent trials. (iii) Add a "do not repeat" signal: the framework already passes rejected-edit memory (`_init_memory_store`, `memory.py`), but B s1 repeated the same guards; add a similarity gate (token-level diff overlap with the last K rejected candidates above a threshold -> require a different cluster) in `pregate`.
- **Where.** `harness.py:2563-2620` (`_copy_step_trajectories`), `harness.py:2709` (`_inject_optimizer_context`), `harness.py:4636` (`ctx.instructions`), pregate toolkit (spec `pregate: toolkit:` in `capevolve.yaml`). Splits come from `read_splits()` (`harness.py:4600`).
- **Expected effect.** Diversity and non-val-fitting; **[UNVERIFIED]** gain. The mechanism is the common factor of GEPA, EvoSkill and Meta-Harness. Removes 80 train rollouts (13% of A) from the baseline bookend and puts them into search.
- **Risks.** More context raises proposer tokens; fresh-train rollouts compete with screens for budget (minibatch 4 is 10% of a screen); the adapters must support evaluating a candidate on a train id list (`evaluate_candidate(..., ids=)` does, `harness.py:327`).
- **Test.** A/B on one suite with matched rollouts; measure edit diversity (pairwise diff overlap of PROCESS/diff across candidates) and promotion yield; check no train id leaks into gate rollouts.

### Rank 6. Parallelism: forward workers and parallelize the baseline phase (S, wall-clock only)
- **Mechanism.** Add `workers` to the spec and forward it in `cli.py:960-966` (`--workers`); run the seed baseline with the same `workers`; set a documented default of 4 for adapters that declare themselves thread-safe. Candidate evaluation can then also fan out: run two candidates per iteration concurrently when workers allow.
- **Where.** `cli.py:960-966` (algorithm command), `skills/algorithms/hill-climb/scripts/run.py:90` (`--workers` handling), baseline phase script, `harness.py:54-127` (`DEFAULT_WORKERS`, `_resolve_workers`; env `CAPEVOLVE_WORKERS` already honoured when `workers is None`).
- **Expected effect.** A: baseline 9.3 h of 24.9 h goes to about 2.5 h (-27% wall) at 4 workers. B/C/D: **[UNVERIFIED]**: bounded by the gateway slot count (24 gpt-oss in flight shared across searches).
- **Risks.** Adapters with module-global state (documented at `harness.py:359`); results are not byte-identical to serial.
- **Test.** The existing `core/tests/test_parallel_eval.py`; compare per-task pass rates serial vs parallel on one seed.

### Rank 7. Candidate-fault sanity check before evaluation (S/M, 0 rollouts, protects D/B tool suites)
- **Mechanism.** After the proposer edits tool code, replay a small set of recorded tool-call sequences from the parent's traces against the candidate's tool module (read-only database copy) and compare outputs; reject or flag candidates whose tools raise or whose outputs change for previously valid calls. Classify errors raised by candidate tool code as `candidate` (reward 0), not `infra`.
- **Where.** The pregate toolkit (`adapters/adapter.py:pregate_toolkit` in the B/C/D projects), and the `error_kind` assignment: the `gate_warning errored_trial_policy` events show `reclassified_trials: 0` because "the adapter never sets `Rollout.metadata['error_kind']='candidate'`" (every B/D hc run); see `R/audit/silent_env_failures.md:77-106`.
- **Expected effect.** D: 107 of 6,323 non-seed rollouts (1.7%) end as `INFRASTRUCTURE_ERROR`, versus 0 of 1,406 for the seed; E20-T s0 cand_0002 12/49 (24% of tasks). Dropping them as missing inflates the paired mean on the survivors and then triggers coverage vetoes (E21-1S s2: 7 vetoes at 86-94%). Zero rollout cost.
- **Risks.** Replay needs deterministic tools; may reject edits with legitimately changed output (compare only error/no-error by default).
- **Test.** Inject a known bad tool edit (E20-T s0 cand_0002 diff) and assert the sanity check fires and the tau2 termination is classified `candidate`.

### Rank 8. Population or beam with per-task Pareto selection (L, uncertain at n=1)
- **Mechanism.** Keep a pool of promoted or near-miss candidates and choose the parent with `selection.pick(..., strategy="pareto_per_instance")` (`selection.py:195-218`, ready-made; `gepa.py` has the frontier logic), with per-task scores averaged over at least 2-3 trials.
- **Where.** `harness.py:4619` (`parent_dir = run_dir.candidate_dir(run_dir.best_id)`), `loop.py:228-255` (existing picker plumbing), the `run_step` call and the promotion path.
- **Expected effect.** **[UNVERIFIED]**. At one trial per task, per-task "wins" are dominated by noise (null flip rate 29% of tasks on B), so the frontier mostly selects noise. Use only after Rank 3 provides multi-draw per-task rates.
- **Risks.** Complexity; population evaluation cost.
- **Test.** Simulate with the B pooled per-task matrix: frontier parent vs best-parent lineage with identical candidate streams.

### Evaluated and rejected, or deferred
- **Subset or minibatch screening with successive halving (reject for B/D; conditional for A).** `subsample.py` already exists (kill-only subset screen for agent-optimize; `screen.py`) and is not wired into hill-climb. Simulation (`sim.py` last block): a 19-task kill-screen on the tasks the baseline draw FAILED passes essentially every candidate (cost 94 to 114 = +19-20 rollouts, power unchanged), because conditioning on a baseline failure makes any candidate look better by regression to the mean. A random subset of 16 tasks has SD about 0.09, far above the +0.06 effect. Subset screens only help where effects are large (A's format fix, +0.2), and there the 12-14 candidates are already cheap. Not recommended in hill-climb.
- **Parallel candidates per iteration (defer).** Best-of-2 from the same evidence is Meta-Harness's design, but with the current evidence loop (2.2, 2.3) the two candidates will be near-duplicates. Do it after Rank 5 forces distinct clusters per candidate; the wall-clock cost is neutral given Rank 6, the rollout cost doubles.
- **Merging complementary candidates (reject for now).** Merging by task wins needs reliable per-task effects; at n=1 the observed fix/break lists are the null rate (6.6/7.6 of 49). A merge of two noisy candidates adds both candidates' regressions. Revisit with 3-trial per-task rates.
- **Cached seed evaluations (accept, folded into Rank 3/4).** Seed draws from `__confbase` and from other runs of the same capability hash are already on disk; they should be pooled, not discarded.

---

## 7. Open items and caveats

- **[UNVERIFIED]** Gateway saturation for B/C/D; whether more workers shorten wall time.
- **[UNVERIFIED]** All counterfactual gains (Rank 1, 2): I replayed no gate offline; see "Test" per item.
- **[UNVERIFIED]** Held-out generalisation of any accepted edit. The stock gate promoted more (A stock +0.286 / +0.349 / +0.322 search-time versus rule P +0.171 / +0.103 / 0.000), but stock selects by max over 12 noisy single draws and has no fresh check; sealed test results are needed.
- The A hc `events.jsonl` shows an `evaluate_error` ("agent view dir ... not empty") on s2 cand_0002-0004 (3 steps lost, 5 h gap); that is a setup defect covered in `R/audit/silent_env_failures.md:14`, not a gate effect.
- `analysis_plan.md` section 8 freezes rule P as run; each change above is a new rule or a framework-defect fix and must be named as such in the paper, not applied silently to the reported arms.
- Power simulation assumes independent Bernoulli noise calibrated from 9 B-seed draws; actual tau2 noise has user-simulator correlation (some tasks flip together). Real power is probably a little lower than the table.


---

## 8. Deterministic helper code in the editable surface

Request: whenever the surface allows it, the proposer should add scripts and snippets (helper modules, verified recipes, validators, I/O wrappers) so that a fix keeps working instead of depending on the target model regenerating it. Must be benchmark-agnostic. `AD` = `/home/dev/projects2/cap-evolve-campaign/templates/adapters/spreadsheetbench/adapter.py`; `SP` = `/home/dev/projects2/cap-evolve-campaign/skills/capabilities/skill-package/scripts/abstract.py`.

### 8.1 What the runs did (measured)

**Code versus prose.** Source: `A/st/edits_by_candidate.csv` joined with the hc step records (`/tmp/hcdiag/steps.csv`). "Code" means any changed line in tool code.

| arm | surface | non-seed candidates | with code | accepted (code / prose-only) | mean Δ vs parent (code / prose-only) |
|---|---|---|---|---|---|
| A hc rule P, A hc stock | `[system-prompt]` | 16, 36 | **0 of 52** | 2, 7 (all prose) | +0.161, +0.016 |
| B hc | `[system-prompt, tools]` | 14 | 14 | 0 | -0.008 |
| C hc, C stock | `[system-prompt, tools]` | 24, 30 | 24, 30 | 2, 3 | +0.067, -0.068 |
| D E20-P (policy only) | prose | 30 | 0 | 5 | -0.053 |
| D E20-T (tools only) | code | 29 (+1 prose) | 29 | 2 | -0.006 |
| D E20-PT (both) | prose + code | 30 | 30 | 5 | +0.007 |
| D E21 rule P / 1S / NOHIST | prose + code | 10 / 30 / 30 | all | 4 / 6 / 5 | +0.075 / +0.023 / -0.005 |

So the A hill-climb proposer never wrote a file other than `prompt.md` / `task_template.md`: the surface is prose-only (`capabilities: [system-prompt]`, `S/runs/E10/hill-climb/s1/project/capevolve.yaml`) and the A adapter ignores any other file (8.4). In B/C/D, where tool code is editable, hc always touched code. Search-time gains on D (3 seeds each, selection-biased): P 0.186, PT 0.214, T 0.101 (`A/st/runs.csv`). With n=3 and noise of 0.05-0.08 per draw this does not show that code beats prose; it shows code-only (T) did not lose to prose-only.

**Which fixes stuck** (accepted candidates, diffs of `candidates/<parent>` vs `candidates/<cid>`):

| kind of fix | example | stuck? |
|---|---|---|
| Computed field in a tool result replacing model arithmetic | D E21 rule P s2 cand_0002: `get_product_details` now returns `summary` with `available_variants`, cheapest and priciest AVAILABLE item and price; C s0 cand_0003: `_flown_segments`, `agent_notes.cancel_facts` | Promoted (confirmed +0.109 / +0.100); fixed tasks robust in 2 of 3 trials (6 fixed / 0 broke on D s2 cand_0002) |
| Corrective error text that lists the valid values | D s0 cand_0006 and C s2 cand_0005: "Payment method X not found ... valid ids are [...]" | Promoted (+0.122, +0.133) |
| Guard that enforces a rule in code | C s2: at most 1 certificate / 1 card / 3 gift cards per reservation; B s1: same-item exchange guard, country `USA` guard | Mixed: C promoted; B guards were screen-rejected under noise, but their effect was never separated from the policy rules that came with them |
| Prose checklist | D s0 cand_0006 policy.md block; A reply-format block | Promoted, and gave the largest A gain (the format fix), but on A the same format fix had to be re-learned by every sampled response (next paragraph) |

**Variance across trials of the same task, seed versus champion** (3 fresh trials each, from `__confbase` vs `__conf` rollouts of promoted or confirmed candidates; script inline in `/tmp/hcdiag`). `var` = mean over tasks of the within-task population variance of reward; `flaky` = fraction of tasks with at least one differing trial.

| run, candidate | parent var / flaky | child var / flaky |
|---|---|---|
| A s0 cand_0003 | 0.067 / 0.30 | 0.044 / 0.20 |
| A s1 cand_0001 | 0.100 / 0.45 | 0.078 / 0.35 |
| C s0 cand_0003, C s2 cand_0005 | 0.078 / 0.35 | 0.067 / 0.30 |
| D rule P s0 cand_0006 | 0.086 / 0.39 | 0.068 / 0.31 |
| D rule P s1 cand_0002 | 0.113 / 0.51 | 0.082 / 0.37 |
| D rule P s2 cand_0002 | 0.100 / 0.45 | 0.100 / 0.45 |
| B s0 cand_0002 | 0.104 / 0.47 | 0.063 / 0.29 |

Champions are modestly less variable (variance down 0-40%) but 20-45% of tasks remain flaky. **Output-level variance is near total on A**: the solution code the agent finally wrote (`Rollout.output = solution_code`, `AD:1680`) is identical across all 3 trials for only 7-10% of tasks in the seed and **0%** in the champions (mean distinct codes per task 2.75 vs 3.00; A s0 cand_0003, A s1 cand_0001). That is the quantity helper code would collapse: the agent regenerates the procedure each time, so a fix expressed only as prose is re-implemented, sometimes wrongly, every trial.

### 8.2 Proposer guidance and edit taxonomy

Add to the optimizer instructions (the shared template that already holds the cluster/edit tables, rendered by `ctx.instructions`, `harness.py:4636`; edit table in `work/cand_*/PROCESS.md`). Benchmark-agnostic taxonomy, in order of preference when a surface allows it:

| class | what it is | use when | stays deterministic because |
|---|---|---|---|
| C1 helper function / module | a small pure function the agent calls (parse, locate, normalise, compute) | the same procedure appears in at least 2 failure traces, or a success trace re-derives it by hand | the call is the same bytes every trial; only the call site is stochastic |
| C2 verified recipe | a script that performs a whole multi-step transform end to end, with a `--self-check` on a synthetic fixture | a repeated multi-step procedure (the skill-package "skipped step becomes a bundled script" lever, `skills/capabilities/skill-package/SKILL.md:32-43`) | one call replaces N agent-chosen steps |
| C3 validator | a post-hoc check the agent calls before finishing (output shape, types, untouched regions) that returns a precise message | failures are "looked done, was wrong" | converts silent failure into a deterministic retry signal |
| C4 I/O wrapper | open/save/serialize in one call that preserves format and layout | failures come from lossy I/O (e.g. a library call that drops formatting) | removes a failure class by construction |
| C5 computed field / enriched error (tool surfaces) | return derived facts and valid-value lists from the tool | failures are arithmetic or guessing ids | the tool computes it (observed to stick, 8.1) |
| C6 prose rule | only when no behaviour can be codified (judgement, tone, policy) | last resort | not deterministic |

Rule text for the proposer: "If a procedure appears in at least 2 failing traces, or in 1 failing and 1 passing trace where the passing one derives it by hand, write it as C1-C5 code, add a `--self-check` that runs on a synthetic fixture you build yourself, and change the prose to one line telling the agent to call it. Do not encode any value, id, string or expected answer taken from a specific task. Do not read or write anything outside the working directory or the task's own input and output paths." Evidence for the 2-trace threshold: in B s1 the same three guards were rediscovered 8 times because the evidence loop never changed; a recurrence rule plus pooled multi-draw failures (Rank 3) makes recurrence countable. **[UNVERIFIED]** that this raises gain; no run has had a code-capable A surface.

Framework support for the threshold: `DIAGNOSIS.json` `clusters[].tasks` (schema in the PROCESS.md template, validated by `_validate_diagnosis_json`, `harness.py:~3200-3260`) already records the task ids per cluster; a cluster with at least 2 task ids and an edit with class C1-C5 is the codify-recurring-procedure signal; a cluster with at least 2 tasks and a C6-only edit can be flagged as a warning.

### 8.3 Surface manifest: how a surface declares executable files

What exists:

- Capability set per run is a spec key: `capabilities: [system-prompt]` for A, `[system-prompt, tools]` for B/C/D (`capevolve.yaml`; read at `harness.py:4401`; briefs at `harness.py:3575-3590`).
- Per-capability action policy is `<capability_dir>/policy.json`: `skill-package` has `DEFAULT_POLICY = {"allow": ["frontmatter","body","reference","script","asset","add","remove"]}` (`SP:77-85`) and `apply()` refuses edits outside the allow set or escaping the dir (`SP:234-296`); `tools` uses the same shape (`core/cap_evolve/tool_surface.py:36-44, 58-100`). "A run that must not gain new executable code drops script and add" is stated at `SP:77-80`.
- `system-prompt` has no script kind: it manages `prompt.txt` / `policy.md` / `SYSTEM.md` (`skills/capabilities/system-prompt/scripts/abstract.py:24`).
- The SpreadsheetBench A adapter reads only `prompt.md` (`AD:1129-1146`) and `task_template.md` (`AD:1066-1126`), so for A there is no executable surface today: the A skill package, once declared as `capabilities: [system-prompt, skill-package]`, would validate and diff, but the adapter would ignore `skills/<name>/`.

Proposed manifest (one optional file in the capability root, `surface.json`; absent means prose-only, today's behaviour):

```
{"executable": {"allowed": true,
                "roots": ["skills/*/scripts"],          # where code may live, relative to the capability dir
                "suffixes": [".py"],
                "entry_contract": "importable-module",   # or "cli", "tool-code"
                "runtime": "target-sandbox",             # where it executes, adapter-defined
                "max_files": 12, "max_total_lines": 800},
 "readonly_at_runtime": true}
```

The adapter owns the runtime half (how roots reach the target); the framework owns the static half (lints, self-check, size caps) and reads the manifest in `_capability_validate` (`harness.py:4017-4082`) so non-conforming files fail before any rollout. Implementation sites: new `load_surface()` beside `load_policy` (`SP:82-85`, `tool_surface.py:36`); enforce `roots`/`suffixes`/size in `SP:_validate_scripts` (`SP:500-541`); expose to the adapter via a small helper `capability_executables(ctx)` in `core/cap_evolve/adapter.py` so each adapter lists the files it should load.

### 8.4 The A adapter: can the target's Python import or run files from the capability dir?

**No, as shipped.** Chain of evidence:

1. The project adapter in `S/runs/E10/hill-climb/s1/project/adapters/adapter.py` is a socket shim (`:1-3` "Holds no gold, no credentials, no scorer"); `run_target` sends only `{"op":"run","task":...,"cand_dir": str(ctx),"seed":...}` (`:41`).
2. The daemon forwards that host path to the real adapter (`S/runs/E10/_tools/eval_daemon.py:117-121`, `_run_with_watchdog` `:68`), which is `templates/adapters/spreadsheetbench/adapter.py` (`start_daemon.sh:10`).
3. The real adapter's `run_target` (`AD:1489-1700`) uses `ctx` for exactly two reads: `_read_task_template(ctx)` (`AD:1066`, called `:1534`) and `_read_system_prompt(ctx)` (`AD:1129`, called `:1553`). Nothing else under `ctx` is read, mounted or copied.
4. The target's Python runs in a Jupyter container (`third_party/spreadsheetbench/code_exec_docker/jupyter.py:298-306`) whose only bind mount is `volumes_path` -> `/mnt/data` with mode `rw` (`:303`); `volumes_path` is the gold-free agent view (`AD:590-605`, `_data_dir` `AD:433-448`). The candidate dir is on the host and is not mounted, so `import helpers` fails in the kernel with `ModuleNotFoundError`, which `exec_code` returns as traceback text to the model (it is not a harness error).
5. Network: the container is started with the default Docker network (no `network_disabled` / `network_mode`, `jupyter.py:298-306`), so egress is possible unless the campaign sandbox blocks it (`S/baselines/EGRESS_SWITCH.txt`, not read in detail) **[UNVERIFIED]**.

**What it takes to make it work read-only and gold-free** (all in `AD`, no mount change needed):

- **Preferred: inject as text into the kernel, not through the filesystem.** After `client = sandbox.client_for(conv_id)` (`AD:1545-1546`), read `ctx/skills/*/scripts/*.py` (the manifest's roots), concatenate in sorted order (cap total bytes), and run once via `vendor["exec_code"](client, bootstrap_src)` where `bootstrap_src` defines the helpers in the kernel namespace (or writes them under `sys.modules` with `types.ModuleType` so `import helpers` works). It is read-only by construction because the target only receives text; it cannot modify the host or other rollouts' files. The kernel keeps state across rounds (the CodeAct loop already relies on it) and the replay onto test cases 2 and 3 uses the same `client` (`AD:1674`), so the helpers persist there too.
- **System prompt gets the index.** Extend `_read_system_prompt` (`AD:1129`) to append each `skills/<name>/SKILL.md` body, so the agent knows which functions exist.
- **No gold.** The text comes from the candidate dir; the optimizer cannot see gold (shim docstring). The mount allowlist still holds: `_check_mount_is_gold_free` scans only `mount/spreadsheet` (`AD:386-403`) and the input regex admits no `.py` (`AD:290`), so do NOT put helper files under `spreadsheet/<id>/`; the injection approach never touches the mount. The remaining leak path is helper code with task answers inside: lint (8.5).
- **Alternative if files are required** (e.g. the helper must be executed as a CLI): write them to the per-rollout dir `outputs/<run_tag>/_helpers` (`AD:1517-1523`, `host_out_dir`, rw leaf) and `chmod a-w`; or add a second `ro` bind in the vendored `jupyter.py:303` (a vendor change; `third_party` is pinned). Rejected as default: the shared `/mnt/data` mount is `rw` and one rollout could tamper with files seen by later ones.
- **Failure attribution.** If the bootstrap itself raises (syntax error, import of a missing module), return `Rollout(error=..., metadata={"error_kind": "candidate"})` exactly like the template check (`AD:1499-1504`), so `errored_trial_policy: fail` scores it as a measured failure (`harness.py:495-500`) rather than dropping it as missing.

### 8.5 Safety: pre-evaluation checks, task-specific-answer lint, crash attribution

Existing pre-eval hook: `_capability_validate` runs at `harness.py:3198`, before the gate and before any rollout; problems make the step indecisive via `_tamper_step` (`harness.py:3207-3213`); problems present in the parent are subtracted (`harness.py:4040-4075`). For a skill-package capability `_validate_scripts` already (a) parses every `scripts/**/*.py` (`SP:508-520`), (b) warns on stubs, (c) warns on risky imports (`RISKY_IMPORTS`, `SP:71-73`; `_risky`, `SP:482-497`), (d) runs a declared `--self-check` with a 30 s timeout, scrubbed env and blanked proxies (`SP:432-468`) and turns a failing self-check into a problem (`SP:536-538`).

Gaps to close:

| gap | evidence | change |
|---|---|---|
| Risky imports and `eval`/`exec` are warnings only | `SP:525-528` appends to `warnings` | In a surface with `readonly_at_runtime`, make `subprocess, socket, urllib, http, requests, httpx, ctypes, os.system, open(..., 'w')` outside the allowed output path a problem. Keep `eval/exec/compile/__import__` a problem unless whitelisted in the manifest |
| Self-check does not block the network or the home dir | it passes `PATH`, `HOME`, `PYTHONPATH` and sets `NO_NETWORK=1`, a hint (`SP:447-451`) | run it under a network-denied wrapper (`unshare -n` or equivalent, **[UNVERIFIED]** available on the host) with `HOME` set to a temp dir and cwd a temp copy of the package, so a script cannot read gold, `.capevolve` or other candidates |
| No smoke test on a task-shaped fixture, only `--self-check` | `SP:442-443` skips scripts without the flag | Require the manifest `entry_contract` and run each exported function on a synthetic fixture the script declares (`--self-check` builds its own data); never on task data: no gold, no val or test files are passed |
| No task-specific-answer lint | no such check exists (grep `core`, `skills`) | New `lint_task_specific(tree, source, known_ids, known_literals)` in `SP`: AST walk flags (i) string/int constants equal to any known task id (`run_dir.read_splits()` ids) or to an instruction substring from `trajectories/`, (ii) `if task_id ==` / `in {...}` dispatch, (iii) large literal tables (more than N distinct constants or lines of data), (iv) literal expected answers that appear in a failing rollout's score feedback. Problems are fatal in the validate hook (`harness.py:3198`); pass `known_ids` through `_capability_validate` (add a keyword) |
| Candidate crashes are scored as infra on tool suites | D: 107 of 6,323 non-seed rollouts end `INFRASTRUCTURE_ERROR`, 0 of 1,406 for the seed (`R/audit/silent_env_failures.md:101-106`); every hc `errored_trial_policy` event reports `reclassified_trials: 0` | Adapters must set `metadata.error_kind="candidate"` when the exception originates in capability code (traceback frame in the candidate dir or kernel bootstrap). The harness already honours it (`harness.py:313-315, 495-500`) |

Hardcoded-id lint worked example for the A surface: a helper `if sid == "50768": ...` is flagged by (ii); a lookup table of 40 `(task_id, answer_position)` pairs is flagged by (iii); a helper that opens `/mnt/data/spreadsheet/*/` globs is allowed only through the manifest's declared input accessor. Because the proposer sees val traces (2.3), (i) must include val ids, which is why Rank 5's train-trace change is also a safety measure.

### 8.6 Determinism metric

Per task `i` with `T >= 3` repeated trials of the same capability (the rule-P confirmation already produces 3 fresh trials of both parent and child, so the metric costs zero extra rollouts):

- `reward_var_i` = population variance of the trial rewards; report `mean_i reward_var_i` and `flaky_frac` = share of tasks with differing outcomes (numbers in 8.1).
- `output_agreement_i` = 1 if the normalised final artifact is identical across trials, else the modal share; for A the normalised `Rollout.output` (whitespace-collapsed solution code) and, more robustly, the hash of the saved workbook's answer-range values; for tool suites the hash of the sequence of write-tool calls with arguments. 8.1 gives the baseline: identical solution code on 7-10% of A tasks for the seed, 0% for the champion.
- `helper_use_rate` = share of solution codes that call a bundled helper, and `helper_pass_rate` = success rate of trials that did versus did not.
- Report seed versus champion (and parent versus child at each promotion), with a paired bootstrap over tasks for the difference. A good helper change should lower `mean reward_var` and raise `output_agreement` without lowering the mean reward; a change that lowers variance by lowering reward (a degenerate constant answer) is caught by the reward test.

Where: compute in `harness.py:1210-1230` (`gate_statistics`, already returns per-step stats), store in the `promotion` record from `promotion_rec` (`harness.py:3340`) and in `final.json` at `finalize` (`harness.py:4733`), then surface in `analysis/scripts/searchtime_results.py`. Needs `T >= 3` so it is available only under confirmation or multi-trial finalize.

### 8.7 Where each change goes (summary)

| change | file:line |
|---|---|
| Surface manifest, `load_surface()` | `skills/capabilities/skill-package/scripts/abstract.py:82-85` (beside `load_policy`); `core/cap_evolve/tool_surface.py:36-44` |
| Static lints incl. hardcoded-id lint, risky-import promotion to problems | `skills/capabilities/skill-package/scripts/abstract.py:482-541` |
| Network-denied, temp-HOME self-check | `skills/capabilities/skill-package/scripts/abstract.py:432-468` |
| Pass split ids to validate | `core/cap_evolve/harness.py:3198` and `:4017-4082` |
| Adapter loads helpers into the kernel, appends SKILL.md to the system prompt, attributes bootstrap failure to the candidate | `templates/adapters/spreadsheetbench/adapter.py:1129-1146, 1499-1504, 1545-1553, 1674` |
| Proposer taxonomy and recurrence rule | optimizer instruction template rendered at `core/cap_evolve/harness.py:4636`; PROCESS.md/DIAGNOSIS.json schema in the same template |
| Determinism metric | `core/cap_evolve/harness.py:1210-1230, 3340`; finalize `:4733` |
| Spec for A v2: `capabilities: [system-prompt, skill-package]` plus manifest | `S/runs/E10/hill-climb/s1/project/capevolve.yaml` (copy for v2) |

Caveats: no run has used a code-capable A surface, so every expected effect in 8.2 and 8.6 is a hypothesis. The strongest in-data evidence is indirect: tool-side computed fields and enriched errors were the edit class that promoted most reliably on C and D (8.1), and A's agent regenerates its solution code differently on 90-100% of tasks every trial.
