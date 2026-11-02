# Purpose

## Origin
Iteration 2. The accepted v1 skill `spreadsheet_helpers` (open_inplace / write_cells / verify_range /
diff_report / oracle_check) fixed pandas full-sheet rewrites, but analysis of the iteration-2 training
traces shows a distinct, still-fatal failure mode it does not cover: **over-filling the answer range**.

- 54638 (0/3 rollouts): target `Sheet1!B2:B150` (149 cells); the user's sample pre-fills only 9 cells.
  The agent wrote a formula into all 149. Scorer: 'your output has a value in 149; the expected output
  has a value in 9; 144 cells CHANGED although the expected value is the cell's own original input'.
- 58484 (0/3): the 'Expected Result' column already held example values (9 of 22); the agent overwrote
  them with formulas and left most of the range blank. Scorer: 'your output has a value in 1; expected 9;
  8 empty where a value is expected; 5 CHANGED although expected is original input'.
- 408-39 (0/3): agent wrote 3 values where the expected answer holds 2 ('written past where the
  answer ends').
- 194-19 (0/3): 16 cells 'hold a value where the expected output has none — written past where the
  answer ends'; 80 cells 'CHANGED although the expected value is the cell's own original input'.

In every case the correct stopping point was visible in the INPUT file as the extent of the pre-filled
example cells — a deterministic signal, so it belongs in a helper, not prose. Note that the existing
diff_report cannot catch this: over-written pre-filled cells and extra in-range values are tagged
IN-RANGE, so the OUT-OF-RANGE count stays 0 and the agent declares success (exactly what happened in
247-24 and 46646 traces).

Secondary mode (46646, 0/3; 247-24 adjacent): the task demanded values with 'nine decimal places';
the agent rounded in Python (round(0.3225806452, 9) truncates to 0.322580645) and lost digits — 10 of
12 cells wrong. The fix is to write the full-precision value and set `number_format`, which also
belonged in a helper.

## Patterns Addressed
- use-sample-rows-as-oracle (extension: the examples also delimit WHERE the answer ends, not just what
  the values should be)
- verify-write-values-not-assumptions (coverage_check is a new signal: written count vs pre-filled
  count, catching what per-cell verification of intended values cannot)
- preserve-untouched-cells-openpyxl (over-writing pre-filled cells is collateral damage INSIDE the
  range, which diff_report tags IN-RANGE and therefore does not flag)
- write-typed-time-values-not-strings (same class: display formatting via number_format, never mangle
  the stored value)

## Evolution History
- v1 (iteration 1, accepted, `spreadsheet_helpers`): xlsx_edit.py + xlsx_oracle.py — in-place editing,
  per-cell verification, input/output diffing, oracle validation. Train accuracy 0.683 -> 0.767.
- v2 (iteration 2, this skill `fill_coverage`): new script xlsx_fill.py (prefill_stats,
  coverage_check, set_number_format, clear_cells) plus the three judgment rules: never over-fill past
  the pre-filled examples, run coverage_check after saving, and treat decimal-place instructions as
  number_format rather than Python rounding. Complements, does not modify, the incumbent skill.
