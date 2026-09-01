# SkillsBench task-by-task-87 — aggregate summary

_Generated 2026-08-28 · 87 tasks · dedicated LSF host per task (CCC) or dedicated Docker container (Mac) · 10 trials per candidate · up to 4 iterations · Sonnet-5 agent + Opus-4.8 optimizer._

## TL;DR

- **Pass rate: 64/87 = 73.6%** (task reaches val ≥ 1.0 or final_test ≥ 1.0).
- **Beats EvoSkill's 71.1% headline by +2.5 pp** on the same 87-task benchmark.
- **NO_SIGNAL: 10** tasks (scored 0.0 for both seed AND every optimizer candidate — cap-evolve had no lever).
- **Mean best** over all 87: **0.825**.
- **Median iterations spent**: **4.0**.

## Two cuts (EvoSkill pass_rate metric)

| cut | denominator | passes | pass_rate | vs EvoSkill 71.1% |
|---|---|---|---|---|
| 1. all tasks | 87 | 64 | **73.6%** | +2.5 pp |
| 2. excl. 10 no-signal | 77 | 64 | **83.1%** | +12.0 pp |

## Overall stats — counts by status

| status | count |
|---|---|
| DONE | 35 |
| KILLED_saturated | 19 |
| KILLED_ceiling | 21 |
| KILLED_val_1.0 | 2 |
| NO_SIGNAL | 10 |
| **TOTAL** | **87** |

## Per-category breakdown

| category | total | eval | no-signal | pass | pass_rate | mean best | EvoSkill | Δ |
|---|---|---|---|---|---|---|---|---|
| cybersecurity | 7 | 6 | 1 | 4 | 57% | 0.731 | 76% | −19 pp |
| finance-economics | 9 | 8 | 1 | 5 | 56% | 0.733 | 82% | −26 pp |
| industrial-physical-systems | 14 | 14 | 0 | 12 | 86% | 0.973 | 64% | **+22 pp** |
| mathematics-or-formal-reasoning | 8 | 8 | 0 | 8 | 100% | 1.000 | n/a | — |
| media-content-production | 5 | 5 | 0 | 5 | 100% | 1.000 | 69% | **+31 pp** |
| natural-science | 14 | 11 | 3 | 10 | 71% | 0.774 | 84% | −13 pp |
| office-white-collar | 14 | 14 | 0 | 11 | 79% | 0.950 | 73% | **+6 pp** |
| software-engineering | 16 | 11 | 5 | 9 | 56% | 0.675 | 68% | −12 pp |

## NO_SIGNAL tasks (10)

**4 tasks where the container built but the agent produced empty tool_calls** — cap-evolve harness ran, no agent activity recorded:
- `earthquake-phase-association` [natural-science / seismology]
- `fix-build-google-auto` [software-engineering / build-repair]
- `fix-visual-stability` [software-engineering / performance-optimization]
- `seismic-phase-picking` [natural-science / seismology]

**6 tasks where cap-evolve ran to completion but no candidate moved off zero:**
- `financial-modeling-qa` [finance-economics]
- `fix-build-agentops` [software-engineering / build-repair]
- `fix-druid-loophole-cve` [software-engineering / cve-triage]
- `python-scala-translation` [software-engineering / language-translation]
- `quantum-numerical-simulation` [natural-science / physics]
- `spring-boot-jakarta-migration` [software-engineering / migration]

## Sources

- **c3-v1** (44 tasks) — c3 worktree v1 runs (bucket-1/2/3 unblocks, freshest)
- **c1-v1** (30 tasks) — c1 worktree v1 (original task-by-task-43)
- **c2-v2** (6 tasks) — c2 worktree v2 reruns (previously contaminated 6 tasks)
- **c1-v5** (4 tasks) — c1 worktree v5 rerun (post 2026-08-24 full-cache-cleared)
- **c1-tA** (3 tasks) — c1 worktree Track A extension (iters 3–4)
- **mac-v2** (7 tasks) — Boaz's Mac + Docker Desktop retry of the 7 CCC-blocked tasks
  - Wins (2): `glm-lake-mendota` → 1.0, `offer-letter-generator` → 1.0
  - Evaluated but low: `suricata-custom-exfil` → 0.67
  - Still no signal (4): `earthquake-phase-association`, `fix-build-google-auto`, `fix-visual-stability`, `seismic-phase-picking`
