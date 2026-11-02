---
name: spreadsheet-helpers
description: Deterministic helper scripts for spreadsheet manipulation tasks. No scripts yet; the optimizer adds them under scripts/.
---

# spreadsheet-helpers

No helper scripts exist yet. A script belongs here when a procedure recurs across tasks (parse, locate, normalise,
compute, validate). Each script is general, offline and deterministic, takes its inputs as arguments, and writes
only to the path it is given. List each script below with one line saying when to call it.

Until scripts are added, follow these procedures yourself, in code, on every task:

## Coordinate mapping (the #1 source of failure)

- The `spreadsheet_content` preview is pandas output: its row index 0 is **not** sheet row 1. When the preview
  shows a header like "Row Labels" at pandas index 3, that is sheet row 4. Always confirm header/data rows by
  opening the file with openpyxl and scanning for the header text; never assume the preview's row numbering.
- `answer_position` uses Excel 1-indexed rows and column letters (B11:M11 = rows 11..11, columns 2..13). Convert
  carefully: `openpyxl.utils.column_index_from_string` and `range` bounds are frequent off-by-one sources.
- Write exactly the target range — no values beyond where the answer ends, and every expected value present.
  After saving, re-open the output and print the full target range plus a couple of neighbouring cells; if a
  value landed outside the range or a cell that should hold a value is empty, fix the code and re-save.

## Value types (never write numbers as text)

- If the expected output is a number or date, write the **real typed value** (int/float/datetime), not a string.
  Writing `'0.322580645'` instead of the float fails the scorer even when the digits are right.
- Decimal-formatting instructions (e.g. "nine decimal places", "zero has no decimal places", "one decimal place
  for single-non-zero-decimal values") describe the *value* to store, not a text format: store `0` as int `0`,
  store `0.4` as float `0.4`, store other values as `round(value, 9)` floats. Do not build formatted strings.
- Empty/missing target cells: leave them `None` (do not write `''`, `'N/A'`, or `0`) unless the instruction
  explicitly says to fill them.

## Column-move / restructure procedures

- To move a column: locate it by scanning the header row for the label text (labels can be strings or numbers —
  compare with `str(cell.value) == str(label)` so numeric headers like `16.0` or `0-15` match); snapshot the
  values, header, number formats and styles of the source column; `insert_cols(target)`; copy values AND
  formatting into the new column; then `delete_cols` the original (remember it shifted by the insert). Verify
  the moved data lands inside `answer_position` before finishing.
- For reshape/pivot tasks ("one row per key, values spread across a fixed header list"): pivot on the key,
  reindex to the pre-existing header list in the target sheet, look up each (key, header) pair, and write
  `None` for missing combinations directly into the target range.

## Workflow discipline

- Inspect first, then write, then verify by re-opening `output_path` and printing the target range. Use all
  available rounds: **never finish while the target range disagrees with the instruction's stated expected
  result** (e.g. "Column B should have the values 2 & 1"). If verification shows the wrong count of non-empty
  cells, wrong placement, or wrong types, diagnose against the original file and rewrite.
- Re-run solution code from a freshly loaded original workbook each round; do not re-apply a move to an
  already-modified workbook.
- Create the output directory with `os.makedirs(os.path.dirname(output_path), exist_ok=True)` before saving,
  and save to the exact `output_path` given in the task message.