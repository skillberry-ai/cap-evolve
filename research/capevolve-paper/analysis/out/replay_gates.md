# replay_gates: historical candidate decisions under alternative acceptance rules

Source: `/home/dev/projects2/campaign-scratch/artifacts/history` (manifest `research/capevolve-paper/audit/artifact_manifest.json`). Script: `analysis/scripts/replay_gates.py`; every number is read from an artifact or computed from artifact numbers with the repo's own `gate.decide` / `objectives.paired_reward`. **Inferred** items are marked [INFERRED]. Nothing is simulated.

## What is and is not replayable

| rule | status |
|---|---|
| (a) recorded decision | read from the run (node status). hill-climb: footprint-masked paired k_se at the run's setting; agent-optimize: the control-based gate |
| (b) unmasked k_se=1 | replayed from per-task val rewards of candidate and parent |
| (c) k_se 0.2 / 0.3 | replayed |
| (d) rule P | screen stage = (b); **confirmation not replayable**: no artifact re-measures candidate and incumbent on fresh trials |
| (e) reward_gated | **reward stage only** (z vs z_accept=2.734 with the 0.031 SE floor); cost conditions need per-trial cost, absent |
| E07 footprint set | **not recomputable**: rollout traces are not in the artifacts (`rollouts*.json` exports are empty). Masking is inferred from recorded vs unmasked delta/SE |
| per-candidate test | **not available**: test is sealed once, for the run's final champion only |

## Totals

19 runs, 96 replayable candidate decisions (by algorithm: {'unknown (pre-metadata export)': {'candidates': 21}, 'agent-optimize': {'candidates': 8}, 'hill-climb': {'candidates': 67}}).

| rule | accepts | decisions that differ from the recorded one |
|---|---|---|
| recorded | 33 | - |
| unmasked_k1 | 23 | 10 |
| k0.2 | 38 | 7 |
| k0.3 | 36 | 7 |
| reward_gated_reward_stage | 10 | 23 |

Runs are replicates on the same benchmark/seed split with the same optimizer family, and several share identical baselines and candidate trajectories; they are NOT independent samples. Pre-metadata exports have no algorithm field and no recorded k_se.

## Recorded accepts that another rule would reject

| run | algorithm | candidate | on champion path | unmasked delta | rules that reject it | run test delta (champion path only) |
|---|---|---|---|---|---|---|
| 30714307266 | unknown (pre-metadata export) | cand_0001 | True | +0.0659 | reward_gated_reward_stage | n/a |
| 30762167950 | unknown (pre-metadata export) | cand_0001 | True | +0.0220 | unmasked_k1,reward_gated_reward_stage | +0.0329 |
| 30762167950 | unknown (pre-metadata export) | cand_0003 | True | +0.0110 | unmasked_k1,k0.3,reward_gated_reward_stage | +0.0329 |
| 30762167950 | unknown (pre-metadata export) | cand_0005 | True | +0.0110 | unmasked_k1,reward_gated_reward_stage | +0.0329 |
| 30762167950 | unknown (pre-metadata export) | cand_0010 | True | +0.0110 | unmasked_k1,reward_gated_reward_stage | +0.0329 |
| 36175707483 | agent-optimize | r1_contract | True | +0.1500 | reward_gated_reward_stage | +0.1321 |
| 36175707483 | agent-optimize | r3_decide | True | +0.1125 | reward_gated_reward_stage | +0.1321 |
| 36466624841 | hill-climb | cand_0003 | True | +0.0750 | reward_gated_reward_stage | +0.3188 |
| 36523096755 | hill-climb | cand_0005 | True | +0.0500 | reward_gated_reward_stage | +0.3358 |
| 36841799223 | hill-climb | cand_0003 | True | +0.0500 | reward_gated_reward_stage | +0.4964 |
| 36862654281 | hill-climb | cand_0003 | True | +0.0750 | reward_gated_reward_stage | +0.4893 |
| 36887243479 | hill-climb | cand_0002 | True | +0.0500 | reward_gated_reward_stage | +0.4853 |
| 37204406089 | hill-climb | cand_0001 | True | +0.2250 | reward_gated_reward_stage | +0.1623 |
| 37204406089 | hill-climb | cand_0005 | True | +0.0000 | unmasked_k1,k0.2,k0.3,reward_gated_reward_stage | +0.1623 |
| 37294448854 | hill-climb | cand_0001 | True | +0.1500 | reward_gated_reward_stage | +0.1745 |
| 37294448854 | hill-climb | cand_0002 | True | +0.0500 | unmasked_k1,reward_gated_reward_stage | +0.1745 |
| 37294448854 | hill-climb | cand_0003 | True | +0.0750 | reward_gated_reward_stage | +0.1745 |
| 37345961613 | hill-climb | cand_0001 | True | +0.1750 | reward_gated_reward_stage | +0.1331 |
| 37345961613 | hill-climb | cand_0004 | True | +0.0500 | unmasked_k1,reward_gated_reward_stage | +0.1331 |
| 37372504934 | hill-climb | cand_0003 | True | +0.0250 | unmasked_k1,reward_gated_reward_stage | +0.2981 |
| 37457414293 | hill-climb | cand_0001 | True | +0.1250 | reward_gated_reward_stage | +0.2295 |
| 37457414293 | hill-climb | cand_0002 | True | +0.0750 | unmasked_k1,reward_gated_reward_stage | +0.2295 |
| 37457414293 | hill-climb | cand_0003 | True | +0.0500 | unmasked_k1,reward_gated_reward_stage | +0.2295 |

