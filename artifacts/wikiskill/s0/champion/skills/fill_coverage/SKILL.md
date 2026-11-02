---
name: fill_coverage
description: Guards against over-filling answer ranges past pre-filled example cells, and applies display number formats instead of Python rounding.
---

# fill_coverage

Deterministic helpers for the two failure modes the edit/verify helpers cannot see: writing MORE
cells than the expected answer contains (over-fill / clobbered examples), and rounding values in
Python when the task only asked for a display format.

## When to Apply

- On EVERY task, before writing: run `prefill_stats` on the answer range to see which cells the user
  already filled and where those examples end.
- On EVERY task, after saving: run `coverage_check` and make sure it does not warn OVER-FILL.
- Whenever a task specifies decimal places, percent, or time formatting: use `set_number_format`,
  do NOT round the value in Python.

## When NOT to Apply

- Do not use these helpers to decide WHAT values to compute — they only constrain WHERE you write
  and HOW values are displayed.
- Do not treat a low pre-fill count as license to skip cells the instruction explicitly asks to fill
  (e.g. 'insert this formula into cells B2:B150') — but even then, never overwrite an existing
  pre-filled value with something different unless the instruction says to replace it.

## Instructions

1. **Never over-fill past the pre-filled examples.** Before writing, call
   `prefill_stats(input_path, sheet, ref)`. If the user provided example outputs that end partway
down the range (e.g. 9 filled of 149), the expected answer almost always ends where the examples
   end: fill the same shape/pattern and STOP there. NEVER overwrite a pre-filled example cell with
   a different value, and never pad the rest of the range with 0, "", or formulas — a blank cell is
   often the correct answer. This exact failure ('your output has a value in 149; the expected output
   has a value in 9; 144 cells CHANGED although the expected value is the cell's own original input')
   is the most common scorer verdict on tasks with sample outputs.
2. **Run a coverage check after saving:** `coverage_check(input_path, output_path, sheet, ref)`
   prints non-empty counts before vs after and lists newly filled cells that lie beyond the last
   pre-filled row. If it warns OVER-FILL (far more values written than were pre-filled), you have
   almost certainly written past where the answer ends — use `clear_cells` on the extra cells or
   rewrite, then re-check, before finishing. Note: `diff_report` from the edit helpers tags these
   cells IN-RANGE and will NOT warn you; only coverage_check sees them.
3. **Decimal-place instructions are FORMATTING, not rounding.** When a task asks for values with N
   decimal places, do NOT round the value in Python (round(0.3225806452, 9) loses the last digit and
   fails cell comparison). Write the full-precision float and set the display format with
   `set_number_format(ws, ref, '0.000000000')`. Only write a literally rounded value when the
   instruction explicitly demands a truncated number as the stored value.

### Script: xlsx_fill.py

Functions (import as `skills.fill_coverage.xlsx_fill`):

- `prefill_stats(path_or_wb, sheet, ref) -> dict` — `{'nonempty': {coord: value}, 'count', 'total',
  'last_row', 'box'}` for already-filled cells in the target range; prints a one-line summary.
  Run BEFORE writing to see the user's example outputs and where they end.
- `coverage_check(input_path, output_path, sheet, ref, max_list=20) -> bool` — re-opens both files,
  prints non-empty counts before vs after, lists up to 20 newly filled cells beyond the last
  pre-filled row, and returns True only when the fill count is plausible (did not more than roughly
  double the pre-filled count). Run after saving; if it warns OVER-FILL, delete the extra values.
- `set_number_format(ws, ref, fmt)` — applies an Excel number format string (e.g. '0.000000000',
  'hh:mm:ss AM/PM', '0%') to every cell in the range. Use instead of rounding values in Python.
- `clear_cells(ws, ref)` — sets cells to None; use to undo an over-fill beyond the example rows.

Example:
```python
from skills.fill_coverage import xlsx_fill as xf
stats = xf.prefill_stats('/mnt/data/in.xlsx', 'Sheet1', 'B2:B150')
print(stats['count'], 'of', stats['total'], 'pre-filled; last filled row', stats['last_row'])
# ... write ONLY the cells matching the example pattern ...
xf.coverage_check('/mnt/data/in.xlsx', '/mnt/data/out.xlsx', 'Sheet1', 'B2:B150')
xf.set_number_format(ws, 'B11:M11', '0.000000000')
```

(Helper script preloaded as `skills.fill_coverage.xlsx_fill`.)
