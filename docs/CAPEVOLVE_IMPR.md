# cap-evolve: proposed improvements, from the AppWorld runs

Generic changes to cap-evolve's defaults, skills and intake, each rooted in the AppWorld smoke-test runs
(`cape_hc_s0`, `cape_hc_s1`, `cape_hc_s2`). The ACE run's **train** steps are used for comparison. The
aim is a higher final TGC and SGC on other benchmarks too, not on AppWorld alone.

**Evidence rule.** Every number below comes from **search-time data only**: rollouts on the official
`train` and `dev` splits (cap-evolve's train = val = 147 tasks), gate events, optimizer transcripts, and
ACE's 90 online train steps. No test_normal result, ground truth or sealed test was used to choose or
size any proposal. The test window exists, but deliberately plays no part here. The estimated gains are
therefore **search-set** gains, and they will shrink on held-out data, since search val overstates test
by about 20 points in these runs.

Ranked by expected effect. P1–P3 are the strongest.

---

## P1. A noise-aware gate: lower `k`, and re-measure near-misses instead of rejecting them

**Evidence (search set, 147 tasks, 1 trial).**
- Re-scoring is very noisy. Five sibling candidates of `cape_hc_s1`, all children of the same parent and
  all with small edits, each changed the outcome of **33–39 of 147 tasks** (22–27%), while their net Δ was only
  −4 to +5. An independent re-run of the unchanged seed agreed on only 6 of 10 dev tasks (acceptance probe A8).
- So the paired SE is about 0.037–0.048 at n = 147, and **at k = 1.0 a real gain smaller than about 4–5 points
  cannot be accepted.**
- 18 gate decisions across the three runs, as z = Δ/SE:

  | run | rejected near-misses (0 < z ≤ 1) | z of those |
  |---|---|---|
  | `cape_hc_s1` | 2 | +0.17, +0.87 |
  | `cape_hc_s2` | 3 | +0.48, +0.90, +0.93 |

  No accepted candidate had z < 1.2, and no candidate with z < 0 would pass at any k ≥ 0.
- In `cape_hc_s2`, rounds 5 and 6 both reached val **0.823** against the champion's 0.789 (+3.4 points each, the
  same Δ twice from two different edits), and both were rejected. In `cape_hc_s1`, round 6 reached 0.803 against
  0.769 and was rejected, so 5 of 6 rounds ended with nothing kept.
- The cost of being strict is large here: the search set has **82 of 147 tasks that flip** across candidates,
  so the next round always starts from a noisy parent.

**Change (generic).**
1. Lower the default `gate_k_se` from 1.0 to **0.5**. At k = 0.5, rounds s2 r5 and r6 and s1 r6 are accepted;
   none of the 18 decisions with z < 0 changes.
2. Add a **confirm step**: when 0 < z ≤ k_confirm (default 1.0), re-score both the parent and the
   candidate with a new trial seed before deciding, and gate on the pooled 2-trial paired Δ. Accept if pooled
   z > k. This halves the variance of exactly the decisions that are close, at a cost of 2 × |val| extra
   rollouts per near-miss: 3 of 6 rounds in `cape_hc_s2`, about 40% more rollouts per run.
3. Expose `gate_k_se` and `confirm` in intake, with the noise estimate (sibling flip rate) printed after
   the baseline. Then the user sets k against measured noise, not by habit.

**Expected effect.** In `cape_hc_s2`, the champion would have become round 5 or 6 (val 0.823) instead of round 4
(0.789): **+3.4 points on the search set**. Compounding helps more, because later rounds would build on the stronger
parent. A lower k also raises the false-accept rate. The confirm step is what keeps that bounded. Without it, k = 0.25 would also have
accepted `cape_hc_s2` round 2 (z = +0.48).

## P2. Run several candidates per round, and keep the best (beam or population), not a single child

**Evidence.**
- The union of the six `cape_hc_s2` candidates passes **94.6%** of the search set. The best single
  candidate passes 82.3%, and the champion 78.9%.
- The candidates fix *different* tasks (18–26 fixed, 12–18 broken per round, against the same parent).
  So most of what one round learns is thrown away when its child is rejected.
- Hill-climb has one child per round, so 4 of 6 rounds in `cape_hc_s1` and 3 of 6 in `cape_hc_s2` produced nothing
  usable.

**Change (generic).**
1. Default **N = 2–3 candidates per round** from the same parent. They can come from different focus clusters or
   different improvement types (code vs prompt vs notes); the optimizer already fans out subagents, so this costs
   no more optimizer time.
2. Gate each candidate with P1 and keep the best. Optionally, a **merge** step tries the union of the accepted
   candidates' non-conflicting edits. The `agent-optimize` algorithm already has a merge operator; this makes it
   available to hill-climb.
