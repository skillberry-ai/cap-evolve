# skillsbench-results — SkillsBench intake results (CCC)

Landing page for the four SkillsBench runs conducted on CCC. Structured to
mirror `parsec-results/` from the parent parsec-intake worktree: one folder per
run phase (with per-task or per-iter logs, `summary.md`, raw results) plus a
top-level `analysis/` folder with a cross-phase flat CSV.

Last updated: 2026-08-23.

---

## One-line summary

**Task-by-task optimization (EvoSkills-style, task's own skills as seed) delivers
+36.3 pp average lift across ALL 43 runnable SkillsBench tasks (0.508 → 0.871).
27 of 43 tasks reach val=1.0 (63%). Compared to whole-suite optimization on
the same 43 tasks (+3.1 pp), task-native seed delivers ~12× the aggregate lift.**

- Prior main event (whole-suite runnable-43): PR #270 merged 2026-07-31 — [`local-20260730-skillsbench-runnable-sonnet5-optimize.md`](https://github.com/skillberry-ai/cap-evolve/blob/benchmark-history/docs/runs/local-20260730-skillsbench-runnable-sonnet5-optimize.md)
- New main event (task-by-task-43): c2 worktree, 43 tasks × 10 trials × up to 4 iters, ~$3,000 spent across 2026-08-19 → 2026-08-23.

---

## Phase folders

| Folder | What it is | Best result |
|---|---|---|
| [`baseline-10task/`](baseline-10task/) | First working run — 10-task shared-office subset, Sonnet-4.6. Small sample, used to validate CCC plumbing. | val = 14.29% (1/7 tasks pass) |
| [`all87-broken-wiring/`](all87-broken-wiring/) | 87-task attempt after adapter was expanded. Killed once we spotted new infra-error classes (`network_mode` conflict on 14 tasks, `python:3.12-slim` base failures on 26 tasks). Used to derive the 43-task RUNNABLE subset. | *baseline never completed* |
| [`runnable-43task-opt/`](runnable-43task-opt/) | 43-task RUNNABLE subset, Sonnet-5 agent + Opus-4.8 optimizer, office quartet as seed. Baseline 13.95% → best cand_0002 17.05% (+3.11 pp, gate-accepted); cand_0004 optimizer hung 2h → job killed. | val = 17.05% (+3.11 pp) |
| [`task-by-task-43/`](task-by-task-43/) | **NEW main event.** ALL 43 runnable tasks, one cap-evolve process per task with task's OWN shipped skills as seed, 10 trials × up to 4 iterations, dedicated LSF host per task. Three submission batches. See `summary.md`, `heatmap.html`, and `per-task-logs/` (43 files). | **avg val = 87.1% (+36.3 pp)** |
| [`analysis/`](analysis/) | Cross-phase flat CSV (`per_task_scores.csv`) — one row per (task × phase × candidate) with mean_reward, trial_rewards, notes. 400 rows. Plus `optimization_analysis.html`. | — |
| [`INVESTIGATION.md`](INVESTIGATION.md) | Insights + open investigations: v7 podman fix, Track A, optimizer-hurts-baseline pattern, next-steps for cap-evolve improvements. | — |

Each phase folder contains:

- `summary.md` — human-readable summary (headline table, per-iter breakdown, cost + wall clock, next moves).
- `run.log` — event-stream digest from `events.jsonl` (baseline + iterN + step accept/reject).
- `iter{N}.log` — one file per iteration (JSON), gate decision + optimizer cost/tokens.
- `baseline_all.json` — cap-evolve's `baseline.json` (per-trial rewards for the seed skill).

---

## Numbers at a glance

### task-by-task-43 (the new headline)

| batch | n | avg baseline | avg best | Δ |
|---|---|---|---|---|
| batch 1 (moderate signal in whole-suite; iters up to 4 for 3 partial-lifts) | 10 | 0.690 | 0.940 | +0.250 |
| batch 2 (all-zero in whole-suite; post-v7 podman fix) | 10 | 0.465 | 0.675 | +0.210 |
| batch 3 (23 remaining runnable; max_iterations=4 from start) | 23 | 0.448 | 0.926 | **+0.478** |
| **FULL RUNNABLE-43** | **43** | **0.508** | **0.871** | **+0.363 (+36.3 pp)** |

**vs whole-suite runnable-43 (same 43 tasks, office quartet as seed):** baseline 0.140 → best 0.170 (+3.1 pp). Task-native seed delivers **~12× the aggregate lift**.

- **27 of 43 tasks reach val=1.0** (63%). 7 saturated at baseline. 20 lifted by optimizer.
- **14 partial lifts** in the 0.05–0.99 range (mostly 0.4-0.9).
- **2 stuck at 0.000**: `python-scala-translation` (Scala/GraalVM runtime crash — different infra failure not covered by v7 fix), `spring-boot-jakarta-migration` (JVM tooling infra).

See [`task-by-task-43/heatmap.html`](task-by-task-43/heatmap.html) for the interactive per-task × per-candidate heatmap. Full breakdown in [`task-by-task-43/summary.md`](task-by-task-43/summary.md).

### runnable-43task-opt (prior main event)

| step | candidate | val reward | Δ vs parent | accepted? |
|---|---|---|---|---|
| 0 | `seed` | 0.1395 (13.95%) | — | — |
| 1 | `cand_0001` | 0.1473 (14.73%) | +0.78 pp | ✓ |
| **2** | **`cand_0002`** | **0.1705 (17.05%)** | **+2.33 pp** | ✓ ← best |
| 3 | `cand_0003` | 0.1551 (15.51%) | −1.55 pp | ✗ (paired-SE gate) |
| 4 | `cand_0004` | *not scored — optimizer hung* | — | — |

Cumulative spend at kill time: **$48.78 optimizer** (Opus 4.8) + ~14.6h of Sonnet-5 rollouts.

---

## Where the source files live (in this worktree)

Cap-evolve run directories (kept preserved, do not delete):

| Phase folder here | Corresponds to |
|---|---|
| `baseline-10task/` | `.capevolve/run_baseline/` |
| `all87-broken-wiring/` | `.capevolve/run_all87_iter7_v2_KILLED_11pct_errors/` |
| `runnable-43task-opt/` | `.capevolve/run_runnable_iter7_v1_KILLED_iter4_optimizer_hung_2h/` |

Config + adapters used across phases:

- [`.capevolve/project/capevolve.yaml`](../.capevolve/project/capevolve.yaml) — 10-task shared-office spec
- [`.capevolve/project/capevolve.runnable.yaml`](../.capevolve/project/capevolve.runnable.yaml) — 43-task RUNNABLE subset spec (main event)
- [`.capevolve/project/capevolve.all87.yaml`](../.capevolve/project/capevolve.all87.yaml) — full 87-task spec (blocked)
- [`.capevolve/project/split_ids.runnable.json`](../.capevolve/project/split_ids.runnable.json) — the 43-task subset list
- [`.capevolve/project/adapters/adapter.py`](../.capevolve/project/adapters/adapter.py) — env-driven MODEL/AGENT
- [`.env`](../.env) — ETE creds + `SKILLSBENCH_MODEL=claude-sonnet-5` + `SKILLSBENCH_SANDBOX_USER=` (root)

Documentation for re-picking-up context:

- [`HANDOFF_CCC.md`](../HANDOFF_CCC.md) — long-form; every workaround and its why.
- [`CCC_PODMAN_SETUP.md`](../CCC_PODMAN_SETUP.md) — colleague-facing recipe for rootless podman on CCC.
- [`SKILLSBENCH_INVENTORY.md`](../SKILLSBENCH_INVENTORY.md) — 87-task landscape by category, difficulty, task-type, shipped skills.

---

## To resume the runnable-sonnet5 run (pick up from iter 4 attempting from cand_0002)

```bash
cd /dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-worktrees/intake_skillbench_c1
mv .capevolve/run_runnable_iter7_v1_KILLED_iter4_optimizer_hung_2h \
   .capevolve/run_runnable_iter7_v1
bsub -q normal -M 100G -n 1 -W 30:00 \
  -J capevolve_runnable_iter7_resume \
  -oo /dccstor/knewedge2/boazc/ccc_logs/%J.stdout \
  -eo /dccstor/knewedge2/boazc/ccc_logs/%J.stderr \
  bash scripts/ccc/run_ccc_experiment.sh \
    --suite-id runnable_iter7_v1 \
    --run-ts runnable_iter7_v1 \
    --resume \
    --max-iterations 7 \
    --spec .capevolve/project/capevolve.runnable.yaml
```

---

## Where we are now (2026-08-21)

The task-by-task strategy hypothesized in the previous README revision has been
**run and validated** on 20 tasks — see [`task-by-task-20/`](task-by-task-20/).

Key findings:

- **Task-by-task with task-native seed delivers ~3× the aggregate lift** of whole-suite
  with the office quartet on the same 10 batch-1 tasks (+23 pp vs +7.3 pp).
- **On batch-2 tasks that scored 0.000 in whole-suite**, task-by-task lifts 2 of 10
  to val=1.0 (grid-dispatch-operator, pddl-airport-planning) — proving the strategy
  scales beyond in-domain tasks. But 8 of 10 remain stuck at 0.000 through both iters:
  those are genuinely hard for the sonnet-5 agent regardless of skill mounting.
- **9 of 20 total tasks reach val=1.0** (6 lifted, 3 saturated at baseline).

Open questions:

- Do the 8 stuck-at-0 tasks yield to more iterations (3+) or a larger optimizer budget?
- Do the 3 partial-lift tasks (0.7→0.9 range) reach 1.0 with iter 3?
- Would per-trial seed variance (`num_trials=20`) tighten the paired-SE gate enough
  to accept marginal improvements that iter 2's gate currently rejects?

---

## Open PRs (from `bcarmeli/cap-evolve` fork)

| PR | Purpose | Status |
|---|---|---|
| [`add-ccc-support`](https://github.com/bcarmeli/cap-evolve/tree/add-ccc-support) | CCC docs + scripts → main | awaiting merge |
| [`docs/remove-docs-runs-migrated-to-bench-history`](https://github.com/bcarmeli/cap-evolve/tree/docs/remove-docs-runs-migrated-to-bench-history) | delete `docs/runs/` from main (now that they're on `benchmark-history`) | awaiting merge |
| [`bench-history/regen-benchmarks-json`](https://github.com/bcarmeli/cap-evolve/tree/bench-history/regen-benchmarks-json) | superseded by #270 which merged the same content | **close without merging** |
| [`bench-history/fix-runnable-sonnet5-md-tables`](https://github.com/skillberry-ai/cap-evolve/pull/270) | **merged as PR #270** | ✓ merged |
| [`bench-history/migrate-docs-runs-from-main`](https://github.com/skillberry-ai/cap-evolve/pull/259) | merged | ✓ merged |
| [`bench-history/add-runnable-sonnet5-run`](https://github.com/skillberry-ai/cap-evolve/pull/258) | merged | ✓ merged |

---

## Rebuilding memory in 30 seconds

The three files to open in order:

1. **[HANDOFF_CCC.md](../HANDOFF_CCC.md)** — long-form; every workaround and its why.
2. **This file** — quick pointers + phase-folder index.
3. **[SKILLSBENCH_INVENTORY.md](../SKILLSBENCH_INVENTORY.md)** — for the task-by-task discussion.

If your fresh Claude session is picking up cold, tell it to read HANDOFF_CCC.md first.
