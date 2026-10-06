<!--
  Capability file: the agent's FIRST USER MESSAGE. Placeholders are filled in per task and are
  load-bearing — {instruction} {spreadsheet_path} {spreadsheet_content} {instruction_type}
  {answer_position} {output_path} must all survive; {max_turns} is optional. A literal brace is
  written {{ or }}. This comment is stripped before the agent sees the message.
-->
Solve the following spreadsheet manipulation task. It is described by six fields:

- **instruction** — what to do. It is written as a question from a spreadsheet user, so it often
  asks "what formula should I use". What is graded is the resulting cell **values**, never a
  formula string (see the CONTRACT below).
- **spreadsheet_path** — the input workbook. Read it; never modify it in place.
- **spreadsheet_content** — a `pandas.read_excel(...).head()` preview of each sheet, plus the
  sheet's true `[data extent]` and the size of the target range. The printed rows are a sample;
  the data extent is the whole sheet.
- **instruction_type** — `Cell-Level Manipulation`: `answer_position` is the exact set of cells
  that is graded. `Sheet-Level Manipulation`: `answer_position` is the **maximum** range you may
  modify, and the expected answer often fills only part of it.
- **answer_position** — the graded cell(s)/range. It bounds *where* you may write; the
  **instruction** says *what* goes where. When the instruction names a more specific place (e.g.
  "put the result starting at I3, with headers"), follow the instruction — do not spread your
  answer over the whole range just because the range is bigger.
- **output_path** — write the finished workbook to this exact path.

### instruction
{instruction}

### spreadsheet_path
{spreadsheet_path}

### spreadsheet_content
{spreadsheet_content}

### instruction_type
{instruction_type}

### answer_position
{answer_position}

### output_path
{output_path}

## CONTRACT — what makes an answer correct

The grader opens your file with `openpyxl.load_workbook(output_path, data_only=True)` and
compares the **stored values** in `answer_position` to the expected workbook. It does **not**
recalculate formulas and it does **not** read anything you write in prose.

1. Every graded cell holds a **literal computed value**, never a string beginning with `=`. A
   formula written by openpyxl has no cached value and reads back as empty, so it scores zero
   however correct it is — including when the instruction asks for a "formula".
2. Values are **correctly typed**: numbers as `int`/`float` (never `"1,234"`, `"$5.00"`,
   `"12%"`), dates as `datetime` objects, text as the exact string. Never an Excel error marker
   such as `#N/A`. Numbers are compared rounded to 2 decimals.
3. Every cell the expected answer fills is filled, and every cell inside `answer_position` that
   the instruction does **not** ask you to change or clear still holds its **original input
   value**. Already-filled target cells are usually the asker's worked example — reproduce them,
   don't overwrite them.
4. Content the instruction never mentions — other sheets, other populated columns, formatting —
   still holds what it held in the input. Filling an empty helper cell is harmless; overwriting
   or blanking data that was already there is not.
5. **Exception — deleting whole rows or columns.** When the instruction asks to delete/remove
   entire **rows** or **columns** (not merely "delete the values" in some cells), really delete
   them with `ws.delete_rows(r)` / `ws.delete_cols(c)`, iterating from the bottom/right so the
   indices stay valid. The content below/right must **shift up/left**; blanking the cells in place
   leaves gaps where the expected answer has the shifted data, so every cell after the first
   deletion is wrong.

## HOW TO WORK — you have up to {max_turns} rounds

Each reply must be **exactly one ```python fenced code block** and nothing else. Its stdout is
returned to you; if it raises, you get the traceback and can fix it. Only the first code block of a
reply is executed, and its real output arrives in the next message — never write out what you
expect the output to be, and never answer as if a block had run before you have seen its output.
Work through these three phases in order.

**Phase 1 — INSPECT (1–2 rounds; do not skip).** Never write your answer from the preview alone.
Load the input and `print` what you need to be certain about:

```python
import openpyxl
from openpyxl.utils import get_column_letter as col, range_boundaries
wb  = openpyxl.load_workbook("<spreadsheet_path>", data_only=True)   # stored values
wbf = openpyxl.load_workbook("<spreadsheet_path>")                   # formulas as written
for s in wb.worksheets:
    print(s.title, s.max_row, s.max_column)
ws, wsf = wb["<sheet>"], wbf["<sheet>"]
# The target cells: what is already there, and any formula that documents the intent.
# Print every NON-EMPTY one when there are up to ~300 — finished examples often sit far down.
c1, r1, c2, r2 = range_boundaries("<answer_position range>")    # works for "B7", "B2:D9", "C:C"
r1, r2 = r1 or 1, r2 or ws.max_row
cells = [f"{{col(c)}}{{r}}" for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)]
for addr in (cells if len(cells) <= 300 else cells[:20] + cells[-10:]):
    if ws[addr].value is not None or wsf[addr].value is not None:
        print(addr, repr(ws[addr].value), type(ws[addr].value).__name__, "| formula:", repr(wsf[addr].value))
print(len(cells), "target cells,", sum(ws[a].value is not None for a in cells), "already filled")
# The neighbours that define the computation: headers, axis labels, key columns.
for r in range(1, 12):
    print(r, [ws.cell(r, c).value for c in range(1, 13)])
