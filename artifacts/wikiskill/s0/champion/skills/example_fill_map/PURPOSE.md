# Purpose

## Origin
Iteration 6. With `spreadsheet_helpers` (it1) and `fill_coverage` (it2) accepted, iteration-6
training traces still show one dominant, recurring, deterministic failure cluster: **the input
file's pre-filled example cells are ignored as both an oracle and a fill map**, plus a terminal
save failure.

- 58484 (0/3): the 'Expected Result' column held 5 example values marking exactly which rows
  carry a count (9 expected values, one per qualifying row). The agent blanket-filled H5:H26
  with IFERROR(...,"") formulas, which blanked/clobbered the example cells: 'your output has a
  value in 1; expected 9; 8 empty where a value is expected; 5 CHANGED although the expected
  value is the cell's own original input'. The example coordinates ARE the fill map.
- 54638 (0/3): same mode — sample outputs in part of B2:B150 marked 9 cells; the agent filled
  all 149 with array formulas evaluating to "", scoring 1 vs 9 values and clobbering 4 example
  cells.
- 48983 (0/3): the target M6:S11 had pre-filled example values; the agent's brand/category key
  mapping was off by one (pandas preview columns vs real Excel columns), so only 5 of 42 cells
  were written ('most of the expected answer is missing'). Validating against the example
  cells before writing would have shown the lookup returning None where examples hold numbers.
- 46121 (0/3): coverage matched (48/48) but 2 cells were LOWER — semantics; the example cells
  are the only in-file oracle for the correct sum semantics.
- 11842 t0 (0/3): the write happened in an earlier round, but the episode ENDED on a
  read-only verification block; the scorer reported 'NO output file — the code never wrote
  output_path'. A save-and-confirm final turn is a pure procedure.

Rejected proposals are NOT repeated: it3 `fill_guards` (fill-count/preview/quiet-diff bundle),
it4 `formula_oracle` (formula evaluation engine + CSE/ArrayFormula writing), it5
`coordinate_anchors` (find_label/anchor_check). This new skill complements the accepted pair
with one small script `xlsx_examples.py` plus four rules. It reads example cells' CACHED
evaluated values (a data_only load — no formula-parsing engine, avoiding the it4 rejection
surface), uses their coordinates as the fill map via a plain dict write, and guarantees the
final turn saves. It uses the existing spreadsheet_helpers (open_inplace, verify_range,
diff_report) for editing and verifying; it adds only the example-as-oracle-and-fill-map layer.

## Patterns Addressed
- use-sample-rows-as-oracle (primary: examples as oracle with evaluated values AND as the
  exact fill map — write on the example coordinates, never blank one)
- match-fill-count-to-expected-answer (write_coords fills exactly the marked cells; no
  blanket IFERROR-fill that blanks examples)
- evaluate-example-formulas-as-oracle (cached data_only values, no parsing engine)
- verify-write-values-not-assumptions (validate_examples must pass before writing)
- last-round-must-save-output (save_and_confirm in the final code block)
- excel-vs-pandas-coordinates-off-by-one (rule 3: a lookup that returns None on example cells
  proves the key mapping is wrong before anything is written)

## Evolution History
- v1 (it1, accepted, `spreadsheet_helpers`): xlsx_edit.py + xlsx_oracle.py. Train 0.683 -> 0.767.
- v2 (it2, accepted, `fill_coverage`): over-fill guard + number formats. 0.767 -> 0.792.
- v3 (it3, REJECTED, `fill_guards`) — do not repeat.
- v4 (it4, REJECTED, `formula_oracle`) — do not repeat.
- v5 (it5, REJECTED, `coordinate_anchors`) — do not repeat.
- v6 (it6, this skill `example_fill_map`): xlsx_examples.py (example_cells, validate_examples,
  write_coords, save_and_confirm) and rules: examples as evaluated oracle, examples'
  coordinates as the exact fill map, mostly-blank output means wrong keys (validate before
  writing), and end every episode with save_and_confirm. Complements the accepted skills.