## Does a flip predict test gain or loss?

Only each run's FINAL champion is measured on test (vs the seed on the same test tasks). For a rule, the champion's ancestry (seed -> ... -> champion) either passes every step under that rule (the run would have reached the same champion; [INFERRED] assuming the optimizer proposes the same candidates) or is blocked at some step. Runs pooled; runs are not independent (shared seed/benchmark/optimizer), so this is descriptive.

| rule | path survives: runs | mean test delta | path blocked: runs | mean test delta | test deltas of blocked runs |
|---|---|---|---|---|---|
| unmasked_k1 | 10 | +0.3552 | 6 | +0.1717 | [0.0329, 0.1623, 0.1745, 0.1331, 0.2981, 0.2295] |
| k0.2 | 15 | +0.2946 | 1 | +0.1623 | [0.1623] |
| k0.3 | 14 | +0.3133 | 2 | +0.0976 | [0.0329, 0.1623] |
| reward_gated_reward_stage | 4 | +0.3235 | 12 | +0.2740 | [0.0329, 0.1321, 0.3188, 0.3358, 0.4964, 0.4893, 0.4853, 0.1623, 0.1745, 0.1331, 0.2981, 0.2295] |

A blocked run whose champion nevertheless gained on test is a gain the stricter rule would have forfeited; a blocked run with test delta <= 0 is a loss it would have avoided.

## E07 footprint false-exclusion audit (hill-climb)

Decisions with a recorded paired delta/SE: 67. In 4 the recorded delta or SE differs from the unmasked one by more than rounding: the live gate saw a footprint-masked and/or SE-floored vector [INFERRED from the mismatch].

- accepted while masked: 1; of these the unmasked k_se=1 gate would reject: **1**
- masked decisions whose excluded tasks carried net NEGATIVE delta (masking hid regressions): 4; net positive: 0
- sum of excluded net delta mass (task-delta units, + = gain hidden): -3.748 [INFERRED = n*(unmasked mean - recorded mean)]
- lower bound on excluded tasks with nonzero delta, summed over decisions: 4 [INFERRED, assumes |delta| <= 1 per task]

| run | candidate | recorded accept | unmasked k1 accept | recorded delta | unmasked delta | recorded SE | unmasked SE | excluded net mass | >= tasks |
|---|---|---|---|---|---|---|---|---|---|
| 36523096755 | cand_0004 | False | False | -0.0769 | -0.1000 | 0.0432 | 0.0480 | -0.901 | 1 |
| 37204406089 | cand_0003 | False | False | -0.0513 | -0.0750 | 0.0631 | 0.0659 | -0.924 | 1 |
| 37204406089 | cand_0005 | True | False | +0.0256 | +0.0000 | 0.0579 | 0.0620 | -0.998 | 1 |
| 37294448854 | cand_0004 | False | False | -0.0513 | -0.0750 | 0.0631 | 0.0659 | -0.924 | 1 |

## Per run

