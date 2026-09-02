# SkillsBench task-by-task-87 — aggregate summary

_Generated 2026-08-28 · 87 tasks · dedicated LSF host per task (CCC) or dedicated Docker container (Mac) · 10 trials per candidate · up to 4 iterations · Sonnet-5 agent + Opus-4.8 optimizer._

## TL;DR

- **Pass rate: 64/87 = 73.6%** (task reaches val ≥ 1.0 or final_test ≥ 1.0).
- **Statistically indistinguishable from EvoSkill's 71.1%**: +2.5 pp against a binomial
  standard error of 4.73 pp — **0.52 SE** (two-proportion z = 0.36, p ≈ 0.72). Not a win.
  See "Reading the comparison honestly" below before quoting any of these numbers.
- **NO_SIGNAL: 10** tasks (scored 0.0 for both seed AND every optimizer candidate — cap-evolve had no lever).
- **Mean best** over all 87: **0.8422**.
- **Median iterations spent**: **4.0**.

## Two cuts (EvoSkill pass_rate metric)

| cut | denominator | passes | pass_rate | vs EvoSkill 71.1% |
|---|---|---|---|---|
| 1. all tasks | 87 | 64 | **73.6%** | +2.5 pp (0.52 SE — noise) |
| 2. excl. 10 no-signal | 77 | 64 | **83.1%** | +12.0 pp (see caveat below) |

## Reading the comparison honestly

Three things make the headline weaker than it looks. All three are reproducible from
`results.json` in this directory.

**1. The pass metric takes the better of two splits.** The rule is `best(val) ≥ 1.0` **OR**
`final_test ≥ 1.0`. Only 34 of 87 tasks have a `final_test` at all, and **45 of the 64
passes are val-only**. Recomputing with test where available and val otherwise:

> **62/87 = 71.3%** — versus EvoSkill's 71.1%. A tie, not a +2.5 pp lead.

This matters because val overstates: `insights/pass_k_analysis.md` §1 lists val-1.0 tasks
whose test reward collapsed (`energy-unit-commitment` 1.0 → 0.1, `organize-messy-files`
0.9 → 0.0), and `handoffs/C4_HANDOFF.md` says outright *"Report test reward, not val."*

**2. `pass^5 = 67.1%` on raw data only** — *below* EvoSkill's 71.1%. See
`insights/pass_k_analysis.md` §3 for the pass^k derivation (tau-bench definition,
all-of-k-succeed). Our 10 trials measure within-run trial noise; EvoSkill's 5 runs measure
optimizer-outcome variance. These are not the same quantity.

**3. Cut 2 is not apples-to-apples.** Of the 10 NO_SIGNAL tasks dropped from the
denominator, only 4 are infrastructure failures — the other 6 ran to completion and never
moved off zero, which are genuine optimizer failures. `fix-visual-stability` is a
benchmark-side broken `docker-compose.yml`. EvoSkill gets no equivalent courtesy, so
"83.1%" is not a number to put beside their 71.1%.

`docs/RESULTS.md` on `main` states the house position on this comparison directly:
*"**Not directly comparable to EvoSkills' 71.1%.** Different paradigm."* That remains the
correct framing.

> **Known inconsistency:** `ui/heatmap.html` renders **63/87 = 72.4%** for this same sweep.
> Its embedded `DATA` is a stale reduced copy of `results.json` missing `final_test`, so it
> cannot see `fix-erlang-ssh-cve` (the one task passing on test but not val). The heatmap is
> wrong, not this file. Regenerating it is tracked as follow-up work.

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
