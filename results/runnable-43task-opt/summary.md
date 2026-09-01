# runnable-43task-opt — Sonnet-5 + Opus-4.8 (cancelled at iter 4)

**Date:** 2026-07-30 → 2026-07-31 (LSF 1412177 on `cccxc445`)
**Agent model:** claude-sonnet-5
**Optimizer model:** claude-opus-4-8
**Task set:** 43-task RUNNABLE subset (see `all87-broken-wiring/` for how this was derived)
**Split discipline:** fit-metric (train == val == 43 tasks; test = 3 dummy tasks overlapping val)
**Cap-evolve spec:** `.capevolve/project/capevolve.runnable.yaml`
**Run dir:** `.capevolve/run_runnable_iter7_v1_KILLED_iter4_optimizer_hung_2h/`
**Merged doc on `benchmark-history`:** [local-20260730-skillsbench-runnable-sonnet5-optimize.md](https://github.com/skillberry-ai/cap-evolve/blob/benchmark-history/docs/runs/local-20260730-skillsbench-runnable-sonnet5-optimize.md)

## Aggregate

| Metric | baseline (seed) | best (cand_0002) |
|---|---|---|
| val_reward (mean) | **0.1395** ± 0.0511 | **0.1705** ± 0.0541 (17.05%) |
| Δ vs baseline | — | **+0.0311 (+3.11 pp)** |
| pass_at_1 (fully passing 3/3 trials) | 4 / 43 (9.3%) | 4 / 43 (9.3%) |
| partial credit (0 < reward < 1) | 4 / 43 | **7 / 43** |
| errored (infra) | 0 / 43 | 0 / 43 |
| Wall clock (this eval) | 242m 2s | 195m 47s |

## Iterations

| iter | candidate | parent | val | Δ vs parent | gate | accepted? |
|---|---|---|---|---|---|---|
| 0 | `seed` | — | 0.1395 | — | (baseline) | — |
| 1 | `cand_0001` | `seed` | 0.1473 | +0.0078 | paired Δ̄=+0.0078 > 0.2·SE=0.0072 | ✓ |
| **2** | **`cand_0002`** | `cand_0001` | **0.1705** | **+0.0233** | paired Δ̄=+0.0233 > 0.2·SE=0.0052 | ✓ ← **best** |
| 3 | `cand_0003` | `cand_0002` | 0.1551 | −0.0155 | paired Δ̄=−0.0155 ≤ 0.2·SE=0.0049 | ✗ |
| 4 | `cand_0004` | `cand_0002` | *not scored* | — | — | HUNG (killed) |

## Cost + wall clock

| | value |
|---|---|
| Optimizer $ spent (through iter 3) | $44.43 |
| Optimizer $ partial in iter 4 (before hang) | ~$4.35 |
| **Cumulative optimizer $ spent** | **$48.78** |
| Runner $ (bench telemetry) | $0 (telemetry gap) |
| Runner wall clock | 52,701 s (~14.6 h Sonnet-5) |
| Total wall clock (submit → kill) | ~18h 15min |

## Passing tasks (best = cand_0002, all 3 trials pass)

- ✓ `3d-scan-calc`
- ✓ `edit-pdf`
- ✓ `protein-expression-analysis`
- ✓ `syzkaller-ppdev-syzlang`

## Partial credit (cand_0002, 0 < avg reward < 1)

| task | reward | trials |
|---|---|---|
| adaptive-cruise-control | 0.667 | 2/3 |
| court-form-filling | 0.667 | 2/3 |
| multilingual-video-dubbing | 0.667 | 2/3 |
| flood-risk-analysis | 0.333 | 1/3 |
| hvac-control | 0.333 | 1/3 |
| invoice-fraud-detection | 0.333 | 1/3 |
| r2r-mpc-control | 0.333 | 1/3 |

## Baseline vs best — what changed

- **Newly passing (gained fully in iters 1–2):** `edit-pdf`, `syzkaller-ppdev-syzlang`, `3d-scan-calc`.
- **Newly partial (gained credit):** `court-form-filling`, `multilingual-video-dubbing`, `flood-risk-analysis`, `invoice-fraud-detection`.
- **Regressed pass → partial:** `adaptive-cruise-control`, `hvac-control`, `r2r-mpc-control` (all were 3/3 at baseline).

Optimizer improved 7 tasks (4 fully, 3 partial), regressed 3 pass → partial. Paired-SE gate correctly banked the aggregate gain (+0.0233 pp on iter 2) despite individual regressions.

## Termination — iter 4 optimizer hang

- 2026-07-31 07:32 EDT — iter 4 optimizer started (`work/cand_0004/`).
- 2026-07-31 07:44 EDT — last state.json write; optimizer_usd=$48.78, optimizer_tokens=269,848.
- 2026-07-31 07:44 → 09:33 EDT — **~1h 49min of zero forward progress**: no file writes, no token growth, LSF stderr empty. Bench_cwd also silent.
- 2026-07-31 09:33 EDT — job manually killed under the pre-agreed 90-min-stall rule.

Suspected cause (unconfirmed): the `claude` CLI held an Anthropic API HTTP request that never terminated (rare, plausible on ETE LiteLLM). Not an infra failure on the task side — bench_jobs shows no container activity in the entire hang window.

## Next moves (open)

- **A. `--resume` from cand_0002.** Rename the KILLED dir back to `run_runnable_iter7_v1/`, resubmit with `--resume`. Iters 5–7 attempt on top of the current best.
- **B. Investigate the iter 4 hang cause first.** Especially the Anthropic API path via ETE LiteLLM — otherwise the same hang might repeat.
- **C. Switch strategy** (see `SKILLSBENCH_INVENTORY.md`) to task-by-task (EvoSkills-style) optimization. Only 21/87 tasks actually ship the office skills the seed targets; task-by-task removes the out-of-domain drag.
- **D. Accept +3.11 pp as the terminal result.** No further compute.

