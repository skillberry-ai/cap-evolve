# A harder val for the gate — SpreadsheetBench, Gemma-4-31B-It reader, Claude Opus 5.5 optimizer

Issue #622, a follow-up to #606 ([../2026-10-01-reader-profile-gemma-opus55/](../2026-10-01-reader-profile-gemma-opus55/)).
Run 2026-10-01 to 2026-10-02 on skillberry-1, from the temp branch `exp/val-hard-gate` (draft PR #623, not merged).

## Question

In #606, later optimization rounds were often rejected after round 1 had already scored about 0.95 on the
40-task val. Was the saturated val the limit? We replaced it with a harder 40-task val, built by a rule fixed
before any run, and ran R×3 and B×3 twice each. Train (80) and the fixed 100-task test are unchanged, so the
test scores compare directly with #606.

## Answer

**No. The harder val did not get more later rounds accepted, and it did not improve the test.** With room on
val, the gate still rejected about a third of the later rounds, now because they gave no real gain.

| comparison (fixed 100-task test, paired bootstrap, 2,000 resamples) | Δ test points | 95% CI |
|---|---|---|
| this experiment (4 runs, 3 iterations) vs #606 1-iteration (6 runs) | **+5.0** | **[+1.3, +8.8]** |
| this experiment vs #606 3-iterations on the old val (4 runs) | −1.6 | [−5.7, +2.3] |
| R×3 vs B×3 in this experiment (2 vs 2) | −0.5 | [−5.1, +4.0] |

Rounds accepted: **8 of 12** here, against 9 of 12 on the old val. The pre-registered gate rule needed 3 of 4
runs to accept all 3 rounds; only 1 of 4 did.

## Runs

| dir | variant | test | val_hard path (40) | rounds accepted | optimizer $ | skill chars |
|---|---|---|---|---|---|---|
| `runs/R3-1_36887388530` | R | 73.7 (99 scored) | 40 → 52.5 → 72.5 → 79.5 | 3 | 27.78 | 38,946 |
| `runs/R3-2_36887401974` | R | 74.0 | 40 → 70.0 → (67.5) → 80.0 | 2 | 27.83 | 34,574 |
| `runs/B3-1_36887395788` | B | 74.0 | 40 → 67.5 → 70.0 → (70.0) | 2 | 36.55 | 30,259 |
| `runs/B3-2_36887407126` | B | 75.0 | 40 → 60.0 → (55.0) → (60.0) | 1 | 22.74 | 15,836 |

Values in parentheses belong to rejected rounds. The seed scores 0.40 on val_hard and 43.0 on the test.
Plumbing run 36887383917 confirmed the seed reuse (val 0.40, test 0.43). Each run directory has the same files
as in #606's record.

## The val (pre-registered)

[setup/make_val_hard.py](setup/make_val_hard.py), with details in [setup/val_hard_source.json](setup/val_hard_source.json).

- **Pool:** `full_verified` test tasks outside the 100-task test, scored by the empty seed and by all three
  #538 champions. That gives 176 tasks.
- **Selection:**
  - all 31 "mixed" tasks, which 1 or 2 of the 3 champions pass;
  - the 2 tasks the seed passes and every champion fails;
  - 5 tasks that every model fails;
  - 2 easy anchors.

  The random choices use seed 607. The result is 40 tasks, 25 Cell-Level and 15 Sheet-Level.
- **Seed val results:** taken from the seed's stored, re-scored test rows in the frozen #538 slot. It is the
  same empty seed, model and settings, measured once (`rescore_run.py --target-split`).
- **Method:** the selection used only the #538 runs, never #606's outcomes, and no val task is in the test.

## Findings

1. **The cause of the rejections changed, the count did not.** Round 1 now reaches only 0.53–0.70 on val, but
   rounds 2–3 were still rejected 4 times out of 8 (by −2.5 to −5 points, or +0). The limit is the
   optimizer's later proposals, not the val ceiling.
2. **3 rounds help by about +5–6 points, whichever val selects them.** Old val: +6.2 [+2.6, +10.1]. Hard val:
   +5.0 [+1.3, +8.8].
3. **The hard val gives more consistent results.** The 4 runs span 73.7–75.0 (1.3 points), against 72.2–81.0
   (8.8 points) on the old val.
4. **The hard val pushes skills to be longer, without benefit.** The champions average 29.9 k chars, against
   14.8 k on the old val, for the same test score.
5. **The reader block still makes no difference** (−0.5 points).
6. **Cost:** $115 of Opus 5.5 for the 4 runs. Several rounds hit the 80-turn optimizer limit; their edits
   were kept.

## Limits

One benchmark, one reader model, and 2 runs per variant. The val rule was fixed in advance, but it is one
choice among many possible hard sets.