### 30714307266 spreadsheetbench/full unknown (pre-metadata export) (meta k_se None, val n None)

Champion `cand_0001` path ['cand_0001']; test +0.6030 vs baseline n/a (delta n/a)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.0659 | 0.0384 | acc | acc | acc | acc | rej | reward_gated_reward_stage |
| cand_0002 | cand_0001 | +0.0073 | 0.0308 | rej | rej | acc | rej | rej | k0.2 |
| cand_0003 | cand_0001 | -0.0330 | 0.0342 | rej | rej | rej | rej | rej | - |
| cand_0004 | cand_0001 | -0.0220 | 0.0280 | rej | rej | rej | rej | rej | - |
| cand_0005 | cand_0001 | -0.0220 | 0.0194 | rej | rej | rej | rej | rej | - |
| cand_0006 | cand_0001 | +0.0220 | 0.0275 | rej | rej | acc | acc | rej | k0.2,k0.3 |
| cand_0007 | cand_0001 | +0.0037 | 0.0198 | rej | rej | rej | rej | rej | - |
| cand_0008 | cand_0001 | +0.0220 | 0.0259 | rej | rej | acc | acc | rej | k0.2,k0.3 |
| cand_0009 | cand_0001 | +0.0037 | 0.0278 | rej | rej | rej | rej | rej | - |
| cand_0010 | cand_0001 | -0.0110 | 0.0160 | rej | rej | rej | rej | rej | - |

### 30762167950 spreadsheetbench/full unknown (pre-metadata export) (meta k_se None, val n None)

Champion `cand_0010` path ['cand_0001', 'cand_0003', 'cand_0005', 'cand_0010']; test +0.5290 vs baseline n/a (delta +0.0329, paired over 639 tasks SE 0.0144)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.0220 | 0.0349 | acc | rej | acc | acc | rej | reward_gated_reward_stage,unmasked_k1 |
| cand_0002 | cand_0001 | +0.0000 | 0.0313 | rej | rej | rej | rej | rej | - |
| cand_0003 | cand_0001 | +0.0110 | 0.0366 | acc | rej | acc | rej | rej | k0.3,reward_gated_reward_stage,unmasked_k1 |
| cand_0004 | cand_0003 | +0.0000 | 0.0271 | rej | rej | rej | rej | rej | - |
| cand_0005 | cand_0003 | +0.0110 | 0.0292 | acc | rej | acc | acc | rej | reward_gated_reward_stage,unmasked_k1 |
| cand_0006 | cand_0005 | -0.0440 | 0.0267 | rej | rej | rej | rej | rej | - |
| cand_0007 | cand_0005 | -0.0220 | 0.0220 | rej | rej | rej | rej | rej | - |
| cand_0008 | cand_0005 | -0.0330 | 0.0188 | rej | rej | rej | rej | rej | - |
| cand_0009 | cand_0005 | +0.0000 | 0.0221 | rej | rej | rej | rej | rej | - |
| cand_0010 | cand_0005 | +0.0110 | 0.0191 | acc | rej | acc | acc | rej | reward_gated_reward_stage,unmasked_k1 |

### 31331458168 swebench/pilot unknown (pre-metadata export) (meta k_se 1.0, val n None)

Champion `seed` path []; test +0.7045 vs baseline n/a (delta -0.0600, paired over 50 tasks SE 0.0723)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.0400 | 0.0569 | rej | rej | acc | acc | rej | k0.2,k0.3 |

### 36175707483 spreadsheetbench/full_verified agent-optimize (meta k_se 1.0, val n 40)

Champion `r3_decide` path ['r1_contract', 'r3_decide']; test +0.7643 vs baseline +0.6321 (delta +0.1321, paired over 280 tasks SE 0.0291)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| r1_contract | seed | +0.1500 | 0.0675 | acc | acc | acc | acc | rej | reward_gated_reward_stage |
| r2_numeric | r1_contract | +0.0500 | 0.0615 | rej | rej | acc | acc | rej | k0.2,k0.3 |
| r3_decide | r1_contract | +0.1125 | 0.0551 | acc | acc | acc | acc | rej | reward_gated_reward_stage |
| r4_silent | r3_decide | -0.0875 | 0.0503 | rej | rej | rej | rej | rej | - |
| r5_verdict | r3_decide | -0.0875 | 0.0503 | rej | rej | rej | rej | rej | - |
| r6_scope | r3_decide | -0.1375 | 0.0537 | rej | rej | rej | rej | rej | - |
| r7_path | r3_decide | -0.0625 | 0.0445 | rej | rej | rej | rej | rej | - |
| r8_cut | r3_decide | -0.0125 | 0.0379 | rej | rej | rej | rej | rej | - |

