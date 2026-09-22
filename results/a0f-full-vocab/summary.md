# A0f — full 196-skill vocabulary pilot (`a0f_full_vocab_v1`)

_Generated 2026-09-15 · 10 tasks · dedicated LSF host per job (CCC) · `cap-evolve run --max-iterations 0` (pure evaluation, no optimizer loop) · Sonnet-5 agent, 10 trials per task._

**Status: 10 of 87 tasks complete.**

## What the experiment asks

Arm **A0f** deploys the entire 196-skill seed library (`.capevolve/seed_capability_full196`) to every task, instead of that task's own ~2.7 shipped skills, and evaluates it zero-shot at `--max-iterations 0`. `A0f − A0` isolates the **selection / interference cost** of a large vocabulary with specialization held at zero — does simply handing the agent every skill in the library, with no ability to pick or tune, help or hurt relative to its normal curated set? A0f gates arms A2f, A3 and A4 in `docs/specs/experiments_plan_v1.md` (not A2p — see the 2026-09-09 correction).

## Results

`A0` = the task's own `seed` score in `results/results.json` (task-by-task-87 sweep). `A0f` = this pilot's measured score, all 196 seed skills, `max_iterations: 0`.

| Task | job | A0 (own skills) | A0f (196 skills) | Δ |
|---|---|---|---|---|
| hvac-control | 764607 | 1.000 | 0.500 | **−0.500** |
| mario-coin-counting | 765000 | 1.000 | 0.100 | **−0.900** |
| earthquake-plate-calculation | 764939 | 0.900 | 1.000 | **+0.100** |
| jpg-ocr-stat | 764940 | 0.800 | 0.700 | −0.100 |
| adaptive-cruise-control | 764941 | 0.700 | 0.700 | 0.000 |
| react-performance-debugging | 764942 | 0.600 | 0.400 | −0.200 |
| organize-messy-files | 764943 | 0.500 | 0.500 | 0.000 |
| setup-fuzzing-py | 765002 | 0.364 | 0.513 | **+0.149** |
| civ6-adjacency-optimizer | 764944 | 0.310 | 0.325 | +0.015 |
| energy-unit-commitment | 764945 | 0.100 | 0.000 | −0.100 |
| **mean (n=10)** | | **0.627** | **0.474** | **−0.154** |

## Reading the 10 tasks honestly

- **The headline drop is not statistically significant.** Paired bootstrap 95% CI on the mean delta is **[−0.360, +0.008]** (20,000 resamples, seed 0); Wilcoxon signed-rank p = **0.195**. The observed delta sits 1.52 standard errors from zero. Treat this as *directional* evidence of interference, sized around −0.15 (−24.5% relative), not a confirmed effect.
- **The two largest regressions are ceiling artefacts, not evidence of harm.** `hvac-control` (−0.50) and `mario-coin-counting` (−0.90) both had `A0 = 1.000` — the reward ceiling. With A0 already at the maximum, any change to the skill set can only regress or hold steady; these two tasks alone account for more than half of the total delta magnitude across all 10 tasks. Excluding them, the remaining 8 tasks show a much smaller mean delta.
- **The three genuine improvements are all on lower-scoring tasks**: `earthquake-plate-calculation` (+0.10), `setup-fuzzing-py` (+0.15), `civ6-adjacency-optimizer` (+0.02). None of these had a saturated seed, so there was room for either direction — that the full library helped here at all is worth tracking as the task set expands.
- Counts: 3 improved / 2 same / 5 regressed, out of 10.
- Sample size is 10 of 87 tasks. Treat all of the above as directional, not conclusive — this is the reason to publish now as a pilot and expand to the rest of the suite rather than wait.

## Methodological caveats

- **Cross-harness pairing.** The `A0` column above is read from `results/results.json` (the Aug-2026 task-by-task-87 sweep, generated 2026-08-28), a different harness build than the one used for these A0f runs. It was not re-measured under the A0f harness for this pilot, so the pairing crosses harness versions. The experiments plan's own Verification step 5 ("Reproduce A0 (0.508) from the A0f harness with the per-task library, as a wiring check") remains undone.
- **Discarded job.** The first `setup-fuzzing-py` attempt (job 764728) returned a forced `reward: 0.0` because the podman socket (`/tmp/podman-run-561567/podman.sock`) vanished mid-run — an infrastructure failure, not a measurement. It is excluded here and superseded by job 765002 (reward 0.513), which is the number shown above.
- **Cost telemetry gap.** `cost_usd` and `tokens` are `0.0` / `0` in every `baseline.json` for these runs — the same gap already documented in `results/baseline-10task/summary.md`.

## Per-task raw results

Machine-readable: [`a0f_full_vocab.json`](a0f_full_vocab.json), including per-task trial reward vectors, hosts, and the aggregate/caveat fields backing the numbers above.

## Operational notes (CCC / LSF)

- Config verified before publishing: exactly 196 entries in `.capevolve/seed_capability_full196` and in each run's `candidates/seed/`; `train == val == test == [task]` in each run's `splits.json`; `max_iterations: 0`, `num_trials: 10`.
- One dedicated host per concurrent job (`bsub -m <host>`), no `-W` walltime, `-n 1` (single-eval, no internal parallelism) — same operational constraints as `results/transfer-eval-8fold/`.
- Each job's host recovered from its LSF stdout log; recorded per task in `a0f_full_vocab.json`.
