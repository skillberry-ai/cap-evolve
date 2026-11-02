---
name: reply-protocol
description: Reply format and verification protocol for the code-execution harness — every reply must be a single fenced python code block, literal values written to answer_position, and a final re-open verification.
compatibility: opencode
---

# Reply Protocol

## 1. Format rule

Every round, your ENTIRE reply must be exactly ONE fenced code block:

```python
...your code...
```

No prose before or after. No XML, no `<|tool_call|>` or JSON tool-call wrappers, no escaped quotes inside a wrapper. Nothing outside the fence.

If a previous round returned "No python code block was found", your next reply must be a plain fenced block with the same code — do NOT change the wrapper style or re-wrap it. The harness only extracts ```python fenced blocks; anything else is never executed.

## 2. No-repeat rule

If a verification round shows wrong or empty values in `answer_position` (or the execution result is unchanged from the previous round), NEVER re-submit the same or substantially identical code. Repeating code that already produced a wrong answer produces the same wrong answer. Instead, your next reply must be DIAGNOSTIC code that prints the actual raw cell values your computation keys on — the label/key columns and header rows of both the source and target tables (e.g. print the full key column of the target range and the header row of the source range) — so you can see why lookups return None or values mismatch.

Interpretation variation: the no-repeat rule ALSO applies when your verification shows full coverage but you had ANY doubt about how to interpret an ambiguous instruction clause (e.g. contradictory statements about output columns, or a clause like "sort only column H" alongside a primary ordering rule). In that case: (a) enumerate the plausible readings in comments, (b) prefer the reading consistent with the instruction's PRIMARY ordering/filtering rule over an extra transformation tacked on afterward, and (c) if a previous trial's interpretation produced wrong values, your next reply must implement a DIFFERENT reading — changing comments or formatting while keeping identical logic produces identical wrong output. Do not invent processing steps the instruction only mentions as a description of the expected result.

## 3. Workflow

- Round 1: inspect the workbook — read-only, no saving. Use openpyxl to print the raw values of EVERY column the instruction names or keys on (including which cells are None/empty), plus the neighborhood of `answer_position` (its header row and first data rows). Never write compute+save code before you have seen the actual source values. Conditional instructions ("if X, use column B; after X, use column C") require printing all involved source columns in full, so empty/missing cells and the threshold's location are visible before any branch logic is written.
  - FULL-EXTENT INSPECTION: inspection must cover the sheet's ENTIRE data extent as given in spreadsheet_content (e.g. rows 1-23 means print/aggregate through row 23, not just the first 10-20 rows). For long columns, print the full column or its distinct values plus total length — never assume a pattern seen in the first rows holds throughout. Additionally: NEVER hardcode lookup grids, bucket boundaries, or table values copied from a partial preview into your computation code — always read them from the actual cells programmatically, so a truncated view cannot silently drop part of the structure.
- ALL-PARAMETERS RULE: before writing lookup/classification logic, list in a comment every parameter the instruction names (e.g. 'Goal', 'Variance to Goal', 'Metric2'). Every named parameter must participate in the lookup. If your function ignores one of them (e.g. indexes a payout grid by only two of three named dimensions), your reading is wrong — re-read the instruction and find where the missing dimension's structure lives in the sheet before computing.
- Later rounds: compute and write the results to `output_path`.
- If the instruction mentions a sample, manual, or reference sheet, or says part of the answer is already completed (e.g. "you can refer to the X sheet", "I've completed results for the first rows"), treat that as ground truth: read it before computing, and match its ordering and formatting. Before finishing, print a cell-by-cell comparison of your written `answer_position` values against those reference values. If they differ, your method is wrong — fix the method (ordering, filtering, mapping), not just the cells.
- If the instruction uses a threshold ("before X", "after X", "greater than X"), print the row(s) at and immediately around the threshold value, and state in a comment which side the boundary row itself falls on (is the row equal to X included or excluded?). Off-by-one at the boundary is a classic single-cell failure.
- Always end with a verification round that re-opens `output_path` and prints the values in `answer_position`.

## 4. Literal values

Write computed literal values (numbers/strings) into `answer_position`, not live Excel formulas (`'=IF(...)'`), unless the instruction explicitly demands a formula. Graders read re-opened cell values; formula strings often store as text or evaluate differently.

## 4b. Blank-justification rule

Every None/empty cell you write into `answer_position` must be justified: print the source-row cells that produced it and cite the instruction clause that mandates leaving it blank. Do NOT conflate "the selected source cell is empty/missing" with "the result is 0, leave blank" — an instruction like "if it's 0, just leave blank" applies to a COMPUTED zero, not to a missing or unparseable source value. When the selected source cell is None, print it and re-read the instruction to decide (e.g., fall back to the other column, treat as 0, or carry the row's other value) instead of silently emitting an empty cell.

## 4c. In-place edit rule

For Sheet-Level Manipulation tasks — and ANY instruction containing "keep the original location of the data unchanged", "leave untouched", or similar — you must edit the ORIGINAL workbook in place: `openpyxl.load_workbook(spreadsheet_path)`, modify ONLY the cells the instruction names, then `wb.save(output_path)`. NEVER round-trip through pandas (`pd.read_excel` → `df.to_excel`): that rebuilds the sheet from scratch, rewrites cells the instruction does not ask you to change, drops original layout/formatting, and can shift or drop trailing rows. pandas may be used for READING/inspection only; the file you save must be the original workbook object with only the mandated cells modified.

## 5. Finish checklist

Do not reply without a code block until ALL pass:

1. `output_path` exists.
2. Every cell in `answer_position` that should hold a value does — verification must print the entire `answer_position` (or per-row/per-column summary counts for large ranges), not just the first few rows, and report the non-empty cell count. If the count is far fewer than the data extent suggests, check where the data actually ends rather than assuming from the preview. If any region is unexpectedly empty or values are repeatedly None, apply the no-repeat rule: switch to diagnostic code and do not finish while unexplained Nones remain inside the data extent.
3. The values match the instruction's semantics.
4. MINIMAL-DIFF VERIFICATION: load BOTH the original input workbook and the saved output workbook, and print a cell-by-cell comparison over `answer_position` — report the count and coordinates of cells that differ. Every differing cell must be justifiable by an explicit clause in the instruction ("change Column I to 0", "add X to unit columns"). If any cell differs from the input that the instruction does not ask you to change — the scorer treats "expected value = the cell's own original input" as a failure — your write path is wrong (most likely a pandas round-trip or an off-by-one range): fix the method, do not just patch the cells. Also confirm you have not written values past where the data ends (no new non-empty cells beyond the original data extent plus cells the instruction explicitly fills).

## 5b. Stop rule

If a verification round confirms every intended value is present and correct AND the execution result is identical to the previous round's, reply WITHOUT a code block to finish. Never resubmit identical code hoping for a different result — identical code produces identical output.

## Example

Bad (never executed by the harness):

<|tool_call|>call:python_interpreter {"code": "print(1)"}<tool_call|>

Good:

```python
from openpyxl import load_workbook
wb = load_workbook("/mnt/data/input.xlsx")
ws = wb.active
print(ws["A1"].value)
```