3. Spend this budget instead of more rounds: 3 rounds × 3 candidates instead of 6 × 1, at about the same rollout
   cost.

**Expected effect.** On the search set, keeping the best of three at each round, without merging, would have led
`cape_hc_s2` to 0.823 by round 5 (P1 alone would do that). Merging targets the 94.6% ceiling. A realistic gain is
**+3 to +6 points on the search set**.

## P3. Build learning from *every* round's trajectories, not only the current parent's

**Evidence.**
- ACE, which reads each trajectory once and accumulates bullets, reached a **72.2% online train success**
  over its 90 train steps: 70.0% in the first 30, then 70.0%, then 76.7%. That's with a stronger Curator, on the
  same agent.
- cap-evolve's champion of `cape_hc_s2` scores 76.7% on the same 90 train tasks.
- But cap-evolve's optimizer sees only the **current parent's** 147 trajectories in each round (`./trajectories/`
  holds only `cand_0004`'s rollouts in round 6). It never sees the rejected children's rollouts, even when a child
  fixed 17–21 tasks the parent fails. It only sees those children's diffs, and those are **truncated at 8,000
  characters** (`_diff_capabilities(max_chars=8000)`). In `cape_hc_s2`, round 5's diff was cut off. The round-6
  optimizer wrote in its journal that it had to *rebuild* round 5's mechanisms "because its diff was truncated".

**Change (generic).**
1. Give the optimizer **per-task evidence across all candidates so far**: for each task, which candidates passed
   it, and the shortest passing trajectory. That is already on disk under `rollouts/val/`. This is ACE's main
   advantage (learning from many attempts) without changing the gate.
2. Raise or remove the 8,000-character diff cap. Store full diffs in `prior_iterations/` and summarize rather
   than truncate.
3. In the briefing, list "tasks fixed by a rejected candidate" as **free wins** for the next round.

**Expected effect.** It targets the 82 flipping tasks directly. Recovering a third of a typical rejected child's
fixes (17–21 per round) is **+3 to +5 points on the search set**, and it compounds with P2.

## P4. Make tools the main improvement surface: add, remove, rewrite and redescribe tools (owner's suggestion)

**Evidence.**
- In `cape_hc_s2`, tool code dominated the accepted edits: helper lines changed per round were 195 (r1),
  331 (r3) and 224 (r4) in the accepted rounds, against 11–45 prompt lines.
- The helpers are heavily used. Every one of the 147 search tasks called at least one helper (`finish_task`
  147/147, `peek` 137, `fetch_all` 129, `api_help` 97).
- Tasks that use the composite helpers pass more often: `apply_each` 0.93, `pay_venmo` 1.00, against 0.79 overall.
- Tool **quality** problems are visible on train:
  - `api_help` raised errors in 17 calls and `fetch_all` in 10;
  - `extract_ids` is used on 8 tasks but they pass only 0.25, `save_file` 0.43 (7 tasks), `venmo_with` 0.56 (9);
  - the helper module hit the 400-line lint cap from round 3 on (400, 396, 400, 397 lines), so later rounds could
    only *replace* tools, not add them.
- Prompt-only edits had small effects: `cape_hc_s1` round 3 changed mostly prose, and its net was −4.

**Change (generic, in the `tools` capability skill and the intake default).**
1. Make **"tools first"** the default edit order in the optimizer briefing:
   - (a) fix the **existing tools with the most errors**, from a per-tool error and pass table that the harness
     computes and puts in the briefing (call count, error count, pass rate of tasks using it);
   - (b) **remove or merge** tools that are unused or that tasks using them fail (a low pass rate over ≥ 5 uses);
   - (c) **add** composite tools for multi-step write actions (the `apply_each` / `pay_venmo` pattern);
   - (d) **improve tool descriptions**: the docstring, a usage example, the error text;
   - only then (e) the prompt.
2. Give tools a **budget instead of a line cap**: count tools and description size against the token budget the
   target agent reads, and let the optimizer trade prompt text for tools.
3. Run a **tool test harness** before scoring: the per-tool unit checks the optimizer writes, run on recorded
   train calls (cap-evolve already has `helper_smoke` for `agent-optimize`; enable it for hill-climb). A tool that
   raises on a recorded call is rejected before any rollout.

**Expected effect.** If the 4 weak or error-prone tools above were brought to the level of the overall pass rate,
the tasks using them (about 30 overlapping tasks) would gain **+2 to +4 points on the search set**. The ranking
table also stops rounds from re-adding tools that had already failed.

## P5. Use partial credit as the learning signal, while keeping the binary gate

**Evidence.**
- The champion passes **91.8% of individual requirement checks** across the search set, but only 78.9% of tasks.
  Of its 31 failing tasks, **27 passed at least half of their checks**.
- The briefing calls these "always-failing" tasks: 40 in round 4 of `cape_hc_s2`, which mixes near-misses with
  real hard failures.

**Change (generic).**
1. Rank the failure clusters in the briefing by **missing checks**, and mark the tasks that are one check away
   (`pass_count = num_tests − 1`) as top priority. Many of them are single-rule fixes.
2. Optionally use `pass_count / num_tests` as a **secondary** gate metric to break ties between candidates of equal
   reward (a shown metric). The binary reward stays the gated one, as AppWorld scores it.

**Expected effect.** Directs the optimizer at the cheapest wins. **+1 to +3 points on the search set**, mostly from
near-miss tasks.

## P6. More trials on the search set where noise is highest, instead of more rounds

**Evidence.**
- At 1 trial, rejection rests on noise (P1). 82 of 147 tasks flip.
- Round 6 of each run added nothing that was kept. So the last round's budget, 147 rollouts, bought nothing.

**Change (generic).**
1. Make **`num_trials: 2` on flipping tasks only** a default: tasks that flipped across ≥ 2 candidates so far get a
   second trial each time they are scored. On this benchmark that is about 82 extra rollouts per evaluation. The
   paired SE drops by about 30%.
2. Show intake the measured noise after the baseline, and recommend trials vs rounds from it.

**Expected effect.** No direct gain, but it lets P1 run at k = 0.5 with fewer false accepts. **+1 to +2 points** as
an enabler.

## P7. Make intake fix the optimizer's subagent model and inherited settings

**Evidence.** In every cap-evolve run, the optimizer's subagents ran on a model the spec never named (Opus 5.5,
inherited from the user's `CLAUDE_CODE_SUBAGENT_MODEL`; 220–403 subagent messages per run). The effort and thinking
settings were also inherited.

**Change (generic).** Intake writes `optimizer_subagent_model` (default: the same as `optimizer_model`), effort and
thinking into the spec. `run-optimizer` sets them explicitly, overriding user settings, and logs the models actually
used per role into the run's events.

**Expected effect on reward:** none directly. It makes comparisons valid and runs reproducible. It also removes
a hidden variable from P1–P6's measurements.

## P8. Stop early when the search set is near its ceiling, and spend the rest on confirmation

**Evidence.** In `cape_hc_s1`, five rejections in a row followed round 1 (val 0.769). Each round cost about $5–11 of
optimizer spend and 147 rollouts. `stall: 0` was set, so the run could not stop.

**Change (generic).** Default `stall: 3`, together with P1's confirm step: after 3 rejections in a row, re-score the
champion and the best rejected child on 2 more trials, and keep the better one. Then stop.

**Expected effect.** Saves budget, and recovers wrongly rejected children: +1 to +3 points when they are real.

---

## Summary

| # | change | where | expected gain (search set, pts) | cost |
|---|---|---|---|---|
| P1 | `gate_k_se` 1.0 → 0.5 + confirm re-score for 0 < z ≤ 1 | core gate, spec defaults, intake | +3 to +5 | +~40% rollouts on near-misses |
| P2 | 2–3 candidates per round, keep best (+ optional merge) | hill-climb algorithm | +3 to +6 | ~same if rounds are cut |
| P3 | cross-candidate per-task evidence; untruncated diffs | harness briefing, memory | +3 to +5 | small |
| P4 | tools-first editing, per-tool error/pass table, tool budget, tool smoke tests | tools skill, intake, harness | +2 to +4 | small |
| P5 | partial-credit-ranked failure clusters, tie-break metric | harness briefing, adapter contract | +1 to +3 | none |
| P6 | extra trial on flipping tasks | evaluation planning | +1 to +2 (enabler) | ~+55% rollouts per eval |
| P7 | explicit subagent model and settings | intake, run-optimizer | 0 (validity) | none |
| P8 | `stall: 3` + confirm-then-stop | spec defaults | +1 to +3 | saves budget |

These gains overlap and do not add. **P1 + P2 + P3 + P4 together** are the strongest set: about **+6 to +10 points
on the search set**. Search val overstated test by about 20 points in these runs, so held-out gains will be
smaller. The plan is to measure them in one interleaved test window against the current defaults, as the
smoke test did.

**How to validate each proposal without touching test data:** replay the existing `cape_hc_s1` and `cape_hc_s2`
rollouts through the new gate (P1, P8; that's what the tables above do). Run the remaining proposals on AppWorld
train ∪ dev under the same 1,050-rollout budget, comparing search-set curves. Then run **one** held-out window
for the final comparison.
