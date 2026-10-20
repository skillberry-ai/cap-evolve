# v6_t2_e1 — task-by-task optimization on the v6 feedback split

Purpose: the T arm counterpart to `v6_g2_e1`, so T and G can be compared on the same 200-task
release and the same published split. This first round optimizes 10 tasks. Merging (v6_t4) is
decided after these finish.

## Tasks (10)

The 10 lowest-scoring feedback tasks under the Seed (v6_g2_e1's own 10-trial Seed sweep). Excluded:
tasks that `classify_fast()` routes to a specialist lacking a tool the task's verifier requires.
Those are unreachable by skill edits (cloud-304, cloud-315, platform-071, icinga-013, cloud-074).

| # | task | Seed (10 trials) |
|--:|---|--:|
| 1 | platform-158-lab-instances-outside-default-region | 0.464 |
| 2 | cloud-057-cloudtrail-select-only-refusal | 0.500 |
| 3 | platform-121-near-miss-pick-partner-repo | 0.500 |
| 4 | cloud-058-malformed-account-id | 0.600 |
| 5 | cost-407-aws-historical-query-came-back-org-wide | 0.600 |
| 6 | platform-116-timeout-headroom-from-history | 0.649 |
| 7 | icinga-215-ack-comment-author-and-expiry | 0.669 |
| 8 | icinga-204-downtime-window-expired | 0.690 |
| 9 | cost-408-three-cloud-total-gcp-query-failed | 0.734 |
| 10 | platform-004-events-then-config | 0.760 |

platform-004 is the Rule 4 / rhpds/parsec PR #57 task: the paper's running example. It gives a
direct v6 T-versus-G comparison on that edit.

## Configuration: same as v6_g2 except where single-task requires otherwise

| setting | v6_g2_e1 | v6_t2_e1 (per task) | why |
|---|---|---|---|
| target / optimizer model | claude-sonnet-4-6 / claude-opus-5 | same | — |
| seed bundle | `artifacts/v6/v6_g2_e1/seed` | same (byte-verified) | — |
| benchmark tree, verifier revision, harness | `rhdp-parsec/v6_2026-10-16`, v6 profile | same | — |
| evaluation dispatch | v6 lane queue on CCC | same; one shared queue for all 10 | — |
| algorithm | hill-climb | hill-climb | — |
| optimizer input, iteration 1 | Seed F trajectories (all 67 tasks × 10) | Seed trajectories of THIS task × 10 (reused from v6_g2_e1, no new eval) | same evidence per task |
| optimizer input, later iterations | Seed traces + prior diffs; other F traces readable on request | current champion's 5 trials + the last rejected candidate's 5 trials on this task, handed over (option b) | decided 2026-10-20; difference from G stated in the paper |
| split | pooled F/C/test, P2 gate on hidden C | train = val = this one F task; no C, no test per task | the per-task gate can only see its own task; held-out evaluation happens after the merge |
| gate | P2 group-sequential on C | paired hill-climb gate on this task (5 fresh trials vs the incumbent's) | single task |
| trials per candidate evaluation | screen 1/task, C ≈ 3/task | 5 | enough to separate a real fix on one task from noise; half the cost of 10 |
| max_iterations / stall | 6 (author-stopped) / 0 | 5 / 2 | v4 T2 used 3; raised to 5 (2026-10-20) for more room per task |
| stop_at_reward | — | 1.0 | a task stops as soon as a candidate scores 1.0 |
| finalize (per-task test) | true (sealed test, once) | false: no per-task test | train = val = test is one task, so a per-task "test" would only re-measure val; held-out evaluation is done on the merged bundle |
| budget | $2,500 / $600 optimizer | $50 / $20 optimizer per task | matches v4 T2 |
| optimizer brief | v6 multi-task brief | v6 brief adapted to one task: no mention of a later merge or of hidden tasks; keeps the "fix the general mechanism, never hard-code instance values" guidance | describes the single-task setting truthfully, without steering edits toward a merge |

Comparison with v6_g2 on held-out data happens after the merge: the merged bundle is scored on
C (4 trials per task, like G's re-measurement) and once on test (66 × 10), the same protocol as
G's cand_0005.

## Batch 2 (launched 2026-10-20)

Every other feedback task the Seed scores below 0.95 that the fast-path router does not misroute:
24 tasks (platform 14, icinga 6, cost 3, cloud 1; Seed 0.760–0.946). With batch 1 this covers all
34 reachable feedback tasks below 0.95. Of the 42 below 0.95, 8 are excluded as routing-gap tasks:
cloud-074, cloud-304, cloud-310, cloud-315, cost-410, cost-419, icinga-013, platform-071. Same
configuration as batch 1. Worker cap 60 for this launch, to leave free CCC nodes for others.
Three batch-2 tasks were also T2-optimized in v4 (platform-005, -007, -032). They are re-run, not
reused, because v6 revised the shared verifier.

## What has to be built

1. `examples/parsec/v6_t2/scaffold_projects.py`: one project per task under
   `.capevolve/v6_t2_e1_<task>/project/` (seed copy, byte-verified; `capevolve.yaml`;
   `split_ids.json` with train = val = test = [task]; `public_tasks.txt` = [task]; adapters →
   `examples/parsec/v6/adapters`; optimizer → `examples/parsec/v6_t2/optimizer`).
2. `examples/parsec/v6_t2/optimizer/INSTRUCTIONS.md`: the single-task brief.
3. Seed-trace reuse. Built: the scaffold writes `.capevolve/v6_t2_<suite>_<task>/prior/`, a
   minimal prior run holding v6_g2_e1's 10 Seed feedback trials of the task as
   `rollouts/val/<task>__seed__t0..9.json`. Its `baseline.json` is computed by cap-evolve's own
   `split_result_from_rollouts`. The project's `reuse_baseline:` points at it, and cap-evolve's
   stock `--reuse-baseline` copies those trials in and skips the Seed evaluation.
4. Option (b) trajectories. Built:
   - Champion half: cap-evolve's `_copy_step_trajectories` copies the *current best's* val trials
     into `trajectories/` (the Seed's 10 until an accept, then the champion's 5). Stock behavior.
   - Rejected half: `stage_rejected.py` copies the most recently rejected candidate's val trials
     into `trajectories/rejected/` (a directory cap-evolve already excludes from the capability).
     It is run by `claude_t2.sh` before `claude`. The v6_t2 registry (`registry.yaml`, generated
     by `build_registry.py`) differs from the stock one only in the claude-code row's
     executable; run_t2.sh points CAPEVOLVE_OPTIMIZER_REGISTRY at it. The row keeps its name, so
     the harness gives the optimizer the same native skills, CLAUDE.md and parallel note as v6_g2.
     No framework change.
5. `examples/parsec/v6_t2/run_t2.sh`. Built: one LSF driver per task, all submitted at once, all
   on ONE shared lane queue (`_run/v6-queue/v6_t2_<suite>`). The worker cap defaults to
   tasks x num_trials (50 for 10 tasks), so every task can evaluate at the same moment without
   waiting for a lane. v4 T2 ran its tasks one after another on a single lane, so it has no
   parallel setting to copy; per-task settings follow v4, and parallelism is new here.
   Item ids carry a batch hash, so drivers cannot collide; workers are counted per queue name,
   so the cap is shared. `V6_SHARED_QUEUE=1` keeps a finishing driver from stopping the pool.
6. A preflight: seed byte-identity, the 10 task dirs present, credentials file present, a
   dry-run scaffold.

## Cost and time (estimate, not measured)

v4 T2's per-task cost: mean $20.82, median $13.83 (range $1.39–$43.57). Ten of the hardest
reachable tasks are likely nearer the mean: about $150–$250 in total, mostly optimizer.
Elapsed: about 3–4 h with all 10 in parallel (each task's optimizer loop is serial; every task
has its own 5 lanes available).

## Not decided yet
- Merge procedure (v6_t4): static union first (cheap, one evaluation), then one-at-a-time with
  a check only if the union regresses. Decided after the 10 finish.