### 36261022325 spreadsheetbench/full_verified hill-climb (meta k_se 1.0, val n 40)

Champion `seed` path []; test +0.6679 vs baseline +0.6679 (delta +0.0000, paired over 280 tasks SE 0.0000)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.0750 | 0.0750 | rej | rej | acc | acc | rej | k0.2,k0.3 |

### 36306060353 spreadsheetbench/full_verified hill-climb (meta k_se 1.0, val n 40)

Champion `cand_0001` path ['cand_0001']; test +0.8536 vs baseline +0.6295 (delta +0.2241, paired over 280 tasks SE 0.0294)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.2500 | 0.0693 | acc | acc | acc | acc | acc | - |

### 36466624841 spreadsheetbench/full_verified hill-climb (meta k_se 0.2, val n None)

Champion `cand_0003` path ['cand_0001', 'cand_0003']; test +0.7536 vs baseline +0.4348 (delta +0.3188, paired over 280 tasks SE 0.0338)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.4500 | 0.0797 | acc | acc | acc | acc | acc | - |
| cand_0002 | cand_0001 | +0.0000 | 0.0506 | rej | rej | rej | rej | rej | - |
| cand_0003 | cand_0001 | +0.0750 | 0.0553 | acc | acc | acc | acc | rej | reward_gated_reward_stage |
| cand_0004 | cand_0003 | -0.0500 | 0.0500 | rej | rej | rej | rej | rej | - |
| cand_0005 | cand_0003 | -0.0750 | 0.0553 | rej | rej | rej | rej | rej | - |

### 36523096755 spreadsheetbench/full_verified hill-climb (meta k_se 0.2, val n None)

Champion `cand_0005` path ['cand_0001', 'cand_0005']; test +0.7706 vs baseline +0.4348 (delta +0.3358, paired over 280 tasks SE 0.0337)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.4500 | 0.0797 | acc | acc | acc | acc | acc | - |
| cand_0002 | cand_0001 | -0.0750 | 0.0553 | rej | rej | rej | rej | rej | - |
| cand_0003 | cand_0001 | +0.0000 | 0.0506 | rej | rej | rej | rej | rej | - |
| cand_0004 | cand_0001 | -0.1000 | 0.0480 | rej | rej | rej | rej | rej | - |
| cand_0005 | cand_0001 | +0.0500 | 0.0500 | acc | acc | acc | acc | rej | reward_gated_reward_stage |

### 36622615059 spreadsheetbench/full_verified hill-climb (meta k_se 0.2, val n None)

Champion `cand_0001` path ['cand_0001']; test +0.7786 vs baseline +0.4348 (delta +0.3438, paired over 280 tasks SE 0.0331)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.5000 | 0.0877 | acc | acc | acc | acc | acc | - |
| cand_0002 | cand_0001 | -0.0250 | 0.0565 | rej | rej | rej | rej | rej | - |
| cand_0003 | cand_0001 | -0.0750 | 0.0659 | rej | rej | rej | rej | rej | - |
| cand_0004 | cand_0001 | -0.0250 | 0.0565 | rej | rej | rej | rej | rej | - |
| cand_0005 | cand_0001 | -0.1000 | 0.0698 | rej | rej | rej | rej | rej | - |

### 36711181652 spreadsheetbench/full_verified hill-climb (meta k_se 0.2, val n None)

Champion `cand_0001` path ['cand_0001']; test +0.8978 vs baseline +0.3857 (delta +0.5121, paired over 280 tasks SE 0.0442)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.6750 | 0.0750 | acc | acc | acc | acc | acc | - |
| cand_0002 | cand_0001 | -0.1000 | 0.0480 | rej | rej | rej | rej | rej | - |
| cand_0003 | cand_0001 | -0.0500 | 0.0500 | rej | rej | rej | rej | rej | - |
| cand_0004 | cand_0001 | +0.0000 | 0.0358 | rej | rej | rej | rej | rej | - |
| cand_0005 | cand_0001 | +0.0000 | 0.0358 | rej | rej | rej | rej | rej | - |

