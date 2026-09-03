# Zero-shot skill transfer — 8-fold pilot (`transfer_eval_v1`)

_Generated 2026-09-02 · 8 folds · 5 distinct tasks · dedicated LSF host per fold (CCC) · `cap-evolve run --max-iterations 0` (pure evaluation, no optimizer loop) · Sonnet-5 agent._

**Status: 8 of 8 folds complete.**

## What the experiment asks

Take the **frozen winning skill** that cap-evolve produced for task A, hand it to a *different* task B, and evaluate it zero-shot (`--max-iterations 0`, no adaptation). Does a skill optimized for one task carry over to another?

The comparison of interest is the transferred skill's score on B versus **B's own native seed** — i.e. what B scored before any optimization at all. If the donor skill beats B's native seed, transfer helped; if it scores below, the donor skill is actively worse than starting from scratch on B.

## Results

`transfer reward` = the donor skill's held-out `test_reward` on the test task.
`native seed` / `native optimized` = the test task's own numbers from `results/results.json` (the task-by-task-87 run).

| # | skill from (train task) | evaluate on (test task) | job | status | transfer reward | native seed | native optimized | transfer − native seed |
|---|---|---|---|---|---|---|---|---|
| 1 | shock-analysis-demand | shock-analysis-supply | 555427 | DONE | 0.1 | 0.0 | 0.2 | **+0.1** |
| 2 | shock-analysis-demand | weighted-gdp-calc | 540431 | DONE | 0.2 | 0.8 | 1.0 ‡ | **−0.6** |
| 3 | shock-analysis-supply | shock-analysis-demand | 543167 | DONE | 0.0 | 0.0 | 0.9 | 0.0 |
| 4 | shock-analysis-supply | weighted-gdp-calc | 540433 | DONE | 0.3 | 0.8 | 1.0 ‡ | **−0.5** |
| 5 | weighted-gdp-calc | shock-analysis-demand | 543168 | DONE | 0.0 | 0.0 | 0.9 | 0.0 |
| 6 | weighted-gdp-calc | shock-analysis-supply | 543169 | DONE | 0.1 | 0.0 | 0.2 | **+0.1** |
| 7 | exam-block-sequencing | paratransit-routing | 543170 | DONE | 0.2 | 0.0 | 1.0 ‡ | **+0.2** |
| 8 | paratransit-routing | exam-block-sequencing | 543171 | DONE | 0.4 | 0.1 | 1.0 ‡ | **+0.3** |

‡ In-loop **val** score, not a held-out test score. These four tasks are `KILLED_ceiling` in `results.json` with `final_test: null` — optimization saturated and the run was stopped before a held-out test eval ran. Rows 3 and 5 use held-out `final_test` (0.9); row 1/6's 0.2 is `shock-analysis-supply`'s `final_test` (its val `best` was 0.3).

## Reading of all 8 folds

- **No fold reaches the test task's own optimized score.** The best transfer result (0.4, fold 8) sits far below that task's 1.0. Zero-shot transfer does not substitute for optimizing on the target task.
- **Transfer actively hurts when the target already has a strong seed.** `weighted-gdp-calc` scores 0.8 on its own seed, but donor skills from either shock-analysis task drag it to 0.2–0.3 (folds 2 and 4, −0.6 and −0.5). A skill tuned elsewhere is worse than no skill at all here.
- **Transfer gives a small positive lift only where the native seed was at or near zero** (folds 1, 6, 7, 8: +0.1, +0.1, +0.2, +0.3). This is the weakest possible baseline to beat, so the lift is not strong evidence of genuine skill reuse.
- **The `shock-analysis-demand` ↔ `shock-analysis-supply` pair is asymmetric.** demand→supply (fold 1, supply's native seed is 0.0) gives +0.1; the reverse, supply→demand (fold 3, demand's native seed is also 0.0), gives 0.0 — no signal at all. Same domain, near-identical framing, but transfer only helps in one direction.
- Sample size is 8 folds over 5 tasks in 2 domains. Treat all of the above as directional, not conclusive.

## Methodological caveat — ignore cap-evolve's own `test_delta`

Every fold reports `best_id: "seed"`, `test_reward == test_baseline_reward`, and `test_delta: 0.0`. **This is an artifact of `--max-iterations 0`, not a finding.** With no optimizer iterations, the transfer project's "seed" *is* the frozen donor skill, and it is the only artifact evaluated — so cap-evolve compares it against itself and the delta is trivially zero by construction. Any real transfer effect must be computed against `results.json`'s native-seed column, as done above.

## Per-fold raw results

Machine-readable: [`transfer_eval_8fold.json`](transfer_eval_8fold.json).

Per-fold logs live in the `intake_skillbench_c5` worktree at
`results/transfer_eval_v1/<jobid>/cap-evolve.log`, with cap-evolve run dirs at
`.capevolve/run_transfer_<train>_to_<test>_v{1,2}/`.

## Operational notes (CCC / LSF)

Worth recording because it cost several reruns:

- **Do not pass `-W` to `bsub` for these jobs.** With `--max-iterations 0` the payload finishes in ~45 min but the job process frequently **does not exit** — it hangs in a post-run step indefinitely. With `-W 2:00` set, LSF killed several jobs via `TERM_RUNLIMIT` *after* they had already written a complete result, making a successful run look like a failure. Folds 2, 3 and 4 above show LSF `EXIT` for exactly this reason; their results are valid and complete.
- **Poll the job's own `cap-evolve.log`, not just `bjobs` STAT.** A finished-but-hung job sits in `RUN` forever. The working procedure is: once the log contains a complete result JSON (`"iterations"` key present), kill that **exact** job ID. Folds 5, 7 and 8 were resolved this way; fold 6 is the only one that exited cleanly on its own.
- **One dedicated host per concurrent job (`bsub -m <host>`).** Rootless podman's graphroot is per-user-per-host, so packing two of these onto one host corrupts container state.
- **`-n 1`, not `-n 4`.** These are single-eval runs with no internal parallelism.
- **Fold 1's first attempt (543166) hung in setup**, not in the payload: 15.6 h in `RUN` with stdout frozen at "Phase 2: loading .env", never reaching `cap-evolve run`, no `cap-evolve.log` ever created. Killed and resubmitted on a fresh host as 555427 with `--run-ts ..._v3`, which then hit the same post-run hang as folds 2–5/7/8: log showed a complete result (`test_reward=0.1`) after ~1h20m of payload time, but the job sat in `RUN` for a further ~23h before being killed by exact ID.
- `scripts/ccc/submit_ccc_experiment.sh` hardcodes both `-W` and `-n 4`, so these folds were submitted with direct `bsub` calls instead.

## Provenance

- Runs executed in worktree `cap-evolve-worktrees/intake_skillbench_c5` (branch `intake_skillbench_c5`), suite id `transfer_eval_v1`, 2026-09-01 → 2026-09-02.
- Native seed/optimized figures read from `results/results.json` (87-task aggregate, generated 2026-08-28).
