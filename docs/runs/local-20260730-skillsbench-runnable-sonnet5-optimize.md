<!-- Local benchmark run detail page. Linked from https://skillberry-ai.github.io/cap-evolve/benchmarks.html -->

> **Local optimization run** (recorded on the benchmark-history branch).
> Ran outside the CI workflow (source: `bcarmeli`); optimizer proposed edits over the shared
> office-document skills (docx/pptx/xlsx/pdf) against a **43-task RUNNABLE subset** of SkillsBench.
> Agent under test: `claude-sonnet-5`; optimizer: `claude-opus-4-8`. LSF submission id `1412177`
> on CCC compute node `cccxc445`.

> **Task subset:** the full 87-task suite hit two CCC-specific infrastructure classes in a prior
> run (`network_mode`/task-compose conflicts on ~14 tasks + `python:3.12-slim` base-image postinst
> failures on ~26 tasks + ~4 tasks on exotic base images). We filtered to the 43 tasks that ran to
> a verifier verdict on seed0 of that prior attempt — the split lives in
> `.capevolve/project/split_ids.runnable.json`. This is a **strict subset** of the SkillsBench
> "full" tier; results are NOT directly comparable to 87-task runs.

> **Run cancelled early at iter 4:** the optimizer step for `cand_0004` wedged after ~13 min of
> normal token spend (270k tokens, $48.78 cumulative) with no further token growth or file writes
> over the next ~2h. Job manually killed under the pre-agreed 90-min-stall rule. Best-so-far
> (`cand_0002` @ 17.05%) preserved; a `--resume` submission can pick up from iter 4 once the
> underlying hang cause is understood. Iters 5–7 not attempted.


# Run summary — `run_runnable_iter7_v1`

