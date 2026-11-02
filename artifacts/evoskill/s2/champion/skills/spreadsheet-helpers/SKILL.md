---
name: spreadsheet-helpers
description: Deterministic helper scripts for spreadsheet manipulation tasks — inspect real structure before writing, write exact ranges, VLOOKUP-safe lookups, verify saved output values and types.
compatibility: opencode
---

# spreadsheet-helpers

Four general, offline, deterministic helper scripts for spreadsheet tasks. Each takes its
inputs as arguments and writes only to the path it is given. Import them inside the kernel as:

```python
from skills.spreadsheet_helpers.inspect_region import inspect_region
from skills.spreadsheet_helpers.write_range import write_range
from skills.spreadsheet_helpers.verify_range import verify_range
from skills.spreadsheet_helpers.excel_lookup import excel_lookup
```

## inspect_region(path, sheet, around_range=None)

Opens the workbook and reports the **real** structure around a target range: every non-empty
cell's coordinate and value in the rows above and columns beside the target, detected header
candidate rows, and the true data extent of each relevant column and row block.

Call it **before** writing anything — never assume header positions or table extent from the
truncated preview. Previews routinely mislead (e.g. labels one row off, or a table that
continues past the visible rows); `inspect_region` reads the actual cells.

## write_range(src_path, out_path, sheet, range_str, values)

Writes a 2D list of values to the exact target range in a workbook loaded from `src_path`,
saved to `out_path`. Cells outside the range are untouched; cells inside the range beyond the
provided values are set to None (stale content cleared, so nothing is written past where the
answer ends). Also accepts a list of `(cell_ref, value)` pairs with `range_str=None` for
scattered answer positions.

**Never** rebuild a workbook via pandas `to_excel` — it rewrites the whole sheet and destroys
everything else. Always write results through `write_range` to the exact answer range given
in the task.

## excel_lookup(src_path, sheet, key_col, value_col, keys, default='#N/A')

Reads a lookup sheet once and returns values for `keys` (list aligned with `keys`; missing
keys yield `default`). It matches **Excel VLOOKUP exact-match semantics**:

- **first occurrence wins**: when a key appears in multiple rows, the FIRST row's value is
  returned — a hand-rolled `dict[key] = value` keeps the LAST duplicate and gives wrong
  answers on duplicated IDs;
- **key coercion**: int `1111` and str `'1111'` match (strings trimmed; numeric-looking
  strings compare numerically; other strings compare case-insensitively) — mixed int/str IDs
  never silently fail to match.

Use it whenever an instruction says VLOOKUP or "populate column X by matching IDs from
another sheet" — **never** a hand-rolled dict comprehension, which gets both duplicate and
type handling wrong. Example:

```python
ids = [row[0] for row in target_rows]
vals = excel_lookup(src_path, "Lookup", "A", "D", ids)
```

## verify_range(path, sheet, range_str, expect_values=None, answer_range=None)

Re-opens the saved output file, counts and prints every non-empty cell with its coordinate,
and emits explicit warnings for:

- empty ranges (with or without intended values);
- count mismatches vs `expect_values` (too many = values written past where the answer ends;
  too few = incomplete coverage);
- **per-cell value mismatches** — `expect_values` may be an int count, a flat list
  (row-major), a 2D list, or `[(cell_ref, value), ...]` pairs; when values are given, each
  differing cell is reported as `(cell, expected, actual)` (up to 10) so wrong rounding or
  wrong lookups are visible before finishing. It never raises on argument shape — an
  unusable shape yields a clear warning and count-only verification;
- **numbers stored as text** — when every non-empty cell in the range is a string that looks
  numeric, it warns: write numbers as numbers, not strings;
- **answer_position coverage** — pass `answer_range=<answer_position from the task, verbatim>`
  and it cross-checks that `range_str` covers the SAME columns and rows. If the verified range
  is a strict sub-range (e.g. verifying G2:H10 when the answer_position is F2:H10) it warns
  that every column of the answer_position must hold its expected values; it also warns when
  the verified range extends beyond the answer_position.

## Decimal formatting rule

When an instruction specifies decimal precision (e.g. "zero has no decimal places, single
non-zero decimal place has one, others have nine"), write **numeric values** —
`round(value, 9)` / `round(value, 1)` / `int 0` — never formatted strings like `f"{v:.9f}"`.
Excel stores the rounded number and the scorer compares types, so text fails even when the
digits are right. Then verify with `verify_range(..., expect_values=values)` so wrong
rounding is caught before finishing.

## Mandatory workflow

1. **ALWAYS call `inspect_region` before writing.** Determine the true header row and data
   extent from its report — never from the preview.
2. **Write results only via `write_range`** to the exact answer position from the task.
   For lookups, compute the values with `excel_lookup`, not a dict comprehension.
3. **ALWAYS call `verify_range` after saving**, passing `expect_values` with the actual
   expected values whenever they are known, and ALWAYS passing `answer_range=<answer_position
   from the task>` — and ALWAYS call it on the **full answer_position**, never on a sub-range
   you happened to write. If you intentionally leave a column of the answer_position
   untouched, verify that column too and justify why its current content is already correct
   cell-by-cell. If it reports empty cells, missing coverage, values past the expected end,
   per-cell mismatches, or numbers stored as text, diagnose and fix — then rewrite — within
   the same session. Do not re-run the same code unchanged, and do not give up while
   verification still reports a problem; an all-empty range means the write did not land
   where you think it did, and do not "fix" a failing verification by dropping
   `expect_values` — that hides wrong values behind a passing coverage check.

**Never self-echo verify.** NEVER pass the same variable you gave to `write_range` as
`expect_values` — that only confirms the write landed, not that the values are right. Before
trusting a clean verify, re-derive the expected values independently:

- recompute the result a second way — a different code path, e.g. re-read the source with
  openpyxl and re-derive the values — and compare the two computations; or
- check a structural invariant the instruction implies (e.g. "names in column J appear
  first, in J's order, no duplicates by (B,C), remaining rows in original order" — assert
  each invariant separately against the written output).

A clean verify derived from the same computation that produced the output proves nothing.

## Instructions with multiple or conflicting sort/filter clauses

Many instructions describe a detailed multi-step procedure (group by a helper list, preserve
original order, dedupe by a composite key) and end with a short summary clause ("sort only
column H lowest to highest") that seems to contradict it. Resolve in favor of the **detailed
clauses** — the trailing sentence describes which output column carries the sort key / the
final presentation, not an override that discards the procedure. Sanity-check your chosen
interpretation against the answer_position layout: a 3-column answer range means all 3
columns, including any ITEM/index column, are part of the graded result. And when the scorer
or verification cannot distinguish between interpretations, **vary the interpretation on the
next attempt** — never re-run the byte-identical code block.

Judgment calls — such as how strictly to match words when filling cells — stay in your
reasoning; the structure-inspection, exact-range write, lookup, and verify-fix loop above
are procedures that must always go through these helpers.
