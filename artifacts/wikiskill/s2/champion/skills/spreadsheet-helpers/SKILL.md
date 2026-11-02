---
name: spreadsheet_helpers
description: Deterministic helpers for exact-coordinate Excel reading/writing, typed values, and output verification.
---

# spreadsheet-helpers

Helpers for spreadsheet tasks. Import as `skills.spreadsheet_helpers.iolib`.

## When to Apply
Every spreadsheet task: inspecting the source, writing the answer range, and verifying the saved output. Especially when the answer must land at exact cells (e.g. `F2:H10`, `'Main!'A2:M70`) while everything outside the range must stay untouched.

## When NOT to Apply
There is no spreadsheet file or output path. The scripts hold no task logic beyond generic cell I/O — judgment about *what* values to compute stays with you.

## Instructions

1. **Reply format**: exactly ONE ```python fenced code block per round. Never emit pseudo tool-call XML or prose around the code — an unmatched format wastes the round and can end the episode with no output file.

2. **Never rebuild the workbook with pandas `to_excel`** on the source dataframe. It rewrites headers, shifts every row by one, drops other sheets' formatting, and converts untouched cells — the scorer then flags 'written past where the answer ends' and 'changed although the expected value is the cell's own original input'. Instead:
   ```python
   from skills.spreadsheet_helpers import iolib
   wb, wbv = iolib.open_output(spreadsheet_path, output_path)  # wbv: cached values view
   ws = wb['Main']
   iolib.write_block(ws, 'F2', values)                          # exact anchor, 2D list
   wb.save(output_path)
   ```
   `open_output(src, dst)` loads the input workbook with openpyxl (formulas and formatting preserved) plus a `data_only=True` copy `wbv` for reading cached computed values.

3. **Inspect before solving**: do not assume layout from the 5-row preview. Print the real grid, with types, over the full extent:
   ```python
   iolib.show_region(wbv, 'Hárok1', 'A1', 19, 19)   # nrows, ncols as ints
   grid = iolib.read_region(wbv, 'Total (2)', 'J35', 20, 6)
   ```

4. **Typed values**: the scorer compares typed values. Where a number is expected write a real int/float (use `iolib.as_number(x)` to coerce); where a cell must *display* a hyphen or blank-zero, write the number (or leave empty) and set a number format (e.g. `ws['G4'].number_format = '#,##0.00;-#,##0.00;"-"'`). Never write the string `'-'` into a numeric answer cell.

5. **Cover the whole answer range**: TARGET SIZE tells how many cells must hold values. After writing, verify by re-opening the saved file — never finish on an unverified write:
   ```python
   iolib.verify_output(output_path, 'COLLECTION', 'A2', 8, 7)
   iolib.diff_region(spreadsheet_path, output_path, 'Main', 'A2', 69, 13)
   ```
   `verify_output` prints the saved region with per-cell types and a non-empty count to compare against TARGET SIZE. `diff_region` prints every cell in the region that changed relative to the original input plus cells you left empty — if a changed cell was not part of the instruction, you altered data you should have left untouched; if the non-empty count is below expected coverage, your extent assumption was wrong.

6. `write_block(ws, 'G2', values)` writes a 2D list (or 1D single row) row-major from the anchor; `None` entries leave the existing cell untouched. Coerce intended numbers with `as_number` first — never write pandas NaN or text where a number is intended.

(Helper script preloaded as `skills.spreadsheet_helpers.iolib`.)
