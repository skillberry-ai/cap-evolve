# task-by-task-43 — EvoSkills-style, one skill per task, ALL 43 runnable SkillsBench tasks

**Date:** 2026-08-19 → 2026-08-23
- Batch 1 (10 tasks): initial 2-iter runs (2026-08-19)
- Batch 2 (10 tasks): all-zero-in-whole-suite (2026-08-20)
- Track A: 3 partial-lift tasks from batch 1 re-run with --resume, max_iterations=4 (2026-08-21)
- v7 podman fix: 8 previously infra-blocked batch-2 tasks re-run (2026-08-21)
- Batch 3 (23 tasks): the remaining runnable, max_iterations=4 (2026-08-22 → 08-23)

**Worktree:** `intake_skillbench_c2` on branch `intake_skillbench_c2`
**Agent:** claude-sonnet-5 · **Optimizer:** claude-opus-4-8
**Trials per candidate:** 10 · **Split:** train == val == test == [single task] · **Gate:** paired-SE, k=0.2

## Aggregate — full 43-task result

| batch | n | avg baseline | avg best | Δ |
|---|---|---|---|---|
| batch 1 | 10 | 0.690 | 0.940 | +0.250 |
| batch 2 (post-v7 fix) | 10 | 0.412 | 0.622 | +0.210 |
| batch 3 (max_iterations=4) | 23 | 0.448 | 0.926 | +0.478 |
| **FULL RUNNABLE-43** | **43** | **0.496** | **0.859** | **+0.363 (+36.3 pp)** |

## vs whole-suite runnable-43 (2026-07-30 baseline)

The same 43-task set, evaluated with the shared office quartet as seed instead of each task's own skills:

| metric | whole-suite (office seed) | task-by-task-43 (own seed) |
|---|---|---|
| avg baseline | 0.140 | 0.496 |
| avg best | 0.170 | 0.859 |
| avg Δ | +0.030 (+3.1 pp) | **+0.363 (+36.3 pp)** |

Task-native seed delivers **~12× the aggregate lift** of the office quartet on the same 43 tasks.

## Task outcomes

- **28/43 tasks reach val=1.0** (65%)
- **7 saturated at baseline** (killed early): `3d-scan-calc`, `flood-risk-analysis`, `threejs-to-obj`, `citation-check`, `dapt-intrusion-detection`, `pptx-reference-formatting`, `protein-expression-analysis`
- **11 reached ceiling via optimizer** (killed early once cand hit 1.0): `data-to-d3`, `dynamic-object-aware-egomotion`, `enterprise-information-search`, `exceltable-in-ppt`, `jpg-ocr-stat`, `lake-warming-attribution`, `pdf-excel-diff`, `sales-pivot-analysis`, `threejs-structure-parser`, `weighted-gdp-calc`, `xlsx-recover-data`
- **11 partial lifts** (0.05–0.99 range)
- **3 stuck at 0**: `financial-modeling-qa`, `python-scala-translation`, `spring-boot-jakarta-migration`

## Per-task table

