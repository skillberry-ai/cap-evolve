# Purpose

## Origin
Iteration 1. Failure analysis of training traces showed three recurring *procedural* failure modes:

1. **Full-sheet pandas rewrites** (194-19: 146 cells 'CHANGED although the expected value is the cell's own original input'; 247-24: 12 numeric cells 'LOWER than expected' after a to_excel round-trip; 51090: 5 original-value cells overwritten). Agents load with `pd.read_excel`, mutate a DataFrame, and `df.to_excel` the whole sheet, which coerces ints to floats, blanks NaNs, destroys formatting, and rewrites columns the instruction never asked to touch. This matches wiki pattern `preserve-untouched-cells-openpyxl`, but no helper existed.
2. **No collateral-damage verification.** Agents verify only that their target cells hold the values they wrote; they never diff the saved file against the input to catch cells they broke elsewhere.
3. **Ignoring pre-filled oracle cells** (194-19 'I've completed results for the first meet'; 11842 off by 2/96 cells). Agents never validate candidate logic against example outputs before filling the whole range. Matches wiki pattern `use-sample-rows-as-oracle`.

The seed skill `spreadsheet-helpers` was an empty placeholder with no scripts.

## Patterns Addressed
- preserve-untouched-cells-openpyxl (primary)
- use-sample-rows-as-oracle (oracle_check / read_range)
- verify-write-values-not-assumptions (verify_range per-cell read-back)

## Evolution History
- v1 (iteration 1): initial scripts `xlsx_edit.py` (open_inplace, write_cells, read_range, verify_range, diff_report) and `xlsx_oracle.py` (oracle_check, find_nonempty_cells). Replaces the empty seed skill.
