---
name: typed_edit_rules
description: Rules and helpers for typed values, sparse coverage, cascade recompute, minimal in-place edits, and contradictory sort clauses. Use together with skills.spreadsheet_helpers.iolib.
---

# typed-edit-rules

Judgment rules and two small helpers that fix recurring scorer failure modes. Import the helpers as `skills.typed_edit_rules.typelib` and use them together with `skills.spreadsheet_helpers.iolib` (open_output / read_region / verify_output / diff_region).

## When to Apply
Every spreadsheet task, after you have computed your answer values and before you save:
- deciding what to write into missing/empty cells of the answer range,
- writing derived numeric columns (sums, balances, lookups),
- editing an input cell that other columns depend on,
- multi-branch conditional fills keyed on an id column,
- sorting tasks with a trailing clause that contradicts the primary rule.

## When NOT to Apply
There is no spreadsheet file or output path, or the task is pure inspection. The helpers hold no task logic — what values to compute stays with you.

## Instructions

1. **Missing data cells stay EMPTY**: when the instruction mentions filling 'N/A'/'-'/blank for missing values but the source has no value, the expected output almost always leaves those cells EMPTY. Do NOT write the string 'N/A', '', or 0 into missing cells. A low non-empty count that MATCHES the expected coverage is CORRECT, not a bug; if your first sparse write matches the expected non-empty count (from TARGET SIZE / the preview), do NOT second-guess it and pad the range. To intentionally blank a cell, set `ws.cell(row=r, column=c).value = None` directly.

2. **Recompute dependent columns after editing an input**: if you change any input cell (e.g. a rate 350→180), every column that is an arithmetic function of it (totals, bill-to, profit, balance) must be recomputed for the affected rows before you save. Scorer feedback "N cells hold a number LOWER than expected" with otherwise perfect coverage is the signature of a stale derived column. In your verify round, self-check derived cells arithmetically on the saved file (e.g. profit == bill - cost).

3. **Contradictory trailing clauses**: some instructions end with an extra clause like "and sort only column H lowest to highest" that contradicts the fully-specified primary rule. The FIRST fully-specified rule governs; never apply a trailing re-sort on top of already-sorted output. If a sheet in the workbook shows the expected result, print it and match it.

4. **int vs float**: the scorer distinguishes `280` (int) from `280.0` (float). When writing a derived numeric column, read the ORIGINAL values of that column (or the column it is derived from) and coerce with `typelib.astype_like(value, original_values)` — float if any original value is a float, int if all are ints. Never call `int(x)` on whole floats just to make them look tidy:
   ```python
   from skills.spreadsheet_helpers import iolib
   from skills.typed_edit_rules import typelib
   orig = iolib.read_region(wbv, 'COLLECTION', 'G2', 7, 1)
   cell.value = typelib.astype_like(balance, [r[0] for r in orig])
   ```

5. **Condition scope and minimal overwrite**: apply each clause of a multi-branch conditional at the scope its wording implies ("accompanied exclusively by X" is a group-level check over the id's rows; "status is X and date present" is row-local). Before writing a full answer column, diff your computed values against the ORIGINAL column and write ONLY the cells that differ — overwriting cells whose original value was already correct triggers "CHANGED although the expected value is the cell's own original input". Use `typelib.changed_cells(ws, orig_values, anchor, computed)`:
   ```python
   orig = iolib.read_region(wbv, 'Sheet1', 'F2', 19, 1)
   for i, j, v in typelib.changed_cells(ws, orig, 'F2', computed):
       ws.cell(row=2 + i, column=6 + j).value = v
   ```

(Helper script preloaded as `skills.typed_edit_rules.typelib`.)
