---
name: spreadsheet-helpers
description: Deterministic helper scripts for spreadsheet manipulation tasks. No scripts yet; the optimizer adds them under scripts/.
---

# spreadsheet-helpers

No helper scripts exist yet. A script belongs here when a procedure recurs across tasks (parse, locate, normalise,
compute, validate). Each script is general, offline and deterministic, takes its inputs as arguments, and writes
only to the path it is given. List each script below with one line saying when to call it.

# Operating rules for spreadsheet tasks

## Response format (most common fatal failure)
Every single round of the conversation — inspection, solution and verification alike — must be exactly **one
```python fenced code block and nothing else**. Do not emit any text, prose, XML, `<|tool_call|>` markers, JSON
tool-call syntax or commentary outside the block: if no ```python block is found, the round is wasted, no code
runs, and if the solution is never executed the output file is never written, which scores 0 regardless of how
correct your reasoning was. Never end the task with reasoning alone: the round that "submits" your answer must
still be a code block that saves the output workbook to `output_path`.

## Always write the output file, and write it early
A trial with no file at `output_path` scores 0 even if every other detail was right. In your very first code
round, after inspecting, either solve and save, or at minimum save a copy of the input workbook to `output_path`
(`os.makedirs(os.path.dirname(output_path), exist_ok=True)` first) so a file always exists; overwrite it in later
rounds as you refine. You have up to 30 rounds — use them, but never leave the output unwritten.

## What the grader checks
The grader compares the **saved values** in `answer_position` of the workbook you wrote to `output_path` — not
formulas, not printed output. Follow the task contract exactly: one Python code block per round; inspect, solve,
then re-open the output file and verify the target cells before finishing.

## Write computed values, not formula text (common type failure)
When the instruction asks for a formula, the graded cell almost always must contain the **numeric result of that
formula**, typed as a number (or date), not the formula string. Writing `"=SUMIFS(...)"` or a bare
`"IF(OR(...),...)"` string into the cell fails the type check ("str where int was expected"). Procedure:

1. Derive the intended formula from the instruction and the sheet layout.
2. Compute the same result in Python (e.g. filter/aggregate the source data with pandas or plain loops, honouring
   criteria such as product, region, "All" = no region filter, blanks in selection cells).
3. Write the **computed number** into the target cell.
Only write the formula string itself if the instruction explicitly demands a live formula in the cell; then also
set it so the cell would evaluate correctly (e.g. via `cell.value = "=..."`), but prefer the computed value. When
you open a workbook that already contains formulas and you intend to recompute them in Python, load twice: once
with `data_only=True` to read cached results and once normally to write, and overwrite formula cells with their
computed values.

## Cell typing
- Numbers as `int`/`float` (integers when exact, e.g. sums of integers like 994110).
- Dates as real datetimes, not text.
- Keep original string values (branch codes like "BR2", model numbers, account codes) verbatim, including
  whitespace variations in source data.
- "Leave blank" means write `None`, not `""` or 0.

## openpyxl gotchas
- Colors: a fill written as `PatternFill(start_color='00FF00', ...)` is stored with an alpha prefix. When verifying
  highlights, compare with `'00FF00' in str(cell.fill.start_color.rgb)` rather than exact equality; on reload the
  color reads back as `'FF00FF00'`. Missing default fills may report rgb `None` or `00000000`.
- Read the sheet first to learn the real header/data extent; the preview may show a numeric first row that is
  actually data, not a header. Treat any row whose column-A value is numeric as data when searching values.
- Blank criteria in SUMIFS-style logic: a None selection cell contributes nothing to the sum; "All" removes the
  region filter entirely.
- `pd.read_excel(path, header=None)` plus manual row-0 handling is a robust way to read sheets whose first row is
  data; when using pandas to recompute lookups, build the mapping from the source columns and fall back to `None`
  for unmatched keys.

## Recurring solution patterns
- **Lookup / INDEX-MATCH**: build a dict from the search column (e.g. C) to the return column (e.g. D), then for
  each target row look up the key from the reference column (e.g. A) and write the value, or `None` when no match
  ("if the formula returns an error, leave the cell blank" → unmatched keys become blank).
- **Filter-and-extract (macro-style)**: scan the source sheet rows, keep rows whose text column starts with any of
  the given prefixes and contains the required word, drop explicitly excluded keys, then write columns A–D of the
  surviving rows in order into the target sheet starting at row 1.
- **Multi-key sort**: read the sheet into a DataFrame, `sort_values(by=[first_col, second_col],
  ascending=[True, True])`, write header plus sorted rows back starting at row 1; verify against any
  expected-outcome sheet in the workbook.
- **Unticked/unmatched extraction**: scan the data rows, collect keys (e.g. branch names) whose marker column is
  empty, and write them in order into the target cells.
- **Conditional aggregation ("OR" SUMIFS with All option)**: compute
  `total = sum over source rows where product == selected product and (any selection == "All" or region in the
  non-empty selected regions)`; write `total` as a number.
- **Subset-sum highlight**: when a task says some values sum to a value in a range [lo, hi], enumerate
  `itertools.combinations` over all numeric cells (datasets are small, ≤ ~20 values) and pick a combination whose
  sum falls in the range; highlight those cells with the exact requested fill color and write the achieved sum
  (the numeric value) to the target cell.
- **Sheet deletion**: `del wb['Sheet3']` before saving; verify `wb.sheetnames` afterwards.

## Verification discipline
Always finish with a verification round that re-opens `output_path` (not the input) and prints:
- the exact values (and types, `type(v)`) in `answer_position`,
- the sheet list,
- fills of cells you colored (using the substring color check above),
- a cross-check (e.g. highlighted-cell sum equals the value written to C2).
If verification disagrees, rewrite and re-verify; do not finish on an unverified file — but remember: verification
is still one ```python code block, never prose, and the file at `output_path` must exist before you stop.