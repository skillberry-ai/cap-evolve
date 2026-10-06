# Reader-profile experiment — SpreadsheetBench, Gemma-4-31B-It reader, Claude Opus 5.5 optimizer

Issue #606 (full log of runs, decisions and infrastructure changes). Run 2026-09-30 to 2026-10-01 on the
self-hosted runner skillberry-1, from the temp branch `exp/606-reader-profile` (draft PR #608, not merged).

## Question

The optimizer's instructions open with a "THE READER" block that describes the model that will read the skill.
Does that description change the result? We compared the two extremes:

- **R (results-driven):** no model name, no tier: *"You do not know which model reads this skill. Infer its
  strengths and weaknesses from the trajectories and failures you are given, and strengthen the areas where it
  fails."* ([setup/reader/R_results_driven.md](setup/reader/R_results_driven.md))
- **B (frontier):** Gemma described with the built-in `frontier` brief: "soften imperatives, keep few-shot
  examples minimal" ([setup/reader/B_frontier.md](setup/reader/B_frontier.md)).

## Answer

**No measurable difference.** The block changes how the skill is written, but not how well it works. The
number of accepted optimization rounds does matter.

| comparison (fixed 100-task test, paired bootstrap, 2,000 resamples) | Δ test points | 95% CI |
|---|---|---|
| R vs B, 1 iteration (3 vs 3 runs) | +1.0 | [−4.0, +5.3] |
| R vs B, 3 iterations (2 vs 2 runs) | +3.1 | [−2.1, +8.8] |
| 3 iterations vs 1 iteration (4 vs 6 runs) | **+6.2** | **[+2.6, +10.1]** |
| 3 iterations, all rounds accepted (2 runs) vs 1 iteration | **+8.3** | **[+3.8, +13.3]** |

Recompute these with `python3 setup/compare_groups.py <runs A> <runs B>`, after pointing it at the
`runs/*/metrics.jsonl` files.

## Runs

| dir | variant | iters | rounds accepted | test | val path (40 tasks) | optimizer $ | skill chars |
|---|---|---|---|---|---|---|---|
| `runs/R1-1_36749820449` | R | 1 | 1 | 68.0 | 84.6 | 4.60 | 7,856 |
| `runs/R1-2_36786991944` | R | 1 | 1 | 72.0 | 87.5 | 7.58 | 9,578 |
| `runs/R1-3_36798553824` | R | 1 | 1 | 69.0 | 90.0 | 3.64 | 25,747 |
| `runs/B1-1_36749825398` | B | 1 | 1 | 66.0 | 77.5 | 6.06 | 6,043 |
| `runs/B1-2_36786995256` | B | 1 | 1 | 71.0 | 75.0 | 5.56 | 6,618 |
| `runs/B1-3_36798556468` | B | 1 | 1 | 69.0 | 85.0 | 5.01 | 5,432 |
| `runs/R3-1_36798559752` | R | 3 | 3 | 81.0 | 80.0 → 82.5 → 95.0 | 23.02 | 13,998 |
| `runs/R3-2_36815050362` | R | 3 | 1 | 72.2 (97 scored) | 97.4 → (92.5) → (97.5) | 8.33 | 24,409 |
| `runs/B3-1_36798563019` | B | 3 | 3 | 74.0 | 82.5 → 87.5 → 92.5 | 17.87 | 11,298 |
| `runs/B3-2_36815053131` | B | 3 | 2 | 73.0 | 82.5 → 87.5 → (87.5) | 22.14 | 9,395 |
| `runs/diag-B1-skillberry2_36746122576` | B | 1 | 1 | 68.0 | 68.0 (only 25 of 40 scored) | 2.50 | 6,229 |

The last row is **not counted**: it ran on skillberry-2, where 15 of 40 val rollouts hung in the sandbox.

Each run directory holds:
- `metrics.jsonl`: per-task test rewards, seed and champion;
- `events.jsonl`: gate decisions, val scores, optimizer cost;
- `steps.jsonl`, `runmeta.json`, `report.md`;
- `reader_block.md`: the exact block the optimizer got;
- `optimizer_models.json`: model ids from the Claude session logs;
- `exp606_report.json`;
- `champion/`: the champion's `prompt.md`, `task_template.md` and diff from the seed.

## Setup

- **Reader (agent):** `ibm-rits/google/gemma-4-31B-it`, 30 turns, 8 in parallel, temperature 0. Reward
  `hard_no_recalc`: the workbook is graded as saved, hard scoring.
- **Optimizer:** `ibm-ete-int/aws/claude-opus-5-5`, `hill-climb-all`, `gate_k_se=0.2`, 1 trial, up to 80
  optimizer turns.
- **Split:** `full_verified` (SkillOpt's released split) train 80 / val 40. Test is a **fixed 100-task subset**
  of its 280 test tasks: seed 606, stratified by task type and by the seed's own pass/fail, drawn only from the
  276 tasks the seed scored ([setup/subset_source.json](setup/subset_source.json),
  [setup/make_probe_subset.py](setup/make_probe_subset.py)). The seed scores 43.0 on the subset and 43.5 on
  all 280.
- **Seed:** the #538 empty seed (run 36622615059), reused from a frozen copy of the saved slot and restricted
  to the subset. No run re-evaluated or rewrote it.
- **Checks on every run** ([setup/exp606_report.py](setup/exp606_report.py)): the optimizer model is only
  `claude-opus-5-5`, the reader block appears verbatim in the optimizer's rendered `INSTRUCTIONS.md`, and the
  seed is reused.
- **Changes made during the experiment:**
  - Gemma warm-up before preflight.
  - From R1-2 on, the end-of-run *train* pass is skipped (`CAPEVOLVE_SKIP_FINAL_TRAIN=1`). It runs after the
    test and changes no compared number.
  - All counted runs are pinned to skillberry-1.
- The full plan, as written before the runs, is in [setup/plan.md](setup/plan.md).

## Findings

1. **The reader block changes the style, not the score.** At 1 iteration, R skills average 14.4 k chars,
   with bold MUSTs, numbered rules and up to 10 code examples. B skills average 6.0 k chars and explain
   the reasons. All skills state the full grader contract: values as saved, types, no formulas, 2-decimal
   rounding. Skill length (5.4–25.7 k chars) shows no relation to the test score.
2. **A 40-task val misleads.** At 1 iteration, R's val was 8 points above B's (87.4 against 79.2), with no
   test gap. The highest val of the experiment (97.4) gave an ordinary test score (72.2).
3. **Accepted rounds are what matter.** The two runs that accepted all 3 rounds reached 81 and 74, against
   about 69 after 1 round.
4. **The val ceiling blocks later rounds.** *Corrected by the follow-up #622
   ([../2026-10-02-val-hard-gemma-opus55/](../2026-10-02-val-hard-gemma-opus55/)): with a harder val, later
   rounds were still rejected about as often (8 of 12 accepted, against 9 of 12), and the test was unchanged.
   The ceiling was not the real limit; the optimizer's later proposals were.* The original observation follows. When round 1 already scores about 0.95 or more on 40 val tasks,
   the paired gate cannot detect a further gain, and it rejects rounds 2–3. The test still has room to
   improve: the best run reached 81 of 100.
5. **Opus 5.5 cost:** $3.6–8 and 10–32 min per round, against $11–14 and 41–49 min for Opus 5 in #538.
   Total for the 10 counted runs: about $104.

## Limits

- One benchmark, one reader model, and 2–3 runs per cell. Runs of the same variant differ by up to 6 points
  on the 100 tasks.
- The variants between the extremes (A: the current `strong` text; C: no block) were not run. The plan ran
  them only if the extremes differed.
