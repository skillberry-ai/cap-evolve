# v6 audits: the low control batch, platform-131, and the sealed-test infrastructure

Three read-only audits of the Global run (`v6_g2_e1`, final bundle `cand_0005`). Each uses recorded
trials only; nothing was rerun. The scripts are `examples/parsec/v6_t4/audits/` on `main`
(skillberry-ai/cap-evolve#904); each prints the numbers quoted here.

Throughout, **recorded** means read from a stored artifact, and **inference** means a conclusion
drawn from recorded facts. Raw run directories are not committed; paths below are in the
`parsec-intake_v6` worktree.

## Summary

| Question | Answer |
|---|---|
| Was the 0.401 control batch an infrastructure failure? | Yes in symptom (recorded); the cause is inferred to be the simulator's backing service being down. |
| Did it decide an acceptance? | Yes: cand_0002 passes the gate with it and fails without it. |
| Is the final test result affected? | No. The sealed test is independent of every gate batch. |
| Does the final bundle depend on cand_0002? | It is a descendant (recorded). Performance dependence is not established. |
| Is `platform-131` a clean agent regression? | No. It is a verifier–tool contract disagreement plus a smaller, genuine completion shortfall. |
| Are sealed-test results sensitive to infrastructure errors? | Not to confirmed ones (+0.0369 → +0.0364). Simulator timeouts hit 18% of trials in both arms and the delta is sensitive to dropping them. |

---

## 1. The low Seed-control batch

### 1.1 Recorded: the control batches
Hidden validation split, 67 tasks × 1 trial per batch. Source:
`.capevolve.sealed/run_g2_e1/rollouts/confirm/*__<tag>__t*.json`, with each record's `trial_dir`
pointing to the trial's `agent/agent.jsonl`.

| Batch | Used for | Valid / errored | Mean ± SE | "Internal error generating mock response" results |
|---|---|---|---|--:|
| r001 seed ctrl_0 | cand_0002 | 65 / 2 | **0.4006 ± .025** | **163** (in 55 of 67 trials) |
| r001 seed ctrl_1 | cand_0002 | 64 / 3 | 0.7477 ± .035 | 0 |
| r001 seed ctrl_2 | cand_0002 | 63 / 4 | 0.8019 ± .034 | 5 |
| r001 seed ctrl_3 | cand_0002 | 64 / 3 | 0.7595 ± .037 | 1 |
| r002 cand_0002 ctrl_0–3 | cand_0003 | 65, 66, 65, 65 | 0.773, 0.789, 0.793, 0.772 | 0, 0, 7, 1 |
| r004 cand_0002 ctrl_0–3 | cand_0005 | 63, 64, 65, 66 | 0.763, 0.771, 0.814, 0.764 | 3, 16, 2, 0 |

The four r001 batches measure the same Seed on the same 67 tasks under the same configuration, so
they are comparable evaluations. Batch 0 ran 2026-10-16 21:47–22:27 UTC (40 min); the others ran
the next 3 hours.

**Evidence that batch 0 was broken** (recorded):
- Paired by task against the other three batches it is 0.373 lower (SE .032), and below them by
  more than 0.3 on 44 of 61 common tasks.
- Mean tokens per trial 36.0k against 45.8–48.8k; mean cost $0.118 against $0.151–0.160.
- 222 of 299 tool results were errors, against 101 of 391 and fewer elsewhere.
- The visible text of the error bodies is an OpenShift page: "Application is not available. The
  application is currently not serving requests at this endpoint."

**Inference:** the service behind the simulator was down or restarting for about the first 40
minutes. No log records the cause. The harness does not treat tool-result errors as infrastructure-
invalid (only trial-level errors: 2 of 67 here), so the trials were scored at their low rewards.

### 1.2 Recorded: the gate and its replay
The production code path is `core/cap_evolve/evaluator.py` `sequential`, which uses
`racing.gs_decide`. It is a group-sequential test: the candidate's rollouts on the validation tasks,
in seeded passes, are compared with each task's mean in a concurrently measured incumbent control
(4 trials per task intended), paired by task. The SE is the larger of a model-based pooled SE and
the spread of per-task deltas. The boundary is O'Brien–Fleming-type, `c·sqrt(n_max/n)`, with five
looks (16, 33, 67, 133, 200), a minimum gain of 0.02, and futility bounds (−0.5, 0, 0.3, 0.7).

Replaying those functions on the recorded trials reproduces all three recorded verdicts
(cand_0002 look 4, n=128, +0.1003, z 5.14; cand_0003 look 5, n=194, +0.0185, z 1.03; cand_0005
look 5, n=195, +0.0386, z 2.45). The boundary constant that reproduces them is 1.6 (`P2Params.gs_c`);
`racing.GS_C` (2.03) is only the module default.

cand_0002 under other controls (candidate trials unchanged):

| Control | Decision |
|---|---|
| As run: all four batches (mean 0.677) | **accept** (look 4, z 5.14 vs boundary 2.00) |
| Excluding batch 0 (batches 1–3, mean 0.771) | **reject** (look 4, +0.005, z 0.26) |
| Batch 1 alone | no decision by look 4 (z 1.01) |
| Batch 2 alone | reject (look 1, −0.082) |
| Batch 3 alone | reject (look 4, +0.020, z 0.64) |
| Batch 0 plus any one healthy batch | accept (look 3, z 3.8–4.5) |

No precomputed Seed estimate existed at that time. These are replays on recorded data, not new
experiments.

### 1.3 Recorded: lineage and what survived

| Candidate | Parent | Outcome |
|---|---|---|
| cand_0001 | Seed | rejected, look 2 |
| cand_0002 | Seed | **accepted**, look 4 (used batch 0) |
| cand_0003 | cand_0002 | rejected, look 5 |
| cand_0004 | cand_0002 | killed at rung 1 |
| cand_0005 | cand_0002 | **accepted**, look 5 (z 2.45, against healthy controls) |
| cand_0006 | cand_0005 | killed at rung 1 |

cand_0005 is a direct descendant of cand_0002. In a line-level diff, 94% of cand_0002's 7,979
added words appear verbatim in cand_0005; 64% of cand_0005's 11,758 added words come verbatim from
cand_0002, and 36% (4,254 words) were added after it. cand_0005 dropped 475 of cand_0002's words,
mostly in `shared_context.md`. Edit survival is not evidence that an edit contributed to
performance.

### 1.4 Recorded: the later remeasurement of cand_0002
Tags `final__champion` and `final__seed`, 4 trials per task over the 67 validation tasks, run back
to back on 2026-10-17 (03:37–05:06 and 05:22–06:54 UTC). It measured **cand_0002, not the final
bundle**. Valid trials 264 / 264, errored 4 / 4. cand_0002 0.8037 against Seed 0.8212, paired by
task: **−0.0175, SE 0.0232, bootstrap 95% CI [−0.066, +0.025]**.

It is the same split and configuration but not concurrent with the gate, so it is roughly
comparable. It shows that the batch-0-driven accept did not reproduce; its CI includes zero, so it
does not show that cand_0002 was harmful. (A "0.8046" figure appeared in an earlier draft; the
recorded values are 0.8037 per task and 0.8021 per rollout.)

### 1.5 Separating the claims
1. *The final bundle improves held-out test reward:* supported by the sealed test, which ran
   afterwards on the frozen bundle and shares no trial with any gate batch.
2. *The gate reliably selected improving candidates:* weakly supported in this run. Its one
   unusual accept rested on a failed batch and did not reproduce; cand_0005 passed against a healthy
   control.
3. *A particular intermediate edit caused the test gain:* not established.

The gate is a single-candidate group-sequential rule with a nominal false-accept rate of about 0.05
per candidate under a well-behaved control. It does not correct for evaluating several candidates
on the same tasks, it does not detect a failing control batch, and it adds no allowance for
batch-to-batch variation beyond its pooled SE.

---

## 2. platform-131

### 2.1 Recorded
Source: `rollouts/test/platform-131-…__FINAL{,_seed}__t*.json` and each trial's
`verifier/reward-detail.json`.

| | Valid trials | Per-trial rewards | Mean |
|---|--:|---|--:|
| Seed | 10 | 1.00 ×9, 0.85 | 0.985 |
| cand_0005 | 10 | 0.56 ×8, 0.71 ×2 | 0.590 |
| Merge by order | 5 | 0.85 ×3, 0.86 ×2 | 0.854 |
| Smart merge | 5 | 1.00 ×3, 0.86 ×2 | 0.944 |
| Non-conflicting | 5 | 1.00, 0.86 ×2, 0.44 ×2 | 0.720 |

The task weighs tool calls 0.3 and the answer 0.7. The −0.395 splits into 0.255 (tool calls: 0.950
→ 0.100) plus 0.140 (answer: 1.000 → 0.800).

- **Seed:** all 10 trials pass `cluster: merlin` to the subject lookup, and all 10 name job 5562091;
  9 of 10 then opened it with `query_aap2 get_job_log`.
- **cand_0005:** 10 of 10 call `list_anarchy_subjects` with only `guid: f3nlx` and no `cluster`. The
  call returned the correct, unambiguous subject. All 10 answers name the failed component, its
  state and the job id; none opened the job. The count fact "2 components" was missed in all 10:
  the answer says "both components" and tabulates two subjects, and the verifier wants a numeral or
  "two" near a noun.
- **Where the points went:** the cluster pin on the subject lookup 0.15; `list_deployments` not
  called (8 of 10 trials) 0.10; the count phrasing 0.14. Opening the job is not scored.
- **The text that caused it:** `candidates/cand_0005/babylon_agent.md:165` (first present in
  cand_0005, kept in cand_0006): "**Most actions need a `cluster`.** Only these resolve without
  one: `list_anarchy_subjects` and `list_anarchy_actions` when you pass a `guid`, and
  `get_workshop` / `get_multiworkshop` when you pass a `name` — those search every cluster."

### 2.2 Interface semantics (recorded)
- The real tool (`parsec-live/src/tools/babylon.py:679-683`): with no cluster resolved, a `guid`
  and action `list_anarchy_subjects`, it searches all configured clusters. `cluster` is not
  required.
- Its schema (`src/agent/tool_definitions.py`) says: "For list_anarchy_subjects … omit cluster to
  automatically search ALL configured clusters until found." The simulator's `api.json` says the
  same.
- The request states the cluster ("on the Babylon cluster `merlin`").
- The verifier pins `cluster: "merlin"` on that call (`tests/expected.json`) and requires every
  pinned argument to be present (`tests/verify.py:109-130`). Another test task, `platform-038`,
  requires the opposite: `absent_args: ["cluster"]`. Of 11 tasks that expect `list_anarchy_subjects`,
  5 pin `cluster`.

### 2.3 Counterfactual rescoring
The recorded trajectories rescored with the task's own `verify.py`:

| Contract | Seed | cand_0005 | Delta | Test-mean delta [95% CI] |
|---|--:|--:|--:|---|
| As graded | 0.985 | 0.590 | −0.395 | +0.0369 [+0.0112, +0.0645] |
| A. subject lookup without `cluster` accepted | 0.985 | 0.740 | −0.245 | +0.0392 [+0.0162, +0.0653] |
| B. A, and `list_deployments` not required | 1.000 | 0.860 | −0.140 | +0.0408 [+0.0193, +0.0663] |
| D. "both components" accepted | 0.985 | 0.688 | −0.297 | +0.0384 [+0.0145, +0.0651] |
| F. B and D | 1.000 | 0.958 | −0.042 | +0.0423 [+0.0216, +0.0671] |

### 2.4 Classification
**Inference.** A verifier that rejects a call the real tool accepts (cluster pin, high confidence);
a count matcher that is phrase-sensitive (medium); plus a smaller genuine shortfall, since the
bundle did not open the job (unscored) and skipped `list_deployments`, which the task is designed
to show hides the second subject. The simulator is not too permissive: the real tool accepts the
call too. Questions for the task's owner: should the contract pin `cluster` when the request gives
it, and should "both components" count as stating 2?

Across the test split, cand_0005 made 130 cluster-less identifier lookups in 19 tasks (Seed: 78
calls in 14 tasks); only `platform-131` pins `cluster` on that call. Correcting this one task moves
the headline from +0.0369 to +0.039–0.042, and the lower CI bound from +0.011 to +0.016–0.022.

---

## 3. Infrastructure in the sealed test

### 3.1 Recorded: counts
All 1,320 trials (660 per arm) were scanned through each trial's `agent/agent.jsonl`.

| | Seed | cand_0005 |
|---|--:|--:|
| Harness-errored / valid | 12 / 648 | 9 / 651 |
| Trials with "Internal error generating mock response" | 2 | 0 |
| Trials with the OpenShift "Application is not available" page | 0 | 0 |
| Trials with a simulator timeout ("did not respond within 240s … never answered") | 114 (17.6%) | 117 (18.0%) |
| Trials with "not modelled by the simulator" | 107 (16.5%) | 48 (7.4%) |

The two mock-response trials (Seed `platform-142` t1, `platform-108` t9) carry "Recursion limit of
50 reached", an agent loop limit, not the outage seen in the control batch. Timeouts occur in 49 tasks for the
Seed and 45 for cand_0005 (62 of 66 in either arm), across many tools, and are balanced in
aggregate but uneven on a few tasks (for example `icinga-072`: 0 vs 7 of 10; `icinga-224`: 5 vs 0).
Within each arm, trials with a timeout score lower (Seed 0.651 vs 0.845; cand_0005 0.733 vs 0.875).

### 3.2 Recomputed paired test delta
Paired by task; bootstrap 95% CI over tasks.

| Exclusion | Tasks | Seed | cand_0005 | Delta | SE | CI |
|---|--:|--:|--:|--:|--:|---|
| As published | 66 | .8126 | .8496 | **+.0369** | .0135 | [+.0112, +.0645] |
| Confirmed failures, by trial | 66 | .8132 | .8496 | +.0364 | .0134 | [+.0109, +.0637] |
| Confirmed failures, by task | 64 | .8157 | .8504 | +.0347 | .0137 | [+.0087, +.0627] |
| Plus all timeout trials | 66 | .8455 | .8523 | +.0068 | .0129 | [−.0170, +.0337] |
| Plus timeouts and "not modelled" | 59 | .8609 | .8778 | +.0169 | .0138 | [−.0092, +.0449] |

Dropping the two designed-outage tasks (`icinga-072`, `icinga-224`) gives +.0379 [+.0116, +.0659].

### 3.3 Reading it
- **Recorded:** the published delta is unchanged by confirmed failures. Timeouts are in both arms
  at the same rate.
- **Inference:** dropping timeout trials removes the trials that are hardest for the agent, and not
  equally across arms; the bundle's guidance about retrying and working around unavailable tools
  applies exactly there. So +.0068 is not "the real effect". It is a restriction to trials in which
  every tool answered. The harness does not mark timeouts invalid, and I did not find a log of why
  they occur.
- "Not modelled by the simulator" is a simulator limitation (the paper already treats it as
  simulator-specific); "No such file at the requested ref" is an ordinary 404.

---

## Evidence paths

| Item | Path (in the `parsec-intake_v6` worktree unless noted) |
|---|---|
| Control batch trials | `.capevolve.sealed/run_g2_e1/rollouts/confirm/*__r00{1,2,4}__*__ctrl_*__t*.json` |
| Gate log and round state | `.capevolve.sealed/run_g2_e1/private/p2_confirm.jsonl`, `private/p2/r00*.json` |
| Gate code | `core/cap_evolve/evaluator.py` (`sequential`), `racing.py` (`gs_decide`), `promotion.py` (`P2Params`) |
| Lineage and decisions | `.capevolve/v6_g2_e1/run_g2_e1/events.jsonl`, `candidates/cand_000{1..6}/` |
| Remeasurement | `rollouts/confirm/*__final__{champion,seed}__t*.json`, `internal_estimate.json` |
| Sealed test | `.capevolve/v6_g2_e1/run_g2_e1/rollouts/test/*__FINAL{,_seed}__t*.json` |
| Trial trajectories and verifier output | each record's `rollout.metadata.trial_dir` (`agent/agent.jsonl`, `verifier/reward-detail.json`) |
| platform-131 contract | `rhdp-parsec/v6_2026-10-16/bench-v6-harbor-tasks/bench-v6-platform-131-…/{tests,instruction.md,provenance.md}` |
| Real tool and schema | `rhdp-parsec/v6_2026-10-16/_run/parsec-live/src/tools/babylon.py`, `src/agent/tool_definitions.py` |
