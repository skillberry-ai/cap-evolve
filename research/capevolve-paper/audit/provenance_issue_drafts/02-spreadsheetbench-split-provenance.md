# SpreadsheetBench split provenance is misstated (seed-42 reconstruction vs SkillOpt's released split)

## Problem
Draft ledger and the run-36175707483 README say the test set is "committed `split_ids.json`, 80/40/280, seed 42". The six headline champion runs were on SkillOpt's released partition; only the two era-A runs used the seed-42 draw. The draft's Table 6 caption ("size-matched reconstruction with different member tasks") is stale for the headline runs.

## Evidence
- Per-run `splits.json` in each artifact vs the two committed manifests: 36175707483 and 36306060353 match `split_ids.capevolve_seed42.json` (280/280); 36466624841, 36523096755, 36622615059, 36711181652, 36841799223 match `split_ids.json` (SkillOpt) 280/280. Only 194/280 test, 4/40 val, 16/80 train ids are shared between the two partitions.
- SkillOpt manifest integrity: sha256 of newline-joined sorted ids matches `split_source.json` for train/val/test.
- Commit 31fe1ff4d (PR #556, 2026-09-28) changed the default.

## Impact
Reader cannot tell which tasks any number refers to; the era-A "76.4" and era-B "76.5" look like replications but are different tasks and scorer. The comparison caveat in the paper is wrong in both directions.

## Correction
Record `split_name` (`skillopt` / `capevolve_seed42`) and the manifest sha256 in every results row and in `runmeta.json` going forward. Fix the draft text.

## Acceptance
Every SpreadsheetBench table row carries split name + manifest digest; the seed-42 caveat is removed for era-B rows.
