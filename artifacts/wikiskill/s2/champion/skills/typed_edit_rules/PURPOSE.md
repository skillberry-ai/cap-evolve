# Purpose

## Origin
Iteration 3. Iteration 1 created `spreadsheet_helpers` (iolib) and was ACCEPTED (0.717 → 0.842). Iteration 2 attempted to extend it but was REJECTED with accuracy 0.0 — post-mortem of the diff shows the patch was structurally broken: it inserted `def astype_like(...)` between `def write_block(ws, anchor, values):` and its docstring, making the entire `write_block` body a nested function definition, so every write call failed. The *guidance* in that proposal was sound and maps directly onto the wiki patterns; this iteration re-applies it as a SEPARATE skill so the working iolib is untouched.

## Patterns Addressed
- cascade-recompute-after-edit (247-24 t0/t1/t2: 12/897 cells "LOWER than expected", coverage perfect — Bill Rate changed 350→180 without recomputing bill-to/actual bill/profit): rule on recomputing all derived columns and self-checking them arithmetically in the verify round.
- missing-value-filler-choice (58949 t0/t1/t2: agent wrote a CORRECT sparse answer (12/32 non-empty matching expected), then second-guessed it and padded 'N/A' to 32/32 — fail): rule that a sparse write matching expected coverage is correct and must never be padded to TARGET SIZE.
- instruction-contradiction-priority (22-47 t0/t1/t2: agent applied the contradictory trailing "sort only column H lowest to highest" as an extra re-sort on top of the helper-list ordering, 4/27 differ): first fully-specified rule governs.
- as-number-int-coercion (398-14 all three rollouts: "int where float was expected" on the BALANCE column plus one overwritten original cell): `astype_like` helper coerces derived numbers to the original column's int/float type.
- group-vs-row-condition-scope / inserted-rows-need-content (55421 t2: 1 overwritten cell whose original value was already correct): `changed_cells` helper yields only cells that differ from the original, enabling minimal in-place edits instead of blanket rewrites.

## Evolution History
- v1 (iteration 1, accepted): iolib with open_output, as_number, write_block, read_region, show_region, verify_output, diff_region.
- v2 (iteration 2, rejected): attempted in-place patch of iolib.py; broken diff destroyed write_block, candidate scored 0. Lesson: never insert new function definitions inside existing function bodies via patch diffs.
- v3 (this proposal): new independent skill `typed_edit_rules` alongside spreadsheet_helpers, with its own script `typelib.py` (astype_like, changed_cells). No task ids, no network, no scorer access, no branches on task content.
