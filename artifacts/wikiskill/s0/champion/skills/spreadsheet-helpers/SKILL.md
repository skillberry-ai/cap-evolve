---
name: spreadsheet_helpers
description: Deterministic openpyxl helpers for in-place cell editing, range parsing, per-cell verification, collateral-damage diffing, and sample-oracle validation in spreadsheet manipulation tasks.
---

# spreadsheet_helpers

Deterministic helpers for the recurring, easy-to-get-wrong parts of spreadsheet tasks: editing cells
in place, verifying what you wrote, catching collateral damage, and validating logic against
pre-filled example cells.

## When to Apply

- On EVERY task: open the input with `open_inplace`, edit only `answer_position` cells, save,
  then run `verify_range` and `diff_report` before finishing.
- When a task mentions example outputs ('I filled in a couple of examples', 'I've completed the
  first rows'): run `oracle_check` on those cells before filling the rest.

## When NOT to Apply

- Do not use pandas `to_excel` for graded sheets: it rewrites every cell (ints→floats, NaN→blank,
  lost formatting) and the scorer flags 'CHANGED although the expected value is the original input'.
- Do not guess sheet layout from the pandas preview ('Unnamed: N' headers); locate the real header
  row by reading cells with `read_range`.

## Instructions

1. **Always edit in place.** `wb = open_inplace(input_path, output_path)` loads the ORIGINAL
   workbook with openpyxl (formulas, formats, and untouched cells intact) and saves an identical
   copy to output_path. Modify ONLY the cells inside `answer_position` via `write_cells`, then
   `wb.save(output_path)`. Never `df.to_excel` a graded sheet.
2. **Parse the answer ref** with `parse_ref("'Total'!O5:Z12")` to get (sheet, min_row, min_col,
   max_row, max_col). It tolerates the odd quoting in refs like `'Main!'A2:M70`.
3. **Use pre-filled cells as an oracle.** If any cells in the target range already contain
   example outputs, compute your logic and call `oracle_check(wb, sheet, {coord: expected})`
   BEFORE writing the whole range. If it does not reproduce the examples exactly, fix the logic
   first — a whole range filled with wrong semantics fails every cell.
4. **Verify per cell, not in aggregate.** After saving, call
   `verify_range(output_path, sheet, ref, expected_values)`; it prints every mismatching cell
   with coordinates. `read_range(path, sheet, ref)` returns the current values as a 2-D list.
5. **Check collateral damage.** `diff_report(input_path, output_path, answer_ref)` prints every
   cell that differs between input and output — cells changed OUTSIDE the answer range, and
   in-range type coercions (e.g. int 100 → float 100.0, or a value replaced by blank). The report
   must be empty (outside the range you intentionally filled) before you finish.
6. Preserve number types: write Python `int` for whole numbers, not floats, when the original
   cells held ints.

### Script: xlsx_edit.py

Functions (import as `skills.spreadsheet_helpers.xlsx_edit`):

- `parse_ref(ref) -> (sheet_name, min_row, min_col, max_row, max_col)` — handles
  `Sheet1!A1:B2`, `'Total'!O5:Z12`, `'Main!'A2:M70`, `Sheet!B6`.
- `open_inplace(input_path, output_path) -> Workbook` — loads input with openpyxl
  (data_only=False) and saves a copy to output_path; edit and re-save it.
- `read_range(path_or_wb, sheet, ref) -> list[list]` — current values of a range.
- `write_cells(ws, ref, values, start_row=None, start_col=None)` — writes a 2-D (or 1-D)
  list of values into the range starting at its top-left; `None` values are skipped, not
  blanked, so partial fills never erase existing content.
- `verify_range(path, sheet, ref, expected)` — re-opens the file and prints a per-cell
  mismatch report (coordinate, written value, expected value). Returns True if all match.
- `diff_report(input_path, output_path, answer_ref=None, max_print=50)` — prints cells that
  differ between input and output: flagged `OUT-OF-RANGE` when outside answer_ref, and
  `TYPE-CHANGE` when a value changed type (int→float etc.). Returns the list of diffs.

Example:
```python
from skills.spreadsheet_helpers import xlsx_edit as xe
wb = xe.open_inplace('/mnt/data/in.xlsx', '/mnt/data/out.xlsx')
ws = wb['Total']
xe.write_cells(ws, "O5:Z12", values_2d)
wb.save('/mnt/data/out.xlsx')
xe.verify_range('/mnt/data/out.xlsx', 'Total', 'O5:Z12', values_2d)
xe.diff_report('/mnt/data/in.xlsx', '/mnt/data/out.xlsx', "'Total'!O5:Z12")
```

### Script: xlsx_oracle.py

Functions (import as `skills.spreadsheet_helpers.xlsx_oracle`):

- `find_nonempty_cells(path_or_wb, sheet, ref)` — coordinates and values of cells in the
  range that already contain data; use to discover the user's example outputs.
- `oracle_check(path_or_wb, sheet, expected_map, computed_fn=None)` — given
  `{coordinate: expected_value}`, or a mapping plus a function coordinate→computed value,
  reports exactly which example cells your logic fails to reproduce. Returns True if all match.

Example:
```python
from skills.spreadsheet_helpers import xlsx_oracle as xo
examples = xo.find_nonempty_cells('/mnt/data/in.xlsx', 'Sheet1', 'H1:I370')
# build your logic, then:
xo.oracle_check('/mnt/data/in.xlsx', 'Sheet1', {'I8': my_logic('I8')})
```

(Helper script preloaded as `skills.spreadsheet_helpers.xlsx_edit`.)

(Helper script preloaded as `skills.spreadsheet_helpers.xlsx_oracle`.)
