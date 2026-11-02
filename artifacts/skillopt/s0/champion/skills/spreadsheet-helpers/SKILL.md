---
name: spreadsheet-helpers
description: Deterministic helper scripts for spreadsheet manipulation tasks. No scripts yet; the optimizer adds them under scripts/.
---

# spreadsheet-helpers

A script belongs here when a procedure recurs across tasks (parse, locate, normalise,
compute, validate). Each script is general, offline and deterministic, takes its inputs as arguments, and writes
only to the path it is given. List each script below with one line saying when to call it.

- `range_check.py` — `write_range(ws, first_cell, values)` writes exactly len(values) cells starting at first_cell without touching anything beyond; `read_range(ws, first_cell, last_cell)` reads a range as a list; `coverage_report(ws, first_cell, last_cell)` prints non-empty count plus first/last values to catch off-by-one shifts and over-filling. Import: `from skills.spreadsheet_helpers.range_check import write_range, read_range, coverage_report`. Call `coverage_report` on your saved output before finishing.
- (No other helpers yet. If a documented helper import raises ModuleNotFoundError, do NOT retry the import — immediately fall back to plain openpyxl: `load_workbook` the ORIGINAL file, set only the target cells' `.value` (and `number_format` if formatting is requested), and save to output_path. This preserves other sheets and formatting just as well and is the standard write path.)
