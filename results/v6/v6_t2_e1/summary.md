# parsec v6 — T-opt arm (`v6_t2_e1`): task-by-task optimization on the train split

Task-by-task (T2) optimization on the v6 feedback split (F, 67 tasks): one cap-evolve hill-climb
per task, each on a private copy of the 8-file bundle. Run 2026-10-20/21. Design and settings:
`examples/parsec/v6_t2/PLAN.md` on `main` (PR #904).

**These are fit numbers.** Each task's champion is scored on the task it was optimized for, and
there are 34 separate bundles, not one. The merged, held-out result is the T-mrg arm, [`../v6_t4_e1/`](../v6_t4_e1/).

## Headline

| | |
|---|--:|
| Feedback tasks | 67 |
| Optimized | 34 (every task with Seed < 0.95 that the router does not misroute) |
| Reached 1.0 | **34 / 34** |
| Unfixable with skills (fast-path routing) | 8 |
| Not run, Seed ≥ 0.95 | 25 (19 at 1.0 on all trials, 6 in 0.965–0.988) |
| Feedback mean, Seed → per-task best | 0.830 → 0.937 |
| Optimizer spend | $281.12 (median $6.91 per task, range $1.92–24.36) |
| Evaluation spend | $38.25 (Seed trials reused from v6_g2_e1, so only candidate evaluations) |

Iterations with a real optimizer edit, per task: 1 for 18 tasks, 2 for 9, 3 for 5, 4 for 2. Over all
tasks, 53 candidates were accepted and 6 rejected.

## Files

| Path | What |
|---|---|
| [`results.json`](results.json) | one row per train (feedback) task: class, Seed, T-opt champion, every step |
| [`../../../ui/heatmap_v6_t2_e1.html`](../../../ui/heatmap_v6_t2_e1.html) | the same, as a sortable heatmap |
| [`../../../artifacts/v6/v6_t2_e1/best/<task>/`](../../../artifacts/v6/v6_t2_e1/best/) | each of the 34 champions' 8 skill files (`CANDIDATE` names the candidate id) |
| [`source/process/<task>/`](source/process/) | per task: every candidate's `PROCESS.md` (the optimizer's rationale), `events.jsonl`, `state.json` |
| [`source/watchdog/`](source/watchdog/) | the unattended watchdog's log, scoreboard, and (empty) resubmit list |
| [`../../../recipes/v6/v6_t2_e1/`](../../../recipes/v6/v6_t2_e1/) | one task's `capevolve.yaml` (all 34 differ only in task id) and the single-task optimizer brief |

Code (scaffold, runner, watchdog, report builder) is `examples/parsec/v6_t2/` on `main` (PR #904).
The raw run directories stay in the `parsec-intake_v6-t2` worktree under `.capevolve/v6_t2_e1_<task>/`.
The Seed is `artifacts/v6/v6_g2_e1/seed/` (byte-identical; T-opt reused the G run's 10-trial Seed sweep).

## Incidents, and what they changed

1. **Driver collisions in Phase-1 setup.** Seven batch-2 drivers that LSF put on one node killed
   each other's podman setup within a second of starting. Resubmitted 20 s apart. No data lost.
2. **Node failure.** `cccxc504` went down holding 13 drivers and 1 worker; then a kill at 13:50
   (attributed to user `boazc` from `ccc-login5`, most likely the login5 incident cleanup) ended
   10 more drivers. All were resumed from disk; no completed step was lost.
3. **Simulator port collision.** Two lane workers started by different drivers at the same second
   were pinned to the same node (`cccxc505`); their simulators collided (infra errors, retried,
   never scored). Killed by hand, then guarded by a watchdog. The cause is the shared lane
   queue; future T runs use one LSF job per task instead.
4. **CLI crash from a full disk.** `/dccstor/knewedge` reached 100%. Claude Code's auto-updater
   then wrote a truncated `claude` binary, which core-dumped on compute nodes. cost-402's three
   resumed iterations made no edit (`x` in the heatmap). Retried with an intact 2.1.304 binary
   (`V6_T2_CLAUDE_BIN`) and solved on the first real attempt. Fixed for good once space was
   freed and 2.1.304 reinstalled.

None of these changed a recorded score: infra-errored trials are retried and never scored as 0.
