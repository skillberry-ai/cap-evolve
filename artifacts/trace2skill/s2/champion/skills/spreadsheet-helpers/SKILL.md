---
name: spreadsheet-helpers
description: Deterministic helper scripts for spreadsheet manipulation tasks.
---

# spreadsheet-helpers

Each script is general, offline and deterministic, takes its inputs as arguments, and writes only to the path
it is given. Import with `from skills.spreadsheet_helpers import <module>`.

## Helper scripts

- `verify` — read [`skills.spreadsheet_helpers.verify` (helper script)](`skills.spreadsheet_helpers.verify` (helper script)). Call `verify.verify_output(output_path, answer_range, input_path=None)` after every write: it re-opens the saved workbook, prints the answer-range contents, and (if `input_path` is given) lists any cells changed outside the answer range. Use `verify.explore(path, sheet=None, n=10)` early to print sheet names, dimensions and sample rows, and `verify.check_filled(path, sheet, ref)` to assert no cell in the target range is empty.
- `workbook_edit` — read [`skills.spreadsheet_helpers.workbook_edit` (helper script)](`skills.spreadsheet_helpers.workbook_edit` (helper script)). Call it whenever you edit an EXISTING workbook in place: `write_range` writes only the cells covered by your values (integers stay integers, formatting elsewhere preserved); `read_range`/`verify_range`/`compare_unmodified` verify the saved file with exact value AND type checks.
- `inspect_layout` — read [`skills.spreadsheet_helpers.inspect_layout` (helper script)](`skills.spreadsheet_helpers.inspect_layout` (helper script)). Call `inspect_layout.dump_rows` before writing any row-matching or counting logic to see the real layout (blanks shown as '.'), and `inspect_layout.key_groups` to propagate keys down through blank/merged cells when a key does not repeat on every row.
- `inspect` — read [`skills.spreadsheet_helpers.inspect` (helper script)](`skills.spreadsheet_helpers.inspect` (helper script)). Call `inspect.show_cells(path, refs)` to see the actual value, type and number format of key input cells (dates, lookup tables, key columns), and `inspect.parse_date` for loud, never-silent date parsing.
- `sheettools` — read [`skills.spreadsheet_helpers.sheettools` (helper script)](`skills.spreadsheet_helpers.sheettools` (helper script)). Call `sheettools.find_header_rows` when a task says to skip headers or a sheet may contain embedded/repeated header rows.
- `row_counts` — read [`skills.spreadsheet_helpers.row_counts` (helper script)](`skills.spreadsheet_helpers.row_counts` (helper script)). Call `row_counts.count_values_in_rows(sheet, key, key_col, count_cols, values)` for COUNTIF/COUNTIFS-style counting of codes over raw detail cells for a selected key.
- `match_rows` — read [`skills.spreadsheet_helpers.match_rows` (helper script)](`skills.spreadsheet_helpers.match_rows` (helper script)). Call `match_rows.match_by_keys(left_df, right_df, left_keys, right_keys)` to map rows between sheets by key columns; it raises on duplicate key combinations so positional-order mistakes cannot slip through silently.
- `fill_by_key` — read [`skills.spreadsheet_helpers.fill_by_key` (helper script)](`skills.spreadsheet_helpers.fill_by_key` (helper script)). Call when filling a destination column from another sheet by matching an identifier; it writes only matched cells and leaves everything else untouched.
- `lookup_helpers` — read [`skills.spreadsheet_helpers.lookup_helpers` (helper script)](`skills.spreadsheet_helpers.lookup_helpers` (helper script)). Call `lookup_helpers.apply_vlookup(main_df, key_col, lookup_df, value_col, target_col)` whenever emulating a VLOOKUP: dict-mapping, so NaN/missing keys can NEVER match, exactly like a real VLOOKUP.

## Reply format (critical)

- Every reply must contain exactly ONE plain ```python fenced code block with runnable code. Never wrap code in `<|tool_call|>` tags, XML or any other tool-call markup — the environment executes only fenced python blocks, and anything else wastes the round.
- If feedback says "No python code block was found in your reply", your format was wrong: resubmit the same code inside a plain ```python block immediately. Never resubmit a failing reply unchanged; treat every error observation as actionable and change the failing element before retrying.
- Budget your rounds: one to inspect the input file, one to write the result to the given output path (write early — even a partial correct file beats none), one to re-open and verify the saved file.

