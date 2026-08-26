# τ²-bench airline: every run so far, and why 90% has not happened

One place for all the numbers this repository has produced on τ²-bench airline, what the honest
best is, and what would actually have to change to reach 90%. Each row says how it was measured,
because on this benchmark the measurement is the difference between a result and a coin flip.

## Every run

| # | run | optimizer | agent + user sim | split | trials | baseline | best val | sealed test | accepts |
|--:|---|---|---|---|--:|--:|--:|--:|--:|
| 1 | `run_full` hill-climb, policy+tools | claude-opus-4-6 | gpt-oss-120b | 50=50=50 (**fit, no holdout**) | 10 | 0.536 | **0.712** | 0.694 | 5/10 |
| 2 | held-out 30(=val)/20 | claude-opus-4-6 | gpt-oss-120b | 30 val / 20 test | 1 | 0.567 | 0.700 | 0.475 | — |
| 3 | agent-optimize held-out | claude | gpt-oss-120b | 30 val / 20 test | 1 | 0.500 | 0.633 | 0.550 | 1 |
| 4 | run 3 re-measured | — | gpt-oss-120b | 30 / 20 | 3 | 0.544 | 0.644 | 0.400 | 1 |
| 5 | agentopt v1 | claude | **haiku-4-5** | 26/12/12 | 1 | 0.833 | — | 0.417 | **0** |
| 6 | agentopt v2 | claude | gpt-oss-120b | 26/12/12 | 1 | 0.750 | — | 0.750 | **0** |
| 7 | agentopt v3 | claude | gpt-oss-120b | 26/12/12 | 1 | 0.667 | — | 0.500 | **0** |
| 8 | agentopt v4 | claude | gpt-oss-120b | 26/12/12 | 5 | 0.567 | — | 0.500 | **0** |
| 9 | `airline90` rounds 1–2 | claude | gpt-oss-120b | 30 val / 20 test | 3 | 0.589 | 0.678 | 0.545 | 1 |
| 10 | `airline90` round 3 | claude | gpt-oss-120b | 30 val, 2 seed blocks | 10 | 0.743 | **0.755** | not re-sealed | 0 |

**The honest best is 0.712 val on a no-holdout fit metric (run 1), and 0.755 val with a proper
control in run 10** — the latter not statistically separable from its own control at 0.743.
Five of ten runs accepted nothing at all.

## Why the numbers move around so much

Runs 5–8 look like they contradict each other — 0.833 then 0.750 then 0.667 then 0.567 baselines on
the same benchmark. They do not. **They were measured at n=1 on 12-task splits**, where a single
task is 8.3 points and the binomial SE on the mean is ≈0.13. Every one of those differences is
inside noise. Run 5's 0.833 baseline with a **0.417** sealed test is the clearest symptom: a small
split at one trial produces a val number that predicts nothing.

That is also why runs 5–8 accepted zero candidates. It was read at the time as "the edits were bad."
It was the gate being unable to resolve anything: the significance bar sat *below* the noise floor,
so accept/reject was a coin flip in both directions.

## What round 3 established about the measurement

- **The residual noise is binomial, not mysterious.** Two byte-identical arms on identical seeds
  differed by **0.0778** against a predicted SE of **0.0615** — a ratio of **1.27**. Per-task
  movement was *below* chance expectation. Earlier rounds had ruled out MoE batching, seed
  non-honoring, seed races and set-ordering by direct measurement; there was nothing left to find.
- **Concurrency is a real but secondary term.** At concurrency 25 per-task movement was 0.250,
  genuinely above the 0.1445 binomial floor; at concurrency 8 it fell to 0.100. Load adds an excess
  on top of the floor and removing it exposes the floor.
- **What the benchmark can certify.** A **+0.02** val effect needs about **n=178 per task**, i.e.
  ~5,300 rollouts per arm, ~26 h per arm at the observed throughput. Tool-surface engineering
  produces effects of roughly that size. **The instrument cannot certify what the method produces.**
- **Two-block sign agreement is the check that works.** It rejected an artifact a single block called
  positive, and refuted a per-task mechanism story of −0.50 that read **+0.20** in the second block.

## Why 90% has not been reached

Not because the edits were weak. Three measured reasons, in order of size.

**1. The ceiling is ≈0.92, and it is set by things no capability edit can touch.**
Pushing every addressable task to 0.95 gives **0.9199** — two points of slack. Three caps set it:

| task | cap | cause |
|---|--:|---|
| 7 | 0.10 | the **user simulator** emits `###STOP###` in the same message as leaked reasoning that explicitly plans to continue ("we must wait for agent's third message. Continue."), in 15 of its 27 observed failures |
| 23 | 0.667 | its measured **COMMUNICATE** component rate |
| 14 | 0.730 | same |

Reward requires *every* component in `reward_basis`, so a perfect database fix on task 23 still
leaves it near 0.67. About **4.2%** of all rollouts are lost to the simulator stopping early.

**2. What remains is agent judgement, not tool surface.** After fixing the tool-surface defects
(a search tool returning `date: null` on **942/942** results; a round-trip `destination == origin`
slip in **8/76** bookings, all in failures; docstrings losing 42% of their text on delivery), the
residual failures are *choices*: which subset of bookings to cancel, which payment method, which
date, what scope for a computed figure. Those are capability limits of a mid-tier agent model.

**3. Individually-verified gains do not compose.** Measured twice, the second time with powered arms
on both sides:

