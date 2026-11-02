# Purpose

## Origin
Training iteration 1. Failing traces (11842, 56786, 58109, 82-30, 6239, 46646, 32337, 46121) show repeated *procedural* failures, not judgment failures:

- 46646 / 408-39: agents located header/data rows by assuming the pandas preview layout instead of scanning real cells, and read data from the wrong row.
- 32337 (6 empty cells) and 56786 (C200 empty): the answer range was left partially unfilled; a coverage check against the exact answer_position would have caught it.
- 6239: the agent saved with `df.to_excel(...)`, rebuilding the sheet and destroying formatting, instead of editing cells in the loaded workbook.
- 82-30: a 'Manual Result' reference sheet contained the expected output; the agent re-derived it from raw data and got ordering wrong (51/54 cells mismatched).

## Patterns Addressed
- inspect-then-write-then-verify-loop (seed wiki): the verify phase needs a real range-aware read-back, not a re-print of the agent's own in-memory values.
- ground-truth-reference-sheet: needs a deterministic region-copy helper.
- expected-value-hints-in-instruction / self-consistent-verification-trap: anchor-finding must scan cells, not the pandas preview.

## Evolution History
- v1: `spreadsheet_helpers.helpers` created with `parse_range`, `find_all`, `write_values`, `read_back`, `save_and_check`, `copy_region`, `sheet_summary`.
