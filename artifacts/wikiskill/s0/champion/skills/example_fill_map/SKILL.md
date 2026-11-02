---
name: example_fill_map
description: Uses pre-filled example cells as an evaluated-value oracle AND the exact fill map, and guarantees the final turn saves the output workbook.
---

# example_fill_map

Deterministic helpers for the most common fatal failure on tasks with pre-filled example cells:
blanking or ignoring the examples, filling the wrong cells, and finishing without saving.

## When to Apply

- On EVERY task, FIRST: run `example_cells(input_path, sheet, ref)` to list the user's
  pre-filled example cells and their CACHED EVALUATED values (formula examples resolve to
  numbers via a data_only load).
- Whenever the answer range (or a parallel 'Expected Result' column) holds example cells:
  validate your logic with `validate_examples` BEFORE writing, then fill exactly the marked
  cells with `write_coords`.
- On EVERY task, make your LAST code block a `save_and_confirm(wb, output_path, sheet, ref)`
  call — never finish on a read-only verification or prose turn.

## When NOT to Apply

- Do not use these helpers to decide WHAT values to compute — they only validate your logic
  against examples, pin down WHERE you write, and guarantee the save.
- If the instruction explicitly says to insert a formula into every cell of a range
  (e.g. 'insert this formula into cells B2:B150'), fill the range — but the example cells must
  still evaluate to their original values; verify that with `validate_examples`.
- Do not treat a missing example cell as a cell to leave blank when the instruction's fill
  pattern extends beyond the examples; extend the pattern, then confirm the examples still hold.

## Instructions

1. **Examples are both the oracle AND the fill map.** Before filling any range, call
   `example_cells(input_path, sheet, ref)` — it returns each pre-filled cell with its
   CACHED EVALUATED value (a formula like `=AVERAGE(B24:B69)` yields a number, not text).
   Then compute YOUR logic for those same coordinates and require
   `validate_examples(computed_map, examples)` to pass before writing anything. A logic that
   returns None or a different number on an example cell is wrong — fix it; never fill the
   range and hope.
2. **Write values on exactly the cells the examples mark.** If examples sit on only some rows
   (one value per group, per last occurrence, per qualifying row), your output must hold values
   on exactly those rows and leave the rest empty. Use `write_coords(ws, {coord: value, ...})`
   with a dict built from the example coordinates — never blanket-fill a whole column with
   IFERROR(...,"") formulas (that BLANKS pre-filled example cells and fails as 'N cells empty
   where a value is expected'), and never pad blanks with 0 or "".
3. **A mostly-blank result means wrong keys, not sparse data.** If a lookup/transfer fills only
   a few of many expected cells, your row/column keys are off (pandas preview columns are
   shifted vs real Excel columns). Validate against the example cells: if your computed value
   is None where an example holds a number, the key mapping is wrong — read the real cells
   around the range and fix the mapping before rewriting.
4. **End every episode with a save.** Make your LAST code block call
   `save_and_confirm(wb, output_path, sheet, ref)`: it saves, asserts the file exists, re-opens
   it, and prints the non-empty count and first values of the answer range. Never finish on a
   read-only verification turn or a prose reply — the scorer otherwise reports 'NO output file
   — the code never wrote output_path'.
5. Combine with the edit helpers: `open_inplace` for in-place edits (never `df.to_excel` on a
   graded sheet), `verify_range` after saving, and `diff_report` for collateral damage. The
   examples' fill-count pattern makes fill-count mistakes visible before you ever save.

### Script: xlsx_examples.py

Functions (import as `skills.example_fill_map.xlsx_examples`):

- `example_cells(path, sheet, ref) -> dict` — `{coord: {'formula': str_or_None, 'value': cached_value}}`
  for every pre-filled cell in the range. The value comes from a `data_only=True` load, so
  formula examples are already evaluated. Prints each example. Run this FIRST on the input.
- `validate_examples(computed_map, examples, tol=1e-9) -> bool` — compares your computed
  `{coord: value}` against the examples (numbers with tolerance, strings exactly). Prints each
  failing coordinate. Must be True before you fill the range.
- `write_coords(ws, mapping) -> int` — writes a `{coord: value}` dict directly (e.g. the same
  coordinates the examples marked). Use this instead of filling the whole range when the
  examples mark a sparse pattern.
- `save_and_confirm(wb, output_path, sheet, ref) -> bool` — saves the workbook, asserts the
  file exists on disk, re-opens it, and prints the non-empty count plus the first row of the
  answer range. Call it in your FINAL code block.

Example:
```python
from skills.example_fill_map import xlsx_examples as xm
from skills.spreadsheet_helpers import xlsx_edit as xe
ex = xm.example_cells('/mnt/data/in.xlsx', 'Sheet1', 'H5:H26')      # the user's examples
computed = {'H6': my_count(6), 'H8': my_count(8)}                   # your logic, same coords
xm.validate_examples(computed, ex)                                  # must pass
wb = xe.open_inplace('/mnt/data/in.xlsx', '/mnt/data/out.xlsx')
xm.write_coords(wb['Sheet1'], computed)                             # fill exactly these cells
xm.save_and_confirm(wb, '/mnt/data/out.xlsx', 'Sheet1', 'H5:H26')   # final turn
```

(Helper script preloaded as `skills.example_fill_map.xlsx_examples`.)