- **Benchmark:** `skillsbench` (43-task runnable subset)
- **Agent under test:** `claude-sonnet-5`
- **Optimizer:** `claude-opus-4-8`
- **Tasks / trials:** 43 tasks · 3 trials
- **Iterations (actual / cap):** 3 completed + 1 attempted (hung) / 7 · **2 accepted**
- **Split discipline:** fit-metric (train == val == 43-task subset; test = 3 tasks overlapping val, kept only to satisfy cap-evolve's finalize step)
- **Best candidate:** `cand_0002`
- **Termination:** cancelled at 09:33 EDT on 2026-07-31 (iter 4 optimizer hung; see "Termination" section below)
- **CCC infrastructure:** rootless podman + patched `ubuntu:24.04` base (chown/useradd/dpkg-statoverride wrappers); see `scripts/ccc/` and `docs/RUN_ON_CCC.md` (PR pending)

## Headline

| | baseline (`seed`) | best (`cand_0002`) |
|---|---|---|
| val_reward (mean) | 0.1395 ± 0.0511 | **0.1705 ± 0.0541** (17.05%) |
| Δ vs baseline | — | **+0.0311 (+3.11pp)** |
| pass_at_1 (fully passing across 3 trials) | 4 / 43 (9.3%) | **4 / 43** (9.3%) |
| partial credit (0 < reward < 1) | 4 / 43 | **7 / 43** |
| errored (infra) | 0 / 43 | 0 / 43 |
| eval wall-clock (this candidate) | 242m 2s | 195m 47s |
| cumulative optimizer $ spent | — | $48.78 |
| cumulative runner wall-clock | — | 52,701 s (~14.6 h Sonnet-5) |
| total wall-clock (submit → kill) | — | ~18h 15min |

## Iterations — performance per step

| iter | candidate | parent | val_reward | Δ vs parent | gate reason | accepted? | opt $ | opt seconds | eval seconds |
|---|---|---|---|---|---|---|---|---|---|
| 0 | `seed` | — | 0.1395 | — | (baseline) | — | — | — | 14522 |
| **1** | **`cand_0001`** | `seed` | **0.1473** | **+0.0078** | paired Δ̄=+0.0078 > 0.2·SE=0.0072 (n=43) | **✓** | $14.01 | 1399 | 13254 |
| **2** | **`cand_0002`** | `cand_0001` | **0.1705** | **+0.0233** | paired Δ̄=+0.0233 > 0.2·SE=0.0052 (n=43) | **✓** ← best | $15.33 | 2703 | 11747 |
| 3 | `cand_0003` | `cand_0002` | 0.1551 | −0.0155 | paired Δ̄=−0.0155 ≤ 0.2·SE=0.0049 (n=43) | ✗ | $15.08 | 1400 | 13179 |
| 4 | `cand_0004` | `cand_0002` | (not scored — optimizer hung; see "Termination") | — | — | — | ~$4.35 partial | ~800+ (hung) | — |
| 5 | — | — | not attempted | — | — | — | — | — | — |
| 6 | — | — | not attempted | — | — | — | — | — | — |
| 7 | — | — | not attempted | — | — | — | — | — | — |

**Trajectory:** two accepted-gate steps in a row (cand_0001 +0.78pp, cand_0002 +2.33pp), then one
rejected step (cand_0003 −1.55pp — the paired-SE gate correctly filtered a regression), then a
hung optimizer step on iter 4. Cumulative gain: **+3.11pp** over the seed skills.

## Passing tasks (best = `cand_0002`, all 3 trials pass — 4 total)

- ✓ `3d-scan-calc`
- ✓ `edit-pdf`
- ✓ `protein-expression-analysis`
- ✓ `syzkaller-ppdev-syzlang`

## Partial credit (`cand_0002`, 0 < avg reward < 1)

| task | reward | trials |
|---|---|---|
| `adaptive-cruise-control` | 0.667 | 2/3 |
| `court-form-filling` | 0.667 | 2/3 |
| `multilingual-video-dubbing` | 0.667 | 2/3 |
| `flood-risk-analysis` | 0.333 | 1/3 |
| `hvac-control` | 0.333 | 1/3 |
| `invoice-fraud-detection` | 0.333 | 1/3 |
| `r2r-mpc-control` | 0.333 | 1/3 |

## Baseline (`seed`) vs best (`cand_0002`) — what changed

- **Newly-passing (gained fully in iters 1–2):** `edit-pdf`, `syzkaller-ppdev-syzlang`, `3d-scan-calc`.
- **Newly-partial (gained credit in iters 1–2):** `court-form-filling`, `multilingual-video-dubbing`, `flood-risk-analysis`, `invoice-fraud-detection`.
- **Regressed from full pass to partial:** `adaptive-cruise-control`, `hvac-control`, `r2r-mpc-control` (all 3 were 3/3 at baseline).

The optimizer's edits improved 7 tasks (4 fully, 3 partially) while regressing 3 from full pass to
partial. The paired-SE gate correctly measured the aggregate improvement (+0.0233pp on iter 2)
despite the individual regressions.

## Errored tasks

None observed across the 4 completed evaluations (baseline + iters 1–3). The "runnable" filter
(built on seed0 of the prior 87-task attempt) held cleanly.

In-run per-rollout **timeout rate:** ~19% (agent idle > 600s or wall-clock budget), consistent
with Sonnet 5's per-task variance on this task mix. Cap-evolve treats timeouts as `reward=0.0`
(failure, not error) — they still enter the paired-SE gate cleanly.

## Termination — iter 4 optimizer hang

Timeline:

- **2026-07-30 15:18** — LSF submit
- **2026-07-31 01:16** — iter 2 accepted (cand_0002 @ 17.05%, best-so-far)
- **2026-07-31 07:31** — iter 3 rejected (cand_0003 @ 15.51%, −1.55pp)
- **2026-07-31 07:32** — iter 4 optimizer started (`work/cand_0004/` created)
- **2026-07-31 07:44** — last state.json write; optimizer_usd = $48.78, optimizer_tokens = 269,848
- **2026-07-31 07:44 → 09:33** — **~1h 49min of zero forward progress:** no file writes anywhere
  under `run_runnable_iter7_v1/`, no growth in optimizer_usd or optimizer_tokens, no rollout
  activity, LSF stderr empty. Bench_cwd also silent.
- **2026-07-31 09:33** — job manually killed under the pre-agreed 90-min-stall rule.

Suspected root cause is not confirmed but the plausible candidates are:
- **Anthropic API stall** — the `claude` CLI holding an open HTTP request that never terminates
  (rare, but possible given ETE LiteLLM proxy behavior we've seen). No error was logged; the
  process was likely blocked in read().
- **Cap-evolve internal step between optimizer completion and eval launch** got wedged — but
  such a step would normally take seconds, not hours.
- Not an infra failure on the tasks side — bench_jobs shows no new activity for the entire hang
  window, so no container was in-flight.

Best-so-far (`cand_0002` @ 17.05%) is preserved in-place; a `--resume` submission will re-enter
iter 4 from the same parent (cand_0002) and re-propose. Iters 5–7 remain unattempted.

## Tasks excluded from this subset (44 tasks not currently runnable on CCC podman)

Failure classes documented in the prior 87-task attempt:

- **`python:3.12-slim` base image** (~26 tasks): apt postinst chown/setuid fails; our patched-ubuntu wrappers don't apply. Needs equivalent patching for the slim Python base.
- **Task-level `docker-compose.yaml` with `networks:` block** (~14 tasks): conflicts with our forced `network_mode: host` (which we use to skip aardvark-dns on compute nodes without systemd).
- **Exotic base images** (~4 tasks): `jasonish/suricata`, `gcr.io/oss-fuzz-base/*`, `bugswarm/cached-images`.

Excluded task list (see `split_ids.runnable.json` for the runnable list):

`ada-bathroom-plan-repair`, `azure-bgp-oscillation-route-leak`, `bike-rebalance`,
`civ6-adjacency-optimizer`, `crystallographic-wyckoff-position-analysis`, `debug-trl-grpo`,
`dialogue-parser`, `earthquake-phase-association`, `earthquake-plate-calculation`,
`econ-detrending-correlation`, `energy-unit-commitment`, `exam-block-sequencing`,
`exoplanet-detection-period`, `fix-build-agentops`, `fix-build-google-auto`, `fix-druid-loophole-cve`,
`fix-erlang-ssh-cve`, `fix-visual-stability`, `flink-query`, `glm-lake-mendota`,
`gravitational-wave-detection`, `lab-unit-harmonization`, `latex-formula-extraction`, `lean4-proof`,
`llm-prefix-cache-replay`, `manufacturing-codebook-normalization`, `manufacturing-equipment-maintenance`,
`manufacturing-fjsp-optimization`, `mario-coin-counting`, `mars-clouds-clustering`, `parallel-tfidf-search`,
`paratransit-routing`, `pddl-tpp-planning`, `powerlifting-coef-calc`, `quantum-numerical-simulation`,
`radar-vital-signs`, `react-performance-debugging`, `seismic-phase-picking`, `setup-fuzzing-py`,
`software-dependency-audit`, `suricata-custom-exfil`, `tictoc-unnecessary-abort-detection`,
`travel-planning`, `video-silence-remover`.

## CCC-specific workarounds validated by this run

- `scripts/ccc/setup_podman.sh` — patched `ubuntu:24.04` base with wrappers for `chown`, `chgrp`, `useradd`, `groupadd`, `usermod`, `groupmod`, `adduser`, `addgroup`, `dpkg-statoverride`; pre-installed `python3`/`python3-pip`/`curl`/`poppler-utils`/`build-essential`; private dbus; rootless podman socket.
- `scripts/ccc/run_ccc_experiment.sh` — cap-evolve wrapper with `--resume` support for LSF walltime recovery.
- `scripts/ccc/submit_ccc_experiment.sh` — LSF `bsub` submitter with sensible defaults.
- Adapter reads `SKILLSBENCH_MODEL` / `SKILLSBENCH_AGENT` / `SKILLSBENCH_SANDBOX_USER` from `.env`.

See PR **add-ccc-support** (pushed to `bcarmeli/cap-evolve`, awaiting review).

## Artifacts

Local run — preserved on the recording host at
`.capevolve/run_runnable_iter7_v1_KILLED_iter4_optimizer_hung_2h/` (gitignored, per-run). To
resume, rename back to `run_runnable_iter7_v1/` and re-submit with `--resume`.

- `baseline.json` — full per-task rewards, 43 tasks
- `events.jsonl` — event timeline (splits, evaluate, step-accept/reject; last entry is iter 3 rejection)
- `state.json` — running iters/USD/tokens counters (frozen at 3 iters spent, $48.78 optimizer, 269,848 tokens)
- `rollouts/val/*.json` — 516 per-rollout JSONs (4 evaluations × 3 trials × 43 tasks)
- `bench_jobs/seed/seed{0,1,2}/*/…` — BenchFlow-level artifacts (per-task result.json + trajectory)
- `work/cand_XXXX/{INSTRUCTIONS.md, RUNMAP.md, prior_iterations/…}` — optimizer's working directory per iter (cand_0004 wedged with partial state)

**Batch submission logs:** `/dccstor/knewedge2/boazc/ccc_logs/1412177.{stdout,stderr}` on CCC.

## Update log

- **2026-07-31 06:35 EDT** — First shareable snapshot: baseline + iter 1 + iter 2 accepted. Iter 3 rollouts at ~67%. Doc had improper markdown tables (fixed in follow-up commit).
- **2026-07-31 09:33 EDT** — Iter 3 rejected (cand_0003 @ 15.51%). Iter 4 optimizer wedged; job manually killed under 90-min-stall rule. Final numbers: best = cand_0002 @ 17.05% (+3.11pp over seed). Iters 5–7 not attempted.
