---
name: wikiskill-wiki
description: Patterns (problem, root cause, fix) compiled from past spreadsheet episodes; consult the index for the task at hand.
---

# Wiki index

- [tool-call-format-no-output-file](wiki/patterns/tool-call-format-no-output-file.md): Agent replies with pseudo tool-call XML instead of one ```python fenced block; harness executes nothing, rounds are wasted, and NO output file is written (score 0). FIX: always reply with exactly one ```python fenced code block, no prose or markup outside it.

- [text-instead-of-typed-values](wiki/patterns/text-instead-of-typed-values.md): Writing display strings like '-' or 'N/A' where the grader expects a real number, writing int where float is expected, or changing cells the instruction didn't ask to change. ROOT CAUSE: display rules misread as data edits; grader compares typed values including int-vs-float. FIX: write real values matching the expected type (float stays float), use number formats for hyphen/zero display, leave untouched cells untouched.

- [assume-extent-from-preview](wiki/patterns/assume-extent-from-preview.md): Output leaves most of answer_position empty (e.g. 6 of 42 cells) because the agent hard-coded table layout from the 5-row preview and sparse source data. FIX: print the full sheet region first and ensure every expected cell is filled per the scorer's COVERAGE count.

- [inspect-actual-columns-first](wiki/patterns/inspect-actual-columns-first.md): SUCCESS pattern — hard-coded column names from the prompt cause KeyErrors and wrong mappings. FIX: run one inspection round printing df.columns (or the raw grid with header=None), then solve, then re-open output_path and print answer_position to verify before finishing. Skill-assisted inspect→write→verify loop passed 577-40, 31915, 262-17, 108-24, 42354.

- [inserted-rows-need-content](wiki/patterns/inserted-rows-need-content.md): After row insertion/lookup tasks, scorer reports numbers LOWER than expected or low coverage because inserted rows were left blank and/or the whole range was cleared and rewritten from a DataFrame (destroying untouched cells, 326/897 vs 559 expected in 247-24). FIX: never clear-and-rewrite the full range from a DataFrame; edit in place, fill inserted rows with values, re-apply lookups on the final layout, and verify coverage against the expected count.

- [as-number-int-coercion](wiki/patterns/as-number-int-coercion.md): Whole floats coerced to int (by iolib.as_number or manual is_integer() logic) cause "int where float was expected" mismatches (398-14 failed twice, 1/56 cells, score 0 — even without the skill). FIX: preserve the column's existing float type; don't int-ify whole floats; compare written types to neighboring cells before finishing.

- [missing-value-filler-choice](wiki/patterns/missing-value-filler-choice.md): Filling 'N/A'/'' into every empty cell of the answer range gives "written past where the answer ends" when the expected output leaves missing cells EMPTY (58949 failed twice: 32/32 vs expected 12/32 — both times the agent had a CORRECT sparse first write and then second-guessed it). FIX: leave missing cells as None; a low non-empty count matching expected coverage is correct — never pad a sparse range to TARGET SIZE.

- [dedup-key-type-mismatch](wiki/patterns/dedup-key-type-mismatch.md): Duplicate rows survive a groupby/dedup because the key concatenated raw mixed-type values (int 2 vs str '2'), causing over-coverage (250-20: 200/200 vs expected 180). FIX: normalize key components (str(x).strip(), as_number) and explicitly check the final output for remaining duplicate keys — duplicates in the verify printout are a FAIL signal even at 100% coverage.

- [instruction-contradiction-priority](wiki/patterns/instruction-contradiction-priority.md): Contradictory trailing clauses in sort instructions ("also sort column H lowest to highest") applied as an extra re-sort on top of the primary ordering break the expected result (22-47: 4/27 mismatch). FIX: the first fully-specified rule governs; never re-sort already-sorted output; inspect the expected-result sheet in the workbook if present.

- [cascade-recompute-after-edit](wiki/patterns/cascade-recompute-after-edit.md): Changing an input column (e.g. Bill Rate 350→180) without recomputing dependent columns (bill-to, actual bill, profit) leaves cells "LOWER than expected" (247-24: 12/897, coverage otherwise perfect). FIX: after editing any input, recompute all columns that are functions of it and self-check derived cells arithmetically in the verify round.

- [group-vs-row-condition-scope](wiki/patterns/group-vs-row-condition-scope.md): Multi-branch conditional fills fail when group-level wording ("accompanied exclusively by SCH") is applied group-wide while sibling conditions are row-local, and blanket-rewriting overwrites cells whose original value was already correct (55421: 2/19 differ, 1 "own original input" violation). FIX: apply each clause at the scope its wording implies, and write only cells that differ from the original column — leave already-correct cells untouched.
