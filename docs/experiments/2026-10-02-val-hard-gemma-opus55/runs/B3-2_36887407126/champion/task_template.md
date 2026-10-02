<!--
  Capability file: the agent's FIRST USER MESSAGE. Placeholders are filled in per task and are
  load-bearing — {instruction} {spreadsheet_path} {spreadsheet_content} {instruction_type}
  {answer_position} {output_path} must all survive; {max_turns} is optional. A literal brace is
  written {{ or }}. This comment is stripped before the agent sees the message.
-->
Solve the following spreadsheet manipulation task. It is described by six fields:

- **instruction** — what to do, written as a question from a spreadsheet user. It often asks for
  a formula or a macro; what is graded is the resulting cell **values** (see the CONTRACT below).
- **spreadsheet_path** — the input workbook. Read it; never modify it in place.
- **spreadsheet_content** — a `pandas.read_excel(...).head()` preview of each sheet, plus the
  sheet's true `[data extent]` and the size of the target range. The printed rows are a sample.
- **instruction_type** — `Cell-Level Manipulation`: `answer_position` is exactly the graded
  cells. `Sheet-Level Manipulation`: `answer_position` is the **maximum** range that is graded,
  and the expected answer often fills only part of it — the rest must be empty or unchanged.
- **answer_position** — the graded cell(s). It bounds *where* you may write; the instruction says
  *what* goes where. Do not spread your answer over the whole range just because it is bigger.
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
compares the **stored values** in `answer_position` with the expected workbook. It does not
recalculate formulas and does not read your prose.

1. Every graded cell holds a **literal computed value**, never a string beginning with `=` (a
   formula written by openpyxl reads back as empty) and never an error marker such as `#N/A`.
2. Values are **correctly typed**: numbers as `int`/`float`, dates as `datetime`, logicals as
   `True`/`False`, text as the exact string found in the workbook. Data you keep or move keeps
   its original type. Numbers are compared rounded to 2 decimals.
3. Every cell the expected answer fills is filled; every target cell the instruction does not ask
   you to change still holds its **original value**; nothing is written past where the answer ends.
4. Content the instruction never mentions — other sheets, other columns — is left as it was.

## HOW TO WORK — you have up to {max_turns} rounds

Each reply is **exactly one ```python fenced code block**. Its stdout is returned to you; if it
raises, you get the traceback. Work through three phases.

**Phase 1 — INSPECT (1–2 rounds).** Never write your answer from the preview alone. Print what
you need to be certain about:

```python
import openpyxl
wb  = openpyxl.load_workbook("<spreadsheet_path>", data_only=True)   # stored values
wbf = openpyxl.load_workbook("<spreadsheet_path>")                   # formulas as written
for s in wb.worksheets:
    print(s.title, s.max_row, s.max_column)
ws, wsf = wb["<sheet>"], wbf["<sheet>"]
# The target cells: what is already there, and any formula that documents the intent.
for addr in ["<cells of answer_position — the first ~20 are enough for a large range>"]:
    print(addr, repr(ws[addr].value), "| formula:", repr(wsf[addr].value))
# The neighbours that define the computation: headers, labels, key columns.
for r in range(1, 12):
    print(r, [ws.cell(r, c).value for c in range(1, 13)])
```

Then state in a comment the reading you settled on and its evidence: an existing formula, a
header, or an already-filled target cell your computation must reproduce. If a filled column
next to the target computes the same quantity for a different parameter (`Q1 total` beside the
`Q2 total` you must fill), compute that column with your function too and compare; a mismatch
means your reading is wrong — fix it before writing.

**Phase 2 — WRITE.** Compute every value in Python, assign the literals, save to `output_path`,
and in the **same** block re-open the saved file and print what the grader will see:

```python
wb = openpyxl.load_workbook("<spreadsheet_path>")      # fresh, WITHOUT data_only
ws = wb["<sheet>"]
# ... assign computed literal values to the target cells ...
wb.save("<output_path>")

chk = openpyxl.load_workbook("<output_path>", data_only=True)
src = openpyxl.load_workbook("<spreadsheet_path>", data_only=True)
for addr in ["<cells of answer_position — sample ~20 if the range is large>"]:
    v = chk["<sheet>"][addr].value
    print(addr, repr(v), type(v).__name__, "| was:", repr(src["<sheet>"][addr].value))
```

For a large range, print a summary instead: count of non-empty cells, the set of types, how many
start with `=` or `#`, and the first and last few values.

**Phase 3 — VERIFY, then stop.** Check the printout:

- no value starts with `=` or is an error marker; no `None` where a value belongs, and no value
  where the answer should end;
- numbers are `int`/`float`, dates `datetime`, kept text is still text;
- target cells the instruction did not ask to change still show their `was:` value, and your
  values reproduce any worked example in the sheet.

If every check passes, reply with one short plain-text sentence and **no code block** — that ends
the task. If a check fails, fix the cause and repeat Phase 2 with changed code; re-sending the
same block changes nothing. If the same check fails twice, revisit your reading of the
instruction rather than the code.
