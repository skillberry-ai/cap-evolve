<!-- Local benchmark run detail page. Linked from https://skillberry-ai.github.io/cap-evolve/benchmarks.html -->

> **Local benchmark run** (recorded on the benchmark-history branch).
> Ran outside the CI workflow (source: `bcarmeli`); artifacts on the recording host.
> Benchmark: SkillsBench (all 87 tasks, fit metric — train==val==test); agent under test: aws/gpt-oss-120b.

# Run summary — `run_baseline_gptoss`

- **Benchmark:** `skillsbench`
- **Agent under test:** `aws/gpt-oss-120b`
- **Optimizer:** `none`
- **Tasks / trials:** 87 tasks · 1 trials
- **Iterations (actual / cap):** 0 / 3
- **Split discipline:** fit-metric (train==val==test, no holdout)
- **Best candidate:** `seed`

## Headline

|  | value |
|---|---|
| val_reward (mean) | **0.0396 ± 0.0191** (4.0%) |
| pass_at_1 (fully passing) | **2/87** (2.3%) |
| test_reward | **0.0396** |
| test_delta (best - baseline) | 0.0 |
| val wall-clock | 76m 53s |
| test wall-clock | 41m 4s |
| total wall-clock | 118m 5s |

## Rollout breakdown (n = 87)

- Passed (r = 1.0): **2**
- Partial (0 < r < 1): **4**
- Errored (infra): **11**
- Failed (r = 0): **70**

## Passing tasks

- ✓ `3d-scan-calc`
- ✓ `pddl-tpp-planning`

## Partial credit

| task | reward |
|---|---|
| `dialogue-parser` | 0.833 |
| `lab-unit-harmonization` | 0.312 |
| `debug-trl-grpo` | 0.250 |
| `tictoc-unnecessary-abort-detection` | 0.050 |

## Errored tasks (infra, not skill defect)

- ⚠ `earthquake-phase-association`
- ⚠ `fix-build-agentops`
- ⚠ `fix-build-google-auto`
- ⚠ `fix-druid-loophole-cve`
- ⚠ `flink-query`
- ⚠ `manufacturing-equipment-maintenance`
- ⚠ `multilingual-video-dubbing`
- ⚠ `python-scala-translation`
- ⚠ `react-performance-debugging`
- ⚠ `seismic-phase-picking`
- ⚠ `spring-boot-jakarta-migration`

