# The SpreadsheetBench 280-task "sealed test" is development-exposed

## Problem
The 280 SkillOpt test tasks are described as sealed/held-out. They have been scored in 16 completed runs, their per-task outcomes were published and used for design decisions, 100 of them are the test set of the #606/#622 experiments, and 40 of them were used as the validation set of four optimization runs.

## Evidence
- Run list: `benchmark-history/runs/*full_verified*` (16 completed SkillOpt-split runs with test scoring; 3 seed-42 runs).
- `docs/experiments/2026-10-01-reader-profile-gemma-opus55/setup/split_ids.json`: 100 test ids, all in the 280 (probe subset stratified by the seed's pass/fail).
- `docs/experiments/2026-10-02-val-hard-gemma-opus55/setup/val_hard_source.json`: 40 val ids, 40/40 in the 280 test, chosen using the test outcomes of the three #538 champions; 4 runs optimized against them.
- Issue #538: formula-only fraction of the test set (15% / 40%) used to explain the result.
- Ledger: `exposure_ledger.csv` rows 3-6.

## Impact
Per-run sealing holds; per-task sealing does not. Headlines on these 280 are post-hoc and no further clean claim can be made on them. Selection optimism is visible (val 95-100 vs test 75-78).

## Correction
Label the 280 as "development-exposed test" in docs; designate a new untouched holdout before any further SpreadsheetBench headline; keep the 280 numbers as historical.

## Acceptance
`docs/RESULTS.md` marks exposure; the paper's claims on SpreadsheetBench carry the label; a new holdout manifest is committed with a digest before the next run.