## Rules that prevent known failure modes

1. **Write only inside the answer range.** The answer_position is the authoritative boundary. Instruction text mentioning other operations is context, not permission to modify out-of-range cells. Write exactly the requested columns — do not add extra columns "to be safe".
2. **Inspect before you implement.** Never hard-code a column range, row layout or mapping from prose or a preview; previews are truncated. Run `verify.explore` / `inspect_layout.dump_rows` / `inspect.show_cells` first, and read pre-completed example or cited cells to reverse-engineer the intended rule. Never assume a key repeats on every row — use `inspect_layout.key_groups` for paired/merged layouts.
3. **Count and aggregate from raw detail data, never from pre-existing summary/aggregate columns.** Implement the stated counting method over raw detail cells; summary columns may be blank, formula-driven without cached values, or computed under different rules. If the workbook has in-sheet totals, cross-check your computed values against them and reconcile mismatches.
4. **Match rows by key, never by position.** Identify ALL key columns (inspect data and completed example rows) and match on those keys. Do not assume row order aligns between sheets or within a group.
5. **Edit the original workbook in place with openpyxl.** Do NOT rebuild sheets with pandas `read_excel` -> `to_excel`: NaN-containing DataFrames coerce integers to floats (100 -> 100.0) and `to_excel` rewrites every cell, destroying formatting and touching cells outside the permitted range. Use `workbook_edit.write_range`, `fill_by_key` or `cell`-level writes.
6. **Never overwrite cells you did not compute.** Inspect existing values in the target range first; if the input has completed example rows, fill only the empty target cells and reproduce the existing values exactly.
7. **Do not emulate lookups with `pd.merge`.** Pandas treats NaN as a joinable value, so NaN keys on both sides match each other and fabricate values VLOOKUP would leave blank. Use `lookup_helpers.apply_vlookup`. For "current value as of date" lookups, define an explicit default for dates before the earliest threshold instead of leaving the cell blank.
8. **Match cell values exactly, preserving case.** Do NOT `.upper()`/`.lower()` values before comparing to category codes unless the task says codes are case-insensitive.
9. **Encode domain semantics explicitly.** If the task states structural rules (e.g. two rows per person = two half-days), write logic that combines them instead of summing raw cell occurrences.
10. **Separate search criteria from output ordering.** A list given "to sort/group results by" defines output order only — it is NOT the matching filter. Do not override a primary sort with a secondary sort; a trailing sort clause is a tie-breaker or a description of the expected result.
11. **Exclude header rows explicitly.** Load with `pd.read_excel(..., header=None)`, use `sheettools.find_header_rows` to locate embedded headers, and exclude those row indices — `dropna`/`drop_duplicates` do not remove headers.
12. **Relative references shift with the destination cell.** If relocating a formula containing relative references (e.g. `$I3`) to a destination like K6, it evaluates against the destination row's cells (I6), not the literal addresses in the prose.
13. **No silent failures.** NEVER use bare `except: pass` or try/except that sets a value to None when parsing input cells — print the raw value and its type and fix the parser. Never write conditionally without an else-branch that reports the skipped key.
14. **Verify before finishing — as a pass/fail gate.** After saving, re-open the output with `verify.verify_output` / `workbook_edit.verify_range` and check: no empty cells, no leftover header-like text, correct ordering, exact values and types, unmodified cells unchanged, and edge cases (rows with missing/NaN keys must have empty result cells). Compare against pre-completed example rows in the input — they are a free correctness oracle. A printout of head(20) proves nothing.
15. **Treat implausible output as failure.** All-zero results, doubled counts or unexpected blanks are red flags: print the actual source rows and confirm the data exists where you expect it before finalising.
16. **Never re-run identical failing code.** If a round produced no new information, the next execution must differ — a diagnostic probe or a modified solution. Only call helpers listed above; never invent helper names — write plain Python instead.