| task | batch | seed | c1 | c2 | c3 | c4 | best | Δ | notes |
|---|---|---|---|---|---|---|---|---|---|
| `edit-pdf` | b1 | 0.900 | 0.900 | 1.000 | — | — | **1.000** (cand_0002) | +0.100 |  |
| `court-form-filling` | b1 | 0.300 | 0.100 | 1.000 | — | — | **1.000** (cand_0002) | +0.700 |  |
| `adaptive-cruise-control` | b1 | 0.700 | 0.700 | 0.900 | 1.000 | 1.000 | **1.000** (cand_0004) | +0.300 | Track A iters 3-4 |
| `hvac-control` | b1 | 1.000 | — | — | — | — | **1.000** (seed) | +0.000 |  |
| `r2r-mpc-control` | b1 | 0.300 | 1.000 | 1.000 | — | — | **1.000** (cand_0002) | +0.700 |  |
| `3d-scan-calc` | b1 | 1.000 | — | — | — | — | **1.000** (seed) | +0.000 | saturated (killed) |
| `syzkaller-ppdev-syzlang` | b1 | 0.700 | 0.900 | 1.000 | — | — | **1.000** (cand_0002) | +0.300 |  |
| `multilingual-video-dubbing` | b1 | 0.700 | 0.900 | 0.900 | 0.900 | 1.000 | **1.000** (cand_0004) | +0.300 | Track A iters 3-4 |
| `flood-risk-analysis` | b1 | 1.000 | — | — | — | — | **1.000** (seed) | +0.000 | saturated (killed) |
| `invoice-fraud-detection` | b1 | 0.300 | 0.200 | 0.400 | 0.200 | 0.200 | **0.400** (cand_0002) | +0.100 | Track A iters 3-4 |
| `financial-modeling-qa` | b2 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | **0.000** (cand_0004) | +0.000 | v7 rerun |
| `sec-financial-report` | b2 | 0.900 | 0.000 | 1.000 | — | — | **1.000** (cand_0002) | +0.100 | v7 rerun |
| `drone-planning-control` | b2 | 0.720 | 0.000 | 0.000 | 0.300 | 0.300 | **0.720** (seed) | +0.000 | v7 rerun |
| `grid-dispatch-operator` | b2 | 0.000 | 0.900 | 1.000 | — | — | **1.000** (cand_0002) | +1.000 |  |
| `jax-computing-basics` | b2 | 0.900 | 0.000 | 0.000 | 0.400 | 0.100 | **0.900** (seed) | +0.000 | v7 rerun |
| `threejs-to-obj` | b2 | 1.000 | — | — | — | — | **1.000** (seed) | +0.000 | saturated (killed); v7 rerun |
| `paper-anonymizer` | b2 | 0.600 | 0.000 | 0.000 | 0.200 | 0.000 | **0.600** (seed) | +0.000 | v7 rerun |
| `pddl-airport-planning` | b2 | 0.000 | 0.000 | 1.000 | — | — | **1.000** (cand_0002) | +1.000 |  |
| `python-scala-translation` | b2 | 0.000 | 0.000 | 0.000 | — | — | **0.000** (cand_0002) | +0.000 | v7 rerun |
| `offer-letter-generator` | b2 | — | — | — | — | — | **—** (—) | +0.000 | v7 rerun |
| `citation-check` | b3 | 1.000 | — | — | — | — | **1.000** (seed) | +0.000 | saturated (killed) |
| `dapt-intrusion-detection` | b3 | 1.000 | — | — | — | — | **1.000** (seed) | +0.000 | saturated (killed) |
| `data-to-d3` | b3 | 0.500 | 0.900 | 1.000 | — | — | **1.000** (cand_0002) | +0.500 | ceiling reached (killed) |
| `dynamic-object-aware-egomotion` | b3 | 0.000 | 1.000 | — | — | — | **1.000** (cand_0001) | +1.000 | ceiling reached (killed) |
| `energy-ac-optimal-power-flow` | b3 | 0.400 | 0.500 | 0.300 | 0.900 | 0.800 | **0.900** (cand_0003) | +0.500 |  |
| `energy-market-pricing` | b3 | 0.000 | 0.500 | 0.700 | 0.900 | 0.800 | **0.900** (cand_0003) | +0.900 |  |
| `enterprise-information-search` | b3 | 0.000 | 1.000 | 1.000 | 1.000 | — | **1.000** (cand_0003) | +1.000 | ceiling reached (killed) |
| `exceltable-in-ppt` | b3 | 0.900 | 1.000 | — | — | — | **1.000** (cand_0001) | +0.100 | ceiling reached (killed) |
| `jpg-ocr-stat` | b3 | 0.800 | 1.000 | — | — | — | **1.000** (cand_0001) | +0.200 | ceiling reached (killed) |
| `lake-warming-attribution` | b3 | 0.100 | 0.600 | 1.000 | — | — | **1.000** (cand_0002) | +0.900 | ceiling reached (killed) |
| `organize-messy-files` | b3 | 0.500 | 0.600 | 0.600 | 0.900 | 0.900 | **0.900** (cand_0004) | +0.400 |  |
| `pdf-excel-diff` | b3 | 0.900 | 1.000 | 1.000 | — | — | **1.000** (cand_0002) | +0.100 | ceiling reached (killed) |
| `pptx-reference-formatting` | b3 | 1.000 | — | — | — | — | **1.000** (seed) | +0.000 | saturated (killed) |
| `protein-expression-analysis` | b3 | 1.000 | — | — | — | — | **1.000** (seed) | +0.000 | saturated (killed) |
| `reserves-at-risk-calc` | b3 | 0.000 | 0.000 | 0.300 | 0.900 | 0.800 | **0.900** (cand_0003) | +0.900 |  |
| `sales-pivot-analysis` | b3 | 0.000 | 1.000 | — | — | — | **1.000** (cand_0001) | +1.000 | ceiling reached (killed) |
| `shock-analysis-demand` | b3 | 0.000 | 0.400 | 0.300 | 0.900 | 0.800 | **0.900** (cand_0003) | +0.900 |  |
| `shock-analysis-supply` | b3 | 0.100 | 0.600 | 0.300 | 0.900 | 0.800 | **0.900** (cand_0003) | +0.800 |  |
| `simpo-code-reproduction` | b3 | 0.800 | 0.900 | 0.300 | 0.900 | 0.800 | **0.900** (cand_0003) | +0.100 |  |
| `spring-boot-jakarta-migration` | b3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | **0.000** (cand_0004) | +0.000 |  |
| `threejs-structure-parser` | b3 | 0.500 | 1.000 | 1.000 | 1.000 | — | **1.000** (cand_0003) | +0.500 | ceiling reached (killed) |
| `weighted-gdp-calc` | b3 | 0.800 | 1.000 | 1.000 | — | — | **1.000** (cand_0002) | +0.200 | ceiling reached (killed) |
| `xlsx-recover-data` | b3 | 0.000 | 0.700 | 1.000 | — | — | **1.000** (cand_0002) | +1.000 | ceiling reached (killed) |