### 36841799223 spreadsheetbench/full_verified hill-climb (meta k_se 0.2, val n None)

Champion `cand_0003` path ['cand_0001', 'cand_0003']; test +0.8821 vs baseline +0.3857 (delta +0.4964, paired over 280 tasks SE 0.0320)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.5750 | 0.0869 | acc | acc | acc | acc | acc | - |
| cand_0002 | cand_0001 | +0.0000 | 0.0620 | rej | rej | rej | rej | rej | - |
| cand_0003 | cand_0001 | +0.0500 | 0.0349 | acc | acc | acc | acc | rej | reward_gated_reward_stage |
| cand_0004 | cand_0003 | +0.0000 | 0.0358 | rej | rej | rej | rej | rej | - |
| cand_0005 | cand_0003 | +0.0000 | 0.0358 | rej | rej | rej | rej | rej | - |

### 36862654281 spreadsheetbench/full_verified hill-climb (meta k_se 0.2, val n None)

Champion `cand_0003` path ['cand_0001', 'cand_0003']; test +0.8750 vs baseline +0.3857 (delta +0.4893, paired over 280 tasks SE 0.0336)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.5750 | 0.0869 | acc | acc | acc | acc | acc | - |
| cand_0002 | cand_0001 | -0.0250 | 0.0437 | rej | rej | rej | rej | rej | - |
| cand_0003 | cand_0001 | +0.0750 | 0.0422 | acc | acc | acc | acc | rej | reward_gated_reward_stage |
| cand_0004 | cand_0003 | -0.0500 | 0.0349 | rej | rej | rej | rej | rej | - |
| cand_0005 | cand_0003 | -0.0250 | 0.0250 | rej | rej | rej | rej | rej | - |

### 36887243479 spreadsheetbench/full_verified hill-climb (meta k_se 0.2, val n None)

Champion `cand_0002` path ['cand_0001', 'cand_0002']; test +0.8710 vs baseline +0.3857 (delta +0.4853, paired over 280 tasks SE 0.0339)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.6000 | 0.0784 | acc | acc | acc | acc | acc | - |
| cand_0002 | cand_0001 | +0.0500 | 0.0349 | acc | acc | acc | acc | rej | reward_gated_reward_stage |
| cand_0003 | cand_0002 | -0.0250 | 0.0250 | rej | rej | rej | rej | rej | - |
| cand_0004 | cand_0002 | +0.0000 | 0.0000 | rej | rej | rej | rej | rej | - |
| cand_0005 | cand_0002 | +0.0000 | 0.0000 | rej | rej | rej | rej | rej | - |

### 37204406089 spreadsheetbench/full_verified hill-climb (meta k_se 0.2, val n None)

Champion `cand_0005` path ['cand_0001', 'cand_0005']; test +0.5971 vs baseline +0.4348 (delta +0.1623, paired over 280 tasks SE 0.0329)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.2250 | 0.0980 | acc | acc | acc | acc | rej | reward_gated_reward_stage |
| cand_0002 | cand_0001 | -0.0250 | 0.0669 | rej | rej | rej | rej | rej | - |
| cand_0003 | cand_0001 | -0.0750 | 0.0659 | rej | rej | rej | rej | rej | - |
| cand_0004 | cand_0001 | -0.0250 | 0.0437 | rej | rej | rej | rej | rej | - |
| cand_0005 | cand_0001 | +0.0000 | 0.0620 | acc | rej | rej | rej | rej | k0.2,k0.3,reward_gated_reward_stage,unmasked_k1 |

### 37294448854 spreadsheetbench/full_verified hill-climb (meta k_se 0.2, val n None)

Champion `cand_0003` path ['cand_0001', 'cand_0002', 'cand_0003']; test +0.6093 vs baseline +0.4348 (delta +0.1745, paired over 280 tasks SE 0.0314)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.1500 | 0.0916 | acc | acc | acc | acc | rej | reward_gated_reward_stage |
| cand_0002 | cand_0001 | +0.0500 | 0.0712 | acc | rej | acc | acc | rej | reward_gated_reward_stage,unmasked_k1 |
| cand_0003 | cand_0002 | +0.0750 | 0.0659 | acc | acc | acc | acc | rej | reward_gated_reward_stage |
| cand_0004 | cand_0003 | -0.0750 | 0.0659 | rej | rej | rej | rej | rej | - |
| cand_0005 | cand_0003 | -0.0500 | 0.0500 | rej | rej | rej | rej | rej | - |

