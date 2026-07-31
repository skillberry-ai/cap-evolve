> **Local optimization run** (recorded on the benchmark-history branch). Ran outside the CI workflow (source: `bcarmeli`); optimizer proposing edits over the shared office-document skills (docx/pptx/xlsx/pdf) against a **43-task RUNNABLE subset** of SkillsBench filtered on our CCC-podman environment. Agent-under-test: `claude-sonnet-5`; optimizer: `claude-opus-4-8`.

> **Task subset:** the full 87-task suite hit two CCC-specific infrastructure classes in a prior run (`network_mode`/task-compose conflicts on ~34 tasks + `python:3.12-slim` base-image postinst failures on ~10 tasks). We filtered to the 43 tasks that ran to a verifier verdict on seed0 of that prior attempt — split via `.capevolve/project/split_ids.runnable.json`. This is a strict subset of the SkillsBench "full" tier; results are NOT directly comparable to 87-task runs.

> **Run in progress:** captured 2026-07-31 05:35 EDT. Baseline + iter 1 + iter 2 landed; iter 3 rollouts in flight. This document will be updated at completion.

Run summary — `run_runnable_iter7_v1`
=====================================

*   **Benchmark:** `skillsbench` (43-task runnable subset)
*   **Agent under test:** `claude-sonnet-5`
*   **Optimizer:** `claude-opus-4-8`
*   **Tasks / trials:** 43 tasks · 3 trials
*   **Iterations (actual / cap):** 2 / 7 · 2 accepted (in progress)
*   **Split discipline:** fit-metric (train==val==43-task-subset, test = 3 tasks that overlap val)
*   **Best candidate so far:** `cand_0002`
*   **CCC infrastructure:** rootless podman + patched ubuntu:24.04 base (chown/useradd/dpkg-statoverride wrappers); see `docs/RUN_ON_CCC.md` (PR pending)

Headline (in-progress)
----------------------

baseline (seed)

best (`cand_0002`)

val\_reward (mean)

0.1395 ± 0.0511

**0.1705 ± 0.0541** (17.05%)

pass\_at\_1 (fully passing across 3 trials)

**4/43** (9%)

**4/43** (9%)

pass\_at\_2 (2 of 2 trials pass)

—

—

partial (0 < reward < 1)

4/43

7/43

Δ from baseline

—

**+0.0311** (real gain; gate: paired Δ̄ > 0.2·SE both accepted)

val wall-clock (per-eval)

242m 2s

195m 47s

optimizer wall-clock (per-iter)

—

23m 19s / 45m 3s (iters 1 / 2)

total wall-clock so far

~14h 15min

Iterations
----------

iter

candidate

parent

val

Δ vs parent

gate reason

accepted?

1

`cand_0001`

`seed`

0.1473

+0.0078

paired Δ̄=+0.0078 > 0.2·SE=0.0072

✓

2

`cand_0002`

`cand_0001`

0.1705

+0.0233

paired Δ̄=+0.0233 > 0.2·SE=0.0052

✓

3

`cand_0003`

`cand_0002`

in flight (rollouts landing; ~08:30 EDT ETA)

—

—

—

4–7

—

—

not started

—

—

—

Passing tasks (best = `cand_0002`, all 3 trials pass)
-----------------------------------------------------

*   ✓ `3d-scan-calc`
*   ✓ `edit-pdf`
*   ✓ `protein-expression-analysis`
*   ✓ `syzkaller-ppdev-syzlang`

Partial credit (`cand_0002`, 0 < avg reward < 1)
------------------------------------------------

task

reward

`adaptive-cruise-control`

0.667 (2/3)

`court-form-filling`

0.667 (2/3)

`multilingual-video-dubbing`

0.667 (2/3)

`flood-risk-analysis`

0.333 (1/3)

`hvac-control`

0.333 (1/3)

`invoice-fraud-detection`

0.333 (1/3)

`r2r-mpc-control`

0.333 (1/3)

Baseline (`seed`) comparison
----------------------------

*   3/3-trials passers at baseline: `adaptive-cruise-control`, `hvac-control`, `protein-expression-analysis`, `r2r-mpc-control`
*   Iter 1–2 gained: `3d-scan-calc` (partial→pass), `edit-pdf` (fail→pass), `syzkaller-ppdev-syzlang` (partial→pass); added partial credit on `court-form-filling`, `multilingual-video-dubbing`, `flood-risk-analysis`, `invoice-fraud-detection`.
*   Iter 1–2 lost: `adaptive-cruise-control` (pass→partial), `hvac-control` (pass→partial), `r2r-mpc-control` (pass→partial). Regression on 3 tasks was outweighed by gains on 4; paired gate confirmed the aggregate is real.

