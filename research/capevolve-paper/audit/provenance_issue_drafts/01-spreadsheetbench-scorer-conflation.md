# SpreadsheetBench headline gains conflate formula-compliance with capability (as-saved vs recalculated scorer)

## Problem
Headline SpreadsheetBench numbers (Gemma 43.5 -> 76.5/76.8, GPT-5.5 38.6 -> 87.6, "+49") are on the as-saved scorer (`hard_no_recalc`: `openpyxl data_only=True`, no LibreOffice recalculation). The draft, ledger and post never put the recalculated numbers next to them, and the draft additionally mixes recalc-scored era-A results (63.2 -> 76.4, 62.9 control) with as-saved era-B results in one narrative.

## Evidence
Recomputed from `metrics.jsonl` (both metrics from the same output workbook; baseline and optimized scored identically; script `sb_recompute.py`):
- Gemma no-skill, run 36387149344: 43.5 as saved vs 58.3 recalculated; 119 pass under both, 42 only with recalculation, 1 only as saved.
- Gemma champions 36466624841/36523096755/36622615059: as saved +31.5/+33.1/+34.4; recalculated 58.3 -> 75.4/77.5/78.6 = +17.1/+19.0/+20.3.
- GPT-5.5 no-skill 36836354465: 38.6 as saved, 77.5 recalculated (110 formula-only passes); champions 88.2/87.5/87.1 as saved, 87.9/87.1/87.1 recalculated: recalculated gain +9.9.
- Era-A runs 36175707483 / 36306060353 have no `reward_metric` and predate #568: reward is the recalculated one although the README says `SB_SCORING=hard`.

## Impact
About 14 of Gemma's 33 points and 39 of GPT-5.5's 49 points are the agent learning to write literal values. Citing +33/+49 as optimizer capability gain overstates it; comparing against WikiSkill/SkillOpt (whose scorer is inferred, not stated, to be as-saved) is only valid with that caveat.

## Correction (additive, history untouched)
Add a results table with columns `scorer` and report both metrics for every SpreadsheetBench row. State the recalculated gain as a co-primary number. Never place era-A and era-B numbers in one comparison.

## Acceptance
- `docs/RESULTS.md` and the paper table list as-saved and recalculated for each SpreadsheetBench row.
- Text names the scorer wherever a SpreadsheetBench number appears.
- `recomputed_numbers.csv` rows SB-G-07, SB-P-04, SB-A-01 are cited.