| mechanism | alone, n=40 | inside a 6-mechanism artifact |
|---|--:|--:|
| preview tool, task 10 | +0.516 (z +4.68) | **+0.80 / +0.40** — survives |
| argument repair, task 20 | +0.220 (z +2.35) | **−0.14 / −0.40** — inverts |

The six-mechanism artifact gated at **−0.0146**; a single-mechanism artifact gated at **+0.0115**.
**Fewer mechanisms beat more.** Two replicated gains against seven replicated losses, four of the
damaged tasks being high scorers no canary covered.

## What would actually get to 90%

Ordered by expected effect per unit of work. The first two change what the number *means* and are
therefore a decision for whoever owns the claim, not for the optimizer.

1. **Fix or replace the user simulator** (+~0.04 available, and it is the only free 0.04 on the
   table). It terminates episodes it intends to continue. Nothing about that measures agent skill.
2. **Raise agent capability** — a stronger model, or reasoning effort as a disclosed configuration.
   Every residual failure class is a judgement error. No prompt or tool edit reaches them.
3. **Buy the precision to see +0.02 effects.** ~5,300 rollouts per arm. If that is unaffordable, say
   so and report sign tests over pre-registered predictions instead of point estimates — 9/10
   positive gave **p = 0.0107** where no single z reached 2.
4. **Optimize the reward components separately.** COMMUNICATE caps two of the twelve weak tasks and
   is an arithmetic/scope failure (one rollout stated **56** distinct figures and still missed the
   required one). Nobody has aimed an edit at it.
5. **Integrate sequentially, always.** `integrate.py` with `--canary-auto`, one branch at a time.
   The −0.0146 artifact is what a one-shot merge of individually-good branches produces.

## What would make cap-evolve better at this class of problem

Each of these came from a failure observed in these runs, not from taste.

- **Report the resolvable effect size next to every gate verdict.** The gate knows `n`, the per-task
  rates and the task count; it can compute `2·SE` and say "this round can resolve ±0.05" *before*
  the driver reads the delta. Four runs of null results would have been interpretable immediately.
- **Make the null control mandatory and plural.** `round.py` now builds two byte-identical replicates
  by default; earlier runs discovered the need for them reactively, after three failures.
- **Require two seed blocks for an accept.** One block called a null positive in this very round.
- **Select canaries mechanically from the whole suite** (`--canary-auto`), lowest rate first. A
  hand-picked set near the mechanisms missed four damaged high scorers.
- **Carry a mechanism ledger with supersede.** 208 rows here, 8 of them retracting earlier claims.
  Without `--supersedes`, a disproved finding stays `verified` and the next round builds on it.
- **Treat a benchmark's own evaluator as part of the contract.** A read-before-write guard was
  *unmeasurable* because τ²'s replay skips non-mutating tools — worth knowing before spending
  rollouts, and the kind of constraint an adapter should surface.
- **Cost the target before accepting the goal.** Sum `1 - rate`, subtract per-component caps, and
  state whether the target is reachable. A target never costed against measured headroom is a wish.

**Status (issue #401 — implemented in `core/cap_evolve/` and the skill's scripts):**

- `gate.decide()` now returns `resolvable_effect_size` (`2·SE`) on every paired/significant
  verdict — `core/cap_evolve/gate.py`.
- `round.py`'s two-byte-identical-control default (`--control-replicates 2`) was already in
  place; the sign-agreement check across those replicates (`verdict_stable`) now runs
  unconditionally whenever there is more than one control block, not only under
  `--gate-against control` — a parent-gated round (the default) is now covered too.
- `--canary-auto` (mechanical, lowest-rate-first canary selection) and the mechanism ledger's
  `--supersedes` were already implemented (`integrate.py`, `mechanisms.py`).
- `cap_evolve.constraints.cost_target()` costs a `target_val_score` against measured per-task
  ceilings; wired into `spend.py --ceiling-file` so a target is costed before the loop keeps
  chasing it.
- A `/goal`-style enforcement mechanism now exists: `plugins/cap-evolve/hooks/goal_reminder.py`
  (a `PostToolUse` hook) re-injects the parsed `stop_condition` predicates + measured
  spend/wallclock/protected-tasks state every `CAPEVOLVE_GOAL_CADENCE` Bash calls (default 12)
  in an agent-mode run, independent of whether the driving agent remembers to call `spend.py`.
- `round.py` now logs an `agent_optimize_compliance` event per candidate recording whether
  `screen.py` ran before that candidate's full-val eval; `dashboard.py`'s `reduce_run` surfaces
  it under `algo_extra["compliance"]` as its own distinct entry.
- The user-simulator `###STOP###` + leaked-continuation-reasoning bug (row 7 above) is now
  detected from the message trace in the adapter (`examples/tau2_airline/adapters/adapter.py`
  and the shared `templates/adapters/tau2_bench/adapter.py`) and the affected rollout is marked
  as infra noise rather than scored as an agent failure — tau2-bench itself is an external,
  unvendored package, so the fix lives on the cap-evolve side of that boundary.
- **Real end-to-end validation:** the implementation sandbox had no network egress, but a
  network-connected run against real `aws/gpt-oss-120b` rollouts (via `examples/tau2_airline`,
  a 2-task/1-trial smoke spec) confirmed the `resolvable_effect_size` annotation above is
  produced by an actual gate decision, not just exercised by a unit test — the run's
  `rejected.jsonl` recorded a paired-mode verdict correctly annotated with `2·SE`. The
  candidate was correctly rejected at that sample size (n=2, SE=0.5), consistent with this
  doc's own noise-floor analysis. The full 30/30/20 `tau2_airline` benchmark run is left as
  follow-up work once that dedicated pass is scheduled.
