<!-- Local benchmark run detail page. Linked from https://skillberry-ai.github.io/cap-evolve/benchmarks.html -->

> **Local benchmark run** (recorded on the benchmark-history branch).
> Ran outside the CI workflow (source: `bcarmeli`); artifacts on the recording host.
> Benchmark: SkillsBench (all 87 tasks, fit metric — train==val==test); agent under test: claude-opus-4-6.

# Run summary — `run_baseline_opus`

- **Benchmark:** `skillsbench`
- **Agent under test:** `claude-opus-4-6`
- **Optimizer:** `none`
- **Tasks / trials:** 87 tasks · 1 trials
- **Iterations (actual / cap):** 0 / 3
- **Split discipline:** fit-metric (train==val==test, no holdout)
- **Best candidate:** `seed`

## Headline

|  | value |
|---|---|
| val_reward (mean) | **0.2809 ± 0.0475** (28.1%) |
| pass_at_1 (fully passing) | **23/87** (26.4%) |
| test_reward | **0.2809** |
| test_delta (best - baseline) | 0.0 |
| val wall-clock | 106m 59s |
| test wall-clock | 41m 38s |
| total wall-clock | 148m 42s |

## Rollout breakdown (n = 87)

- Passed (r = 1.0): **23**
- Partial (0 < r < 1): **3**
- Errored (infra): **8**
- Failed (r = 0): **53**

## Passing tasks

- ✓ `3d-scan-calc`
- ✓ `adaptive-cruise-control`
- ✓ `citation-check`
- ✓ `court-form-filling`
- ✓ `crystallographic-wyckoff-position-analysis`
- ✓ `econ-detrending-correlation`
- ✓ `exam-block-sequencing`
- ✓ `fix-erlang-ssh-cve`
- ✓ `glm-lake-mendota`
- ✓ `gravitational-wave-detection`
- ✓ `hvac-control`
- ✓ `lean4-proof`
- ✓ `mars-clouds-clustering`
- ✓ `offer-letter-generator`
- ✓ `parallel-tfidf-search`
- ✓ `pddl-tpp-planning`
- ✓ `pdf-excel-diff`
- ✓ `powerlifting-coef-calc`
- ✓ `pptx-reference-formatting`
- ✓ `protein-expression-analysis`
- ✓ `spring-boot-jakarta-migration`
- ✓ `threejs-to-obj`
- ✓ `tictoc-unnecessary-abort-detection`

## Partial credit

| task | reward |
|---|---|
| `dialogue-parser` | 0.667 |
| `lab-unit-harmonization` | 0.521 |
| `debug-trl-grpo` | 0.250 |

## Errored tasks (infra, not skill defect)

- ⚠ `earthquake-phase-association`
- ⚠ `energy-ac-optimal-power-flow`
- ⚠ `fix-druid-loophole-cve`
- ⚠ `fix-visual-stability`
- ⚠ `multilingual-video-dubbing`
- ⚠ `python-scala-translation`
- ⚠ `quantum-numerical-simulation`
- ⚠ `seismic-phase-picking`

