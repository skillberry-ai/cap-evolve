# icinga-014-check-script-path-moved

<!-- BEGIN:auto -->

**task:** `icinga-014-check-script-path-moved`  
**category:** icinga  
**tranche:** regression  
**services:** icinga, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_icinga-014-check-script-path-moved/run_20260919_225727` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 1.000 |
| our baseline (v4_t1_e1) | test | 3 | 0.883 |
| seed (val, v4_t2_e1) | val | 5 | 0.860 |
| cand_0001 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.000 · delta vs our baseline: 0.117

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_icinga-014-check-script-path-moved/run_20260919_225727/report.md`, `.capevolve/v4_t2_e1_icinga-014-check-script-path-moved/run_20260919_225727/JOURNAL.md`

<!-- END:auto -->

## What the optimizer tried

A single candidate (`cand_0001`), 11 edits confined to `icinga_agent.md` (248 → 371 lines). It first had to work around the shipped `trajectories/*.json` being empty (`trace: null`) by following `rollout.metadata.trial_dir` into the real run directory to read `verifier/reward-detail.json` directly, which showed the agent locates the moved script correctly in every trial and fails only on how it names the fault. It rewrote the Reference Repositories guidance (a plugin path on the Icinga host is a checkout directory, not a repository name; compare only the repo-relative tail), replaced the stale Step 0.5 diagnosis logic with a "stale check configuration" rule providing a copyable verdict sentence, and added matching vocabulary to three separate output surfaces (`Summary`, `Script Source`, and a new `### What Is Wrong` section).

## Why the winning candidate won

JOURNAL.md identifies the exact failure mode: 4 of 5 seed trials described the moved script using vocabulary `expected.json` deliberately excludes ("wrong repository", "never deployed", "path does not exist", "misconfigured"), even though the underlying investigation (finding the script at its new path) was correct in all 5 trials. Because the optimizer had measured that agents express their conclusion on three different output surfaces (free-form prose 5/5, the `Summary:` line 1/5, `Configured Thresholds` 0/5), it carried the accepted "moved"/"stale configuration" vocabulary onto all three rather than just one, so a compliant answer scores 1.0 under the task's own verifier regardless of which surface the model chose. This took val 0.860 (seed) to 1.000 (Δ +0.140). The held-out test split shows a smaller but real gain: report.md records baseline seed skills at 0.965 vs. optimized skills at 1.0 (Δ +0.035) — a different figure from the val delta because, unlike most other tasks in this batch, this task's val-seed score (0.860) and test-seed score (0.965) are not equal.

## Caveats

n=5 val trials; single-task tuning, never checked against other tasks (see `results/v4/summary.md`'s "Coverage" section).