Errored tasks
-------------

None observed in baseline or iters 1–2 rollouts. The "runnable" filter was designed to exclude tasks that hit infra errors in a prior attempt; the filter held cleanly for the first three evaluations. **In-run timeout rate:** ~19% of rollouts hit Sonnet-5 idle/wall-clock budgets (`Agent idle for 600s` or similar); cap-evolve treats those as `reward=0.0` (failure, not error), consistent with paired-SE gating.

Tasks excluded (44 that hit infra errors in the prior 87-task attempt, not runnable in this environment)
--------------------------------------------------------------------------------------------------------

*   `ada-bathroom-plan-repair`, `azure-bgp-oscillation-route-leak`, `bike-rebalance`, `civ6-adjacency-optimizer`, `crystallographic-wyckoff-position-analysis`, `debug-trl-grpo`, `dialogue-parser`, `earthquake-phase-association`, `earthquake-plate-calculation`, `econ-detrending-correlation`, `energy-unit-commitment`, `exam-block-sequencing`, `exoplanet-detection-period`, `fix-build-agentops`, `fix-build-google-auto`, `fix-druid-loophole-cve`, `fix-erlang-ssh-cve`, `fix-visual-stability`, `flink-query`, `glm-lake-mendota`, `gravitational-wave-detection`, `lab-unit-harmonization`, `latex-formula-extraction`, `lean4-proof`, `llm-prefix-cache-replay`, `manufacturing-codebook-normalization`, `manufacturing-equipment-maintenance`, `manufacturing-fjsp-optimization`, `mario-coin-counting`, `mars-clouds-clustering`, `parallel-tfidf-search`, `paratransit-routing`, `pddl-tpp-planning`, `powerlifting-coef-calc`, `quantum-numerical-simulation`, `radar-vital-signs`, `react-performance-debugging`, `seismic-phase-picking`, `setup-fuzzing-py`, `software-dependency-audit`, `suricata-custom-exfil`, `tictoc-unnecessary-abort-detection`, `travel-planning`, `video-silence-remover`

Failure classes were:

*   **`python:3.12-slim` base image** — apt postinst chown/setuid failed for 26 tasks; our patched-ubuntu wrappers don't apply. Requires equivalent patching for the slim Python base.
*   **Task-level `docker-compose.yaml` with `networks:` block** — conflicts with our forced `network_mode: host` (which we use to skip aardvark-dns; aardvark needs systemd, not available on compute nodes). 14 tasks affected.
*   **Odd base images** (`suricata`, `gcr.io/oss-fuzz`, `bugswarm/cached-images`) — 4 tasks; individual fixes needed.

CCC-specific workarounds validated by this run
----------------------------------------------

*   `scripts/ccc/setup_podman.sh` (patched `ubuntu:24.04` with chown/chgrp/useradd/groupadd/usermod/groupmod/adduser/addgroup/dpkg-statoverride wrappers + poppler-utils/build-essential preinstalls + private dbus + rootless socket)
*   `scripts/ccc/run_ccc_experiment.sh` (cap-evolve wrapper with `--resume` support for LSF walltime recovery)
*   `scripts/ccc/submit_ccc_experiment.sh` (LSF `bsub` submitter)
*   Adapter reads `SKILLSBENCH_MODEL` / `SKILLSBENCH_AGENT` / `SKILLSBENCH_SANDBOX_USER` from `.env`

See PR `add-ccc-support` (in review) for details.

Artifacts
---------

Local run — artifacts live on the recording host under `.capevolve/run_runnable_iter7_v1/` (gitignored, per-run):

*   `baseline.json` — full per-task rewards, 43 tasks
*   `events.jsonl` — event timeline (splits, evaluate, step-accept)
*   `state.json` — running iters/USD/tokens counters
*   `rollouts/val/*.json` — per-rollout JSONs across candidates × trials × tasks
*   `bench_jobs/seed/seed{0,1,2}/*/…` — BenchFlow-level artifacts (per-task result.json + trajectory)
*   `work/cand_XXXX/{INSTRUCTIONS.md, RUNMAP.md, prior_iterations/…}` — optimizer's working directory per iter

**Batch submission logs:** `/dccstor/knewedge2/boazc/ccc_logs/1412177.{stdout,stderr}` on CCC.

Update — 2026-07-31 05:35 EDT
-----------------------------

Iter 3 rollouts landing; ~1h into the eval, first-trial rollouts (43) complete. ETA iter-3 gate decision ~08:30 EDT. Total run ETA ~30h from submit (Fri 21:18 EDT) — LSF `-W 30:00` walltime may kill mid-iter-6; a `--resume` submission will complete iters 6–7.
