---
name: spreadsheet-helpers
description: Deterministic helper scripts for spreadsheet manipulation tasks. No scripts yet; the optimizer adds them under scripts/.
---

# spreadsheet-helpers

Each script is general, offline and deterministic, takes its inputs as arguments, and writes
only to the path it is given.

## crossfill.py
`from skills.spreadsheet_helpers.crossfill import crossfill`

Use when the task asks to copy/transfer values from one labeled grid (source) into another labeled grid
(target) by matching row labels and column headers — i.e. INDEX/MATCH or VLOOKUP-style cross-table fills.
Call it with the worksheet, the source block's header row / label column / row & column bounds, the target
block's corresponding bounds. It writes a value into EVERY target cell, using 0 for blank or unmatched
source cells (matching INDEX/MATCH behavior), so the whole answer range is covered. First print the
relevant region of the sheet to determine the true header row, label column and data extent.