### 37345961613 spreadsheetbench/full_verified hill-climb (meta k_se 0.2, val n None)

Champion `cand_0004` path ['cand_0001', 'cand_0004']; test +0.5679 vs baseline +0.4348 (delta +0.1331, paired over 280 tasks SE 0.0339)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.1750 | 0.1006 | acc | acc | acc | acc | rej | reward_gated_reward_stage |
| cand_0002 | cand_0001 | +0.0000 | 0.0716 | rej | rej | rej | rej | rej | - |
| cand_0003 | cand_0001 | -0.0250 | 0.0758 | rej | rej | rej | rej | rej | - |
| cand_0004 | cand_0001 | +0.0500 | 0.0712 | acc | rej | acc | acc | rej | reward_gated_reward_stage,unmasked_k1 |
| cand_0005 | cand_0004 | -0.0250 | 0.0565 | rej | rej | rej | rej | rej | - |

### 37372504934 spreadsheetbench/full_verified hill-climb (meta k_se 0.2, val n None)

Champion `cand_0003` path ['cand_0001', 'cand_0003']; test +0.7329 vs baseline +0.4348 (delta +0.2981, paired over 280 tasks SE 0.0329)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.3250 | 0.0973 | acc | acc | acc | acc | acc | - |
| cand_0002 | cand_0001 | -0.1000 | 0.0698 | rej | rej | rej | rej | rej | - |
| cand_0003 | cand_0001 | +0.0250 | 0.0565 | acc | rej | acc | acc | rej | reward_gated_reward_stage,unmasked_k1 |
| cand_0004 | cand_0003 | -0.1500 | 0.0572 | rej | rej | rej | rej | rej | - |
| cand_0005 | cand_0003 | -0.0750 | 0.0553 | rej | rej | rej | rej | rej | - |

### 37457414293 spreadsheetbench/full_verified hill-climb (meta k_se 0.2, val n None)

Champion `cand_0003` path ['cand_0001', 'cand_0002', 'cand_0003']; test +0.6643 vs baseline +0.4348 (delta +0.2295, paired over 280 tasks SE 0.0313)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | +0.1250 | 0.0891 | acc | acc | acc | acc | rej | reward_gated_reward_stage |
| cand_0002 | cand_0001 | +0.0750 | 0.0750 | acc | rej | acc | acc | rej | reward_gated_reward_stage,unmasked_k1 |
| cand_0003 | cand_0002 | +0.0500 | 0.0712 | acc | rej | acc | acc | rej | reward_gated_reward_stage,unmasked_k1 |
| cand_0004 | cand_0003 | -0.0500 | 0.0712 | rej | rej | rej | rej | rej | - |
| cand_0005 | cand_0003 | -0.0250 | 0.0437 | rej | rej | rej | rej | rej | - |

### 37531466608 spreadsheetbench/full_verified hill-climb (meta k_se 0.2, val n None)

Champion `cand_0002` path ['cand_0002']; test +0.6487 vs baseline +0.4348 (delta +0.2140, paired over 280 tasks SE 0.0307)

| candidate | parent | unmasked delta | unmasked SE | recorded | k=1 unmasked | k=0.2 | k=0.3 | reward_gated (reward stage) | flips vs recorded |
|---|---|---|---|---|---|---|---|---|---|
| cand_0001 | seed | -0.0750 | 0.0422 | rej | rej | rej | rej | rej | - |
| cand_0002 | seed | +0.3500 | 0.0844 | acc | acc | acc | acc | acc | - |
| cand_0003 | cand_0002 | +0.0000 | 0.0620 | rej | rej | rej | rej | rej | - |
| cand_0004 | cand_0002 | -0.0500 | 0.0500 | rej | rej | rej | rej | rej | - |
| cand_0005 | cand_0002 | -0.0750 | 0.0553 | rej | rej | rej | rej | rej | - |