## Wins — tasks reaching val=1.0

| task | batch | baseline | best | lift | winning cand |
|---|---|---|---|---|---|
| `edit-pdf` | b1 | 0.900 | 1.000 | +0.100 | cand_0002 |
| `court-form-filling` | b1 | 0.300 | 1.000 | +0.700 | cand_0002 |
| `adaptive-cruise-control` | b1 | 0.700 | 1.000 | +0.300 | cand_0004 |
| `hvac-control` | b1 | 1.000 | 1.000 | +0.000 | seed |
| `r2r-mpc-control` | b1 | 0.300 | 1.000 | +0.700 | cand_0002 |
| `3d-scan-calc` | b1 | 1.000 | 1.000 | +0.000 | seed |
| `syzkaller-ppdev-syzlang` | b1 | 0.700 | 1.000 | +0.300 | cand_0002 |
| `multilingual-video-dubbing` | b1 | 0.700 | 1.000 | +0.300 | cand_0004 |
| `flood-risk-analysis` | b1 | 1.000 | 1.000 | +0.000 | seed |
| `sec-financial-report` | b2 | 0.900 | 1.000 | +0.100 | cand_0002 |
| `grid-dispatch-operator` | b2 | 0.000 | 1.000 | +1.000 | cand_0002 |
| `threejs-to-obj` | b2 | 1.000 | 1.000 | +0.000 | seed |
| `pddl-airport-planning` | b2 | 0.000 | 1.000 | +1.000 | cand_0002 |
| `citation-check` | b3 | 1.000 | 1.000 | +0.000 | seed |
| `dapt-intrusion-detection` | b3 | 1.000 | 1.000 | +0.000 | seed |
| `data-to-d3` | b3 | 0.500 | 1.000 | +0.500 | cand_0002 |
| `dynamic-object-aware-egomotion` | b3 | 0.000 | 1.000 | +1.000 | cand_0001 |
| `enterprise-information-search` | b3 | 0.000 | 1.000 | +1.000 | cand_0003 |
| `exceltable-in-ppt` | b3 | 0.900 | 1.000 | +0.100 | cand_0001 |
| `jpg-ocr-stat` | b3 | 0.800 | 1.000 | +0.200 | cand_0001 |
| `lake-warming-attribution` | b3 | 0.100 | 1.000 | +0.900 | cand_0002 |
| `pdf-excel-diff` | b3 | 0.900 | 1.000 | +0.100 | cand_0002 |
| `pptx-reference-formatting` | b3 | 1.000 | 1.000 | +0.000 | seed |
| `protein-expression-analysis` | b3 | 1.000 | 1.000 | +0.000 | seed |
| `sales-pivot-analysis` | b3 | 0.000 | 1.000 | +1.000 | cand_0001 |
| `threejs-structure-parser` | b3 | 0.500 | 1.000 | +0.500 | cand_0003 |
| `weighted-gdp-calc` | b3 | 0.800 | 1.000 | +0.200 | cand_0002 |
| `xlsx-recover-data` | b3 | 0.000 | 1.000 | +1.000 | cand_0002 |

## Remaining stuck at 0.000

- `financial-modeling-qa` (batch2) — genuinely hard (verifier runs, agent can't produce correct output)
- `python-scala-translation` (batch2) — Scala/GraalVM runtime crash inside container
- `spring-boot-jakarta-migration` (batch3) — JVM tooling / Java migration tooling infra

## Files

- `summary.md` — this file
- `results.json` — raw per-task per-tag data (5 candidate slots)
- `heatmap.html` — interactive heatmap
- `per-task-logs/<task>.md` — 43 files, one per task with per-trial rewards