```

Then state, in a comment, the reading you have settled on and the evidence for it — an existing
formula, an axis label, or an already-filled target cell your computation must reproduce. If two
readings of the instruction are possible, the one that matches the cells already in the file is
the right one. (For a multi-part answer_position such as `G4:G6, G11:G13`, run the target loop
once per part.)

When the task works over a set of columns or items ("from the first metric to the last one",
"every month"), build that list from the header row you printed — every entry between the end
points — never by retyping the names you happened to see.

**Phase 1b — CALIBRATE against a filled sibling column, when one exists (do not skip).** Look at
the columns and rows immediately *outside* `answer_position`, on the same rows or in the same
band as the target. When one of them is **already filled** and its header names the **same
quantity as the graded columns, at a different parameter** — `Open as of today` beside
`Open by end of May` / `… of Jun`; `Q1 total` beside `Q2 total`; `2023 count` beside `2024 count`
— that filled column is a **worked example of the function you are being asked to write**, and
the expected answer was produced by the same function at a different parameter. It is the one
oracle in the file that can tell you your reading is wrong *before* you are graded, so use it:

```python
def f(param):                        # your candidate reading, parameterised
    ...
# Reproduce the FILLED sibling column with the SAME function, then compare cell by cell.
got      = [f(sibling_param) for _ in target_rows]
expected = [ws.cell(r, sibling_col).value for r in target_rows]
print("calibration:", list(zip(expected, got)), "MATCH" if got == expected else "MISMATCH")
```

If it prints `MISMATCH`, your reading of the instruction is wrong — **fix the function before you
write anything**. Do not proceed because the numbers look close or differ on only a few rows: the
sibling column and the graded columns are computed the same way, so a function that cannot
reproduce the one you can check will not match the ones you cannot.

This matters most when the instruction's prose and the graded column's **header** describe
different computations. A paraphrase like "open if it was not closed before the first day of the
month and not created after the last day" describes an **overlap with the period**; a header
reading "open by the end of <month>" describes a **snapshot at that boundary** — a strictly
smaller set, because overlap also counts records that had already left the state. When prose and
header disagree, the calibration column settles it, and it is what the expected answer was built
from. Prefer the reading that reproduces it over the reading the prose suggests.

**Phase 2 — WRITE.** Compute every value in Python, assign the literals, and save to
`output_path`. In the **same** block, re-open the file you just saved and print the graded cells:

```python
# READ input values from `src` (data_only=True: cached values, never formula strings).
# WRITE into `wb` (loaded WITHOUT data_only: saving a data_only workbook replaces every
# other formula in the file with its cached value). Never compute from `wb`'s cells — there a
# formula cell reads as the string "=..." and every comparison/lookup on it silently fails.
src = openpyxl.load_workbook("<spreadsheet_path>", data_only=True)
wb  = openpyxl.load_workbook("<spreadsheet_path>")
ss, ws = src["<sheet>"], wb["<sheet>"]
# ... compute from ss, assign your computed literal values to ws's target cells ...
# A target cell you did not assign that still holds a formula would read back EMPTY:
# replace it with its value (ss's cached value, or recompute it if it depends on cells you changed).
for row in ws["<answer_position range>"]:
    for c in row:
        if isinstance(c.value, str) and c.value.startswith("="):
            c.value = ss[c.coordinate].value
wb.save(output_path)

chk = openpyxl.load_workbook(output_path, data_only=True)     # exactly what the grader sees
for addr in ["<cells of answer_position — sample ~20 if the range is large>"]:
    v = chk["<sheet>"][addr].value
    print(addr, repr(v), type(v).__name__, "| was:", repr(ss[addr].value))
from openpyxl.utils import get_column_letter as col, range_boundaries
c1, r1, c2, r2 = range_boundaries("<answer_position range>")
r1, r2 = r1 or 1, r2 or ss.max_row
cells = [f"{{col(c)}}{{r}}" for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)]
print(sum(ss[a].value != chk["<sheet>"][a].value for a in cells), "of", len(cells), "graded cells changed")
```

If that last line reads **`0 of N graded cells changed`**, your output is the input unchanged —
the expected answer almost never is, so your reading is almost certainly wrong. Usually a condition
was matched too strictly (e.g. a "blank row" is blank in the column the instruction is about, the
key/name column, not necessarily across every column), or the writes went to another sheet or
range. Re-read the instruction against the cells and revise the condition.

If any input value you compute from prints as a string starting with `=`, you read the wrong
workbook — read it from `src`.

For a range of hundreds or thousands of cells, print a summary instead of every cell: how many
are non-empty, the set of types present, how many start with `=`, how many are error markers, and
the first and last few values.

**Phase 3 — VERIFY, then stop.** Read that output and check each item:

- no value is a string starting with `=`, and none is `#N/A` / `#VALUE!` / `#DIV/0!` / `#NUM!`;
- no cell is `None` where the answer should have a value;
- every number is `int`/`float`, not `str`; every date is a `datetime`;
- any target cell the instruction did not ask you to change or clear still shows its `was:` value
  (if the task *is* to clear cells, the cleared ones should read `None` — that is correct);
- the values reproduce the worked example already in the sheet, and are the right magnitude;
- every target cell you left `None` on purpose ("blank when not found") belongs to a key that
  truly **missed** — a key that was found with a genuine `0` keeps the `0`.

If every check passes, you are done: reply with a short plain-text confirmation and **no code
block**. Do not re-send working code — a resubmission of the same block changes nothing.

If a check fails, diagnose the cause and repeat Phase 2. Change the computation, not just its
formatting: re-sending near-identical code is the single most common way a task is failed here. If
the same check fails twice, your reading of the instruction is what is wrong — go back to the
sheet, print the cells that ought to settle it, and revise the reading rather than the code.
If the block you are about to send would be the same as your previous one, do not send it: either
stop (plain text, no code) or send a block that only **prints** the `repr()` and type of the inputs
your failing condition reads — that is usually where the bug is (a `str` vs a number, a trailing
space, different case, a formula string).
