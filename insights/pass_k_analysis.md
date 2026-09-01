# pass^k analysis — SkillsBench 87-task scoreboard (cap-evolve)

Generated from `results.json` (87 tasks) + raw per-trial `verifier/reward.txt` files in the
`.capevolve/run_task_*/bench_jobs/<winning_tag>/seedN/<timestamp>/<task>__<hash>/verifier/` trees of the
`intake_skillbench_c2` (c1-v1 / c1-tA / c1-v5 / c2-v2 runs), `intake_skillbench_c3` (c3-v1) and
`intake_skillbench_v2` (mac-v2) worktrees. Nothing else in this directory was modified.

## 1. Methodology

**pass^k (tau-bench, Yao et al.)** — probability that a random size-`k` subset of the `n` available trials
for a task contains *only* successes:

```
pass^k = C(c, k) / C(n, k)      (= 0 when c < k;  undefined when n < k)
```
where `c` = number of successful trials out of `n`. This is the hypergeometric "all k succeed" probability —
the **opposite** of pass@k (`1 - C(n-c,k)/C(n,k)`, "at least one success"). Reported here:

- `pass^1 = c/n` — plain per-trial success rate.
- `pass^5` — headline reliability number (k=5 chosen to mirror EvoSkill's 5 independent full-benchmark runs).
- `pass^10 = 1 if c == n else 0` — strict all-trials-pass.

**Success threshold.** A trial counts as a success iff its raw reward `>= 0.999`. Most tasks are binary 0/1,
but a few emit continuous partial credit (e.g. 0.45, 0.82, 0.5, 0.6, 0.9667); those partial values count as
failures, so `pass^1` here is *not* the same as the mean reward recorded in `results.json`.

**Which candidate.** For each task the winning candidate is `best_tag` from `results.json` (`seed` for the
KILLED_saturated tasks, where the seed capability itself is the winner). Trials are read from that tag's
`bench_jobs` subtree; when a `seedN` directory held more than one timestamp (a retry), only the latest
timestamp was used, and where a timestamp held more than one job directory the newest was used (3 tasks:
`court-form-filling`, `flink-query`, `paper-anonymizer`).

**Errored / pruned trials.** A trial whose `reward.txt` is absent was cross-checked against the
harness-recorded `trial_rewards` array in the same run's `final.json` / `baseline.json`; in every such case
the harness had recorded 0.0 (infrastructure error or timeout counted as a failure). Where the recorded
array agreed with every `reward.txt` actually found, the full 10-value array was used and the substitution is
noted per task. No value was invented.

**Which evaluation.** cap-evolve prunes `bench_jobs` as a run proceeds, so what survives on disk is the
*last* 10-trial evaluation of the winning tag. For runs that finished (`DONE`) that is the held-out **test**
evaluation; for runs killed the moment val hit the ceiling (`KILLED_ceiling`, `KILLED_saturated`,
`KILLED_val_1.0`) it is the **val** evaluation. The `split` column records which. This matters: for several
tasks the winner scored val 1.0 but test < 1.0 (e.g. `edit-pdf` 1.0 -> 0.8, `travel-planning` 1.0 -> 0.8,
`syzkaller-ppdev-syzlang` 1.0 -> 0.9, `energy-unit-commitment` 1.0 -> 0.1, `organize-messy-files` 0.9 -> 0.0),
so val-sourced rows are systematically more optimistic than test-sourced rows.

**CAVEAT on comparability.** EvoSkill's 71.1% averages 5 *independent full-benchmark runs* — each run repeats
the entire optimization process, so their spread captures **optimizer-outcome variance**. Our 10 trials are
repeated *evaluations of one fixed, already-optimized candidate*, so `pass^5` here measures **within-run
trial-noise reliability** only. It is a useful additional cut (and a much harder bar than the mean reward),
not a like-for-like substitute; it says nothing about how often our optimizer would rediscover the same
winning candidate.

## 2. Per-task table

`n` = trials found. `D` marks the 19 rows whose `c` was **derived** rather than read (see notes / §3).

| task | category | split | n | c | pass^1 | pass^5 | pass^10 | notes |
|---|---|---|---|---|---|---|---|---|
| `3d-scan-calc` | industrial-physical-systems | val(seed) | 10 | 10 | 1 | 1 | 1 |  |
| `ada-bathroom-plan-repair` | industrial-physical-systems | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `adaptive-cruise-control` | industrial-physical-systems | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `azure-bgp-oscillation-route-leak` | software-engineering | test | 10 | 10 | 1 | 1 | 1 |  |
| `bike-rebalance` | mathematics-or-formal-reasoning | val (run killed at ceiling) | 2 | 2 | 1 | n/a | n/a | eval truncated by kill: only 2 trials on disk. |
| `citation-check` | office-white-collar | val(seed) | 10 | 10 | 1 | 1 | 1 |  |
| `civ6-adjacency-optimizer` | mathematics-or-formal-reasoning | test | 10 | 10 | 1 | 1 | 1 |  |
| `court-form-filling` | office-white-collar | test | 10 | 10 | 1 | 1 | 1 | [seed4:2jobdirs] |
| `crystallographic-wyckoff-position-analysis` | natural-science | test | 10 | 1 | 0.1 | 0 | 0 | reward.txt pruned for trial(s) 3,5,7,8,9; harness-recorded value used. |
| `dapt-intrusion-detection` | cybersecurity | val(seed) | 10 | 10 | 1 | 1 | 1 |  |
| `data-to-d3` | software-engineering | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `debug-trl-grpo` | software-engineering | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `dialogue-parser` | software-engineering | test | 10 | 10 | 1 | 1 | 1 |  |
| `drone-planning-control` | industrial-physical-systems | test | 10 | 5 | 0.5 | 0.004 | 0 |  |
| `dynamic-object-aware-egomotion` | industrial-physical-systems | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `earthquake-phase-association` | natural-science | test | 3 | 0 | 0 | n/a | n/a | reward.txt pruned for trial(s) 0,1,2; harness-recorded value used. |
| `earthquake-plate-calculation` | natural-science | test | 10 | 10 | 1 | 1 | 1 |  |
| `econ-detrending-correlation` | finance-economics | test | 10 | 10 | 1 | 1 | 1 |  |
| `edit-pdf` | office-white-collar | test | 10 | 8 | 0.8 | 0.2222 | 0 |  |
| `energy-ac-optimal-power-flow` | industrial-physical-systems | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `energy-market-pricing` | industrial-physical-systems | test | 10 | 8 | 0.8 | 0.2222 | 0 |  |
| `energy-unit-commitment` | industrial-physical-systems | test | 10 | 1 | 0.1 | 0 | 0 | reward.txt pruned for trial(s) 1,2,3,4,5,6,7,8,9; harness-recorded value used. |
| `enterprise-information-search` | office-white-collar | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `exam-block-sequencing` | mathematics-or-formal-reasoning | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `exceltable-in-ppt` | office-white-collar | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `exoplanet-detection-period` | natural-science | val(seed) | 10 | 10 | 1 | 1 | 1 |  |
| `financial-modeling-qa` | finance-economics | test | 10 | 0 | 0 | 0 | 0 |  |
| `fix-build-agentops` | software-engineering | test | 10 | 0 | 0 | 0 | 0 | 2 run dirs; used newest mtime. |
| `fix-build-google-auto` | software-engineering | test | 3 | 0 | 0 | n/a | n/a | reward.txt pruned for trial(s) 0,1,2; harness-recorded value used. |
| `fix-druid-loophole-cve` | cybersecurity | test | 10 | 0 | 0 | 0 | 0 |  |
| `fix-erlang-ssh-cve` | cybersecurity | test | 10 | 10 | 1 | 1 | 1 |  |
| `fix-visual-stability` | software-engineering | test | 3 | 0 | 0 | n/a | n/a | reward.txt pruned for trial(s) 0,1,2; harness-recorded value used. |
| `flink-query` | software-engineering | test | 10 | 9 | 0.9 | 0.5 | 0 | [seed7:2jobdirs] |
| `flood-risk-analysis` | natural-science | val(seed) | 10 | 10 | 1 | 1 | 1 |  |
| `glm-lake-mendota` | natural-science | val(seed) | 3 | 3 | 1 | n/a | n/a | mac-v2 run: only 3 trials configured |
| `gravitational-wave-detection` | natural-science | val(seed) | 10 | 10 | 1 | 1 | 1 |  |
| `grid-dispatch-operator` | industrial-physical-systems | test | 10 | 10 | 1 | 1 | 1 |  |
| `hvac-control` | industrial-physical-systems | val(seed) | 10 | 10 | 1 | 1 | 1 |  |
| `invoice-fraud-detection` | finance-economics | test | 10 | 3 | 0.3 | 0 | 0 |  |
| `jax-computing-basics` | software-engineering | test | 10 | 9 | 0.9 | 0.5 | 0 |  |
| `jpg-ocr-stat` | office-white-collar | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `lab-unit-harmonization` | natural-science | test | 10 | 10 | 1 | 1 | 1 |  |
| `lake-warming-attribution` | natural-science | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `latex-formula-extraction` | office-white-collar | test | 10 | 8 | 0.8 | 0.2222 | 0 |  |
| `lean4-proof` | mathematics-or-formal-reasoning | test | 10 | 10 | 1 | 1 | 1 |  |
| `llm-prefix-cache-replay` | software-engineering | test | 10 | 10 | 1 | 1 | 1 |  |
| `manufacturing-codebook-normalization` | industrial-physical-systems | val (run killed at ceiling) | 6 | 6 | 1 | 1 | n/a | eval truncated by kill: only 6 trials on disk. |
| `manufacturing-equipment-maintenance` | industrial-physical-systems | val (run killed at ceiling) | 3 | 3 | 1 | n/a | n/a | eval truncated by kill: only 3 trials on disk. |
| `manufacturing-fjsp-optimization` | industrial-physical-systems | test | 10 | 10 | 1 | 1 | 1 |  |
| `mario-coin-counting` | media-content-production | val(seed) | 10 | 10 | 1 | 1 | 1 |  |
| `mars-clouds-clustering` | natural-science | val(seed) | 10 | 10 | 1 | 1 | 1 |  |
| `multilingual-video-dubbing` | media-content-production | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `offer-letter-generator` | office-white-collar | test | 3 | 3 | 1 | n/a | n/a | mac-v2 run: only 3 trials configured |
| `organize-messy-files` | office-white-collar | test | 10 | 0 | 0 | 0 | 0 | reward.txt pruned for trial(s) 0,1,2,3,4,5,6,7,8,9; harness-recorded value used. |
| `paper-anonymizer` | office-white-collar | test | 10 | 6 | 0.6 | 0.0238 | 0 | [seed9:2jobdirs] |
| `parallel-tfidf-search` | software-engineering | val(seed) | 10 | 10 | 1 | 1 | 1 |  |
| `paratransit-routing` | mathematics-or-formal-reasoning | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `pddl-airport-planning` | mathematics-or-formal-reasoning | test | 10 | 10 | 1 | 1 | 1 |  |
| `pddl-tpp-planning` | mathematics-or-formal-reasoning | val(seed) | 10 | 10 | 1 | 1 | 1 |  |
| `pdf-excel-diff` | office-white-collar | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `powerlifting-coef-calc` | office-white-collar | test | 10 | 10 | 1 | 1 | 1 |  |
| `pptx-reference-formatting` | office-white-collar | val(seed) | 10 | 10 | 1 | 1 | 1 |  |
| `protein-expression-analysis` | natural-science | val(seed) | 10 | 10 | 1 | 1 | 1 |  |
| `python-scala-translation` | software-engineering | test | 10 | 0 | 0 | 0 | 0 | 2 run dirs; used newest mtime. reward.txt pruned for trial(s) 0,1,2,3,4,5,6,7,8,9; harness-recorded value used. |
| `quantum-numerical-simulation` | natural-science | test | 10 | 0 | 0 | 0 | 0 | reward.txt pruned for trial(s) 0,1,2,5,6,7,8,9; harness-recorded value used. |
| `r2r-mpc-control` | industrial-physical-systems | test | 10 | 10 | 1 | 1 | 1 |  |
| `radar-vital-signs` | natural-science | test | 10 | 10 | 1 | 1 | 1 |  |
| `react-performance-debugging` | software-engineering | val (run killed at ceiling) | 3 | 3 | 1 | n/a | n/a | eval truncated by kill: only 3 trials on disk. |
| `reserves-at-risk-calc` | finance-economics | test | 10 | 10 | 1 | 1 | 1 |  |
| `sales-pivot-analysis` | office-white-collar | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `sec-financial-report` | finance-economics | test | 10 | 10 | 1 | 1 | 1 | 2 run dirs; used newest mtime. |
| `seismic-phase-picking` | natural-science | test | 3 | 0 | 0 | n/a | n/a | reward.txt pruned for trial(s) 0,1,2; harness-recorded value used. |
| `setup-fuzzing-py` | cybersecurity | test | 10 | 3 | 0.3 | 0 | 0 | 2 run dirs; used newest mtime. |
| `shock-analysis-demand` | finance-economics | test | 10 | 9 | 0.9 | 0.5 | 0 |  |
| `shock-analysis-supply` | finance-economics | test | 10 | 2 | 0.2 | 0 | 0 | reward.txt pruned for trial(s) 2,7; harness-recorded value used. |
| `simpo-code-reproduction` | software-engineering | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `software-dependency-audit` | cybersecurity | test | 10 | 10 | 1 | 1 | 1 |  |
| `spring-boot-jakarta-migration` | software-engineering | test | 10 | 0 | 0 | 0 | 0 | reward.txt pruned for trial(s) 0,1,2,3,4,5,6,7,8,9; harness-recorded value used. |
| `suricata-custom-exfil` | cybersecurity | test | 3 | 2 | 0.6667 | n/a | n/a | reward.txt pruned for trial(s) 2; harness-recorded value used. |
| `syzkaller-ppdev-syzlang` | cybersecurity | test | 10 | 9 | 0.9 | 0.5 | 0 |  |
| `threejs-structure-parser` | media-content-production | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `threejs-to-obj` | media-content-production | val(seed) | 10 | 10 | 1 | 1 | 1 | 2 run dirs; used newest mtime. |
| `tictoc-unnecessary-abort-detection` | software-engineering | test | 10 | 10 | 1 | 1 | 1 |  |
| `travel-planning` | mathematics-or-formal-reasoning | test | 10 | 8 | 0.8 | 0.2222 | 0 |  |
| `video-silence-remover` | media-content-production | test | 10 | 10 | 1 | 1 | 1 |  |
| `weighted-gdp-calc` | finance-economics | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |
| `xlsx-recover-data` | finance-economics | val (derived) | 10 | 10 | 1 | 1 | 1 | **D** reward.txt pruned (run killed at ceiling); winner's val eval = 1.000 over n=10 in history.jsonl, so all 10 trials must be 1.0 -> c=10 derived, not read. |

## 3. Aggregates

Two cuts, because 19 of 87 tasks had their winning candidate's `bench_jobs` tree pruned when the run was
killed at the val ceiling.

### A. Raw-data-only (68 tasks with per-trial rewards actually on disk / recorded by the harness)

| metric | mean | tasks in mean |
|---|---|---|
| mean pass^1 | **74.4%** | 68 |
| mean pass^5 | **67.1%** | 58 (10 tasks have n<5 -> pass^5 undefined, excluded) |
| mean pass^10 | **61.4%** | 57 (11 tasks have n<10 -> pass^10 undefined, excluded) |

### B. All 87 tasks, with the 19 pruned tasks filled in by derivation

For all 19, `history.jsonl` records the winning candidate's val reward as **exactly 1.000** over the standard
`n=10` evaluation. Since no single trial can exceed 1.0, a mean of exactly 1.0 over 10 trials forces all 10
trials to be 1.0, so `c=10` is entailed, not guessed. These are val-split numbers, and val-sourced rows run
optimistic (see §1), so treat B as an upper bound.

| metric | mean | tasks in mean |
|---|---|---|
| mean pass^1 | **80.0%** | 87 |
| mean pass^5 | **75.2%** | 77 (10 tasks have n<5 -> pass^5 undefined, excluded) |
| mean pass^10 | **71.1%** | 76 (11 tasks have n<10 -> pass^10 undefined, excluded) |

For reference, the scoreboard's mean `best` reward over the same 87 tasks is **84.2%**, and EvoSkill reports **71.1%**.

### Tasks not fully computable

- **0 tasks** had no locatable run directory.
- **19 tasks** had no raw per-trial file for the winning candidate (bench_jobs pruned on kill): `ada-bathroom-plan-repair`, `adaptive-cruise-control`, `data-to-d3`, `debug-trl-grpo`, `dynamic-object-aware-egomotion`, `energy-ac-optimal-power-flow`, `enterprise-information-search`, `exam-block-sequencing`, `exceltable-in-ppt`, `jpg-ocr-stat`, `lake-warming-attribution`, `multilingual-video-dubbing`, `paratransit-routing`, `pdf-excel-diff`, `sales-pivot-analysis`, `simpo-code-reproduction`, `threejs-structure-parser`, `weighted-gdp-calc`, `xlsx-recover-data`. Handled by derivation as above; they are the `D` rows.
- **11 tasks** have `n != 10` (mac-v2 runs were configured with 3 trials; some ceiling-kills cut the eval short), so `pass^10` is undefined for all of them and `pass^5` is undefined for the 10 with n<5:
  - `bike-rebalance`: n=2 — eval truncated by kill: only 2 trials on disk.
  - `earthquake-phase-association`: n=3 — reward.txt pruned for trial(s) 0,1,2; harness-recorded value used.
  - `fix-build-google-auto`: n=3 — reward.txt pruned for trial(s) 0,1,2; harness-recorded value used.
  - `fix-visual-stability`: n=3 — reward.txt pruned for trial(s) 0,1,2; harness-recorded value used.
  - `glm-lake-mendota`: n=3 — mac-v2 run configured with only 3 trials (all 3 reward.txt present).
  - `manufacturing-codebook-normalization`: n=6 — eval truncated by kill: only 6 trials on disk.
  - `manufacturing-equipment-maintenance`: n=3 — eval truncated by kill: only 3 trials on disk.
  - `offer-letter-generator`: n=3 — mac-v2 run configured with only 3 trials (all 3 reward.txt present).
  - `react-performance-debugging`: n=3 — eval truncated by kill: only 3 trials on disk.
  - `seismic-phase-picking`: n=3 — reward.txt pruned for trial(s) 0,1,2; harness-recorded value used.
  - `suricata-custom-exfil`: n=3 — reward.txt pruned for trial(s) 2; harness-recorded value used.

### Disagreements / judgement calls

- `fix-build-agentops`, `python-scala-translation`, `sec-financial-report`, `setup-fuzzing-py`,
  `threejs-to-obj` each had 2 candidate run directories (an earlier `INFRA_BROKEN` / `infra_broken_uvx`
  attempt plus the good one); the most recently modified was used, which in every case is the non-broken run.
- `fix-erlang-ssh-cve` shows c=10 (test) against a recorded val of 0.9 — the winner did better on test.
- `crystallographic-wyckoff-position-analysis` and `setup-fuzzing-py` are the main continuous-reward tasks;
  their pass^1 (0.1 and 0.3) is far below their mean reward (0.317 and 0.881) because partial credit does
  not clear the 0.999 threshold.
