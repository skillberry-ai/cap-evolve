# v6_g2_e1 — hill-climb over a shared bundle: cost & time, per iteration

Hand-built from `source/events.jsonl`'s own `promotion`/`step` events and `source/state.json`'s
cumulative spend — no cost_time-parsing script exists for this arm yet (only 6 rows). Unlike
v4_g_e1/v5_g2_e1, this run has **three splits**, not one: F (feedback, screened on a random
12-task rung, never scored whole), C (confirm, hidden from the optimizer, scored by a
group-sequential test at increasing sample size), and test (sealed, scored exactly once at the
very end). The table below is per-ITERATION, not per-task — there is no analogue of v4's "all
34 tasks every iteration" row shape, because F and C are each only partially sampled per
iteration by design (see `../summary.md`'s "Why there's no per-task F/C ledger").

## Summary table — one row per iteration

| Iter | Candidate | Parent | F screen Δ | F screen z | F screen n | C decision | C val | Fixed (C) | Broke (C) | Optimizer $ | Optimizer tokens |
|---|---|---|--:|--:|--:|:--:|--:|--:|--:|--:|--:|
| 1 | cand_0001 | seed | +0.0605 | 0.60 | 12 | reject | 0.8708 | 3 | 0 | $82.70 | 20,519,494 |
| 2 | cand_0002 | seed | +0.1681 | 1.53 | 12 | **accept** | 0.9500 | 6 | 0 | $49.40 | 14,731,198 |
| 3 | cand_0003 | cand_0002 | +0.0190 | 0.18 | 12 | reject | 0.8390 | 0 | 0 | $33.62 | 16,348,824 |
| 4 | cand_0004 | cand_0002 | −0.0043 | −0.03 | 11 | killed at F rung 1 | — | 0 | 0 | $22.45 | 21,145,862 |
| 5 | cand_0005 | cand_0002 | +0.0782 | 0.65 | 12 | **accept** | 0.8728 | 0 | 0 | $58.19 | 51,444,932 |
| 6 | cand_0006 | cand_0005 | −0.0321 | −0.33 | 12 | killed at F rung 1 | — | 0 | 0 | $108.66 | 30,800,380 |
| **total optimizer** | | | | | | | | | | **$355.02** | **154,990,690** |

"Fixed (C)"/"Broke (C)" counts are tasks whose move on the confirm split exceeded 2 standard
errors of its own per-task measurement error (the run's own LEDGER convention; see
`../../source/LEDGER.md`) — tasks that moved by less are `unresolved`, not evidence of either
direction, and are not counted here. 0 breaks across all 6 iterations.

## Where the eval cost went

| | eval $ | eval runner-seconds | optimizer $ | optimizer-seconds | total $ |
|---|--:|--:|--:|--:|--:|
| **6 iterations (F screen + C confirm, all candidates)** | $809.37 | 153,426 (42.6h) | $355.02 | 32,181 (8.9h) | $1,164.39 |
| **sealed test (final.json: FINAL + FINAL_seed)** | $138.02 + $94.19 = $232.21 | 13,360 + 14,261 = 27,621 (7.7h) | — | — | included above\* |

\*The test-split eval cost/time above is already counted inside the $809.37/153,426s eval total —
it isn't a separate addition, since `finalize()` runs inside the same `state.json` spend tracker
as every F/C-split eval. Listed separately here because it's the number that answers "what did
scoring the champion on held-out data cost," which the per-iteration table above can't show (test
is scored once, after all 6 iterations, not per-iteration).

**Optimizer dominates less here than in v4_g_e1.** $355.02 of $1,164.39 total (30.5%) is the
optimizer proposing each candidate — well below v4_g_e1's ~75% and v4_t_e1's ~85%, because every
iteration's eval sweep here is far larger per candidate (an F-split screen, a full C-split
re-confirmation of the incumbent, plus the candidate's own group-sequential C-split test at up to
200 cumulative rollouts) than v4_g_e1's flat 170-rollout sweep.

**Optimizer cost per iteration doesn't track outcome.** The single most expensive optimizer call
of the run ($108.66, iteration 6) produced the worst F-split screen result (−0.0321) and was
killed before any confirm-split spend — the cheapest possible failure mode despite being the most
expensive candidate to produce. The two accepted candidates (iterations 2 and 5) cost $49.40 and
$58.19 respectively, both below the run's $59.27 median optimizer cost.

## Data-quality note: the finalize crash

The driver that scored the sealed test split (LSF job 1702040) completed BOTH test-split
evaluations — champion as `FINAL` ($138.02, 13,360s), seed as `FINAL_seed` ($94.19, 14,261s), both
logged in `events.jsonl` with final rewards — then crashed (exit 255, apparent host-level LSF
fault on `cccxc436`) while starting the free train/val bookend report that `finalize()` runs
after test. `final.json` was reconstructed from the already-completed test rollouts (not
re-scored — see `../summary.md`'s caveat for the full account); the train/val bookend never ran
and is not included anywhere in this arm's reports.
