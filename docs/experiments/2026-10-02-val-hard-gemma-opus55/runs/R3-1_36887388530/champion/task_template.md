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

## HOW TO WORK — you have up to {max_turns} rounds

Each reply must be **exactly one ```python fenced code block** and nothing else. Its stdout is
returned to you; if it raises, you get the traceback and can fix it. Only the **first** block in a
reply is executed: any further blocks, and any "stdout:" or "output:" text you write predicting
what the code will print, are thrown away unseen. So end your reply at the closing fence and
reason only from the real output that comes back. Work through these three phases in order.

**Phase 1 — INSPECT (1–2 rounds; do not skip).** Never write your answer from the preview alone.
Load the input and `print` what you need to be certain about:

```python
import openpyxl
wb  = openpyxl.load_workbook("<spreadsheet_path>", data_only=True)   # stored values
wbf = openpyxl.load_workbook("<spreadsheet_path>")                   # formulas as written
for s in wb.worksheets:
    print(s.title, s.max_row, s.max_column)
ws, wsf = wb["<sheet>"], wbf["<sheet>"]
# The target cells: EVERY already-filled one (worked examples often sit at the END of the range),
# and any formula that documents the intent.
cells  = [c for row in wsf["<answer_position range>"] for c in row]
filled = [c for c in cells if c.value is not None]
print(len(cells), "target cells,", len(filled), "already filled")
for c in (filled[:40] + filled[-10:] if len(filled) > 50 else filled):
    v = ws[c.coordinate].value
    print(c.coordinate, repr(v), type(v).__name__, "| formula:", repr(c.value))
# The neighbours that define the computation: headers, axis labels, key columns.
for r in range(1, 12):
    print(r, [ws.cell(r, c).value for c in range(1, 13)])
```

Then state, in a comment, the reading you have settled on and the evidence for it — an existing
formula, an axis label, or an already-filled target cell your computation must reproduce. If two
readings of the instruction are possible, the one that matches the cells already in the file is
the right one.

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

**Phase 1c — TEST your function on the already-filled target cells (whenever Phase 1 found
any).** Write the computation as a function of the cell, run it on every filled target cell, and
compare its result with what the cell holds. Do this **before** you write anything:

```python
def f(r, c):                         # your computation for the target cell at row r, column c
    ...
for cell in filled:                  # `filled` from Phase 1
    have = ws[cell.coordinate].value
    mine = f(cell.row, cell.column)
    print(cell.coordinate, repr(have), repr(mine), "OK" if mine == have else "DIFF")
```

If the sheet also holds a **processed copy** of the input block (the same index or labels,
already transformed), run `f` on each raw input and compare the result with its processed twin
in the same way. A filled cell that is already its own output proves nothing; the raw→processed
pair does.

All `OK`: go on. A `DIFF` in substance (another number, extra characters such as brackets the
filled cell lacks) means your reading is wrong. Fix `f` and run this again. The only `DIFF`s
you may let stand are the two exceptions in the system prompt §2: a case- or space-only
difference where `f` builds the text straight from the workbook's own labels, and cells that use
a format other than the one the instruction quotes. Name which one applies in a comment.

**Phase 2 — WRITE.** Compute every value in Python, assign the literals, and save to
`output_path`. In the **same** block, re-open the file you just saved and print the graded cells:

```python
# TWO loads, two jobs. READ every input value from `vs` (data_only=True). WRITE into `ws` and save
# `wb` (no data_only — saving a data_only workbook turns every other formula in the file into a
# literal). Never read inputs from `ws`: a formula cell there is the string "=A2+1", not its value,
# so dates/numbers computed by formulas silently drop out and your answer comes back empty or short.
src = openpyxl.load_workbook("<spreadsheet_path>", data_only=True)
wb  = openpyxl.load_workbook("<spreadsheet_path>")
vs, ws = src["<sheet>"], wb["<sheet>"]
# ... compute from vs, assign your computed literal values: ws["C2"] = value ...

# Any formula still inside answer_position reads back EMPTY after saving — including cells the
# instruction never named (a total/average row, a helper column). Each one needs its literal
# value (computed AFTER your new values, if it depends on them) or None.
left = [c.coordinate for row in ws["<answer_position range>"] for c in row
        if (isinstance(c.value, str) and c.value.startswith("=")) or type(c.value).__name__ == "ArrayFormula"]
print("formula cells still in answer_position (must be []):", left)

# SPELLING — every text you wrote, against the workbook's own strings: data cells outside the
# target, plus the "..." literals inside formulas. A near-twin (case / space / plural only) means
# you retyped a label from the instruction. Write the workbook's string instead. (Ignore it only
# when the instruction itself asks you to change case or spacing: "uppercase", "trim", "proper case".)
import re
tgt  = set(c.coordinate for row in ws["<answer_position range>"] for c in row)
norm = lambda t: re.sub(r"\s+", "", t).lower().rstrip("s")
twin = dict()
for s_ in src.worksheets:
    for row in s_.iter_rows():
        for c in row:
            if isinstance(c.value, str) and not (s_.title == ws.title and c.coordinate in tgt):
                twin.setdefault(norm(c.value), set()).add(c.value)
for s_ in openpyxl.load_workbook("<spreadsheet_path>").worksheets:
    for row in s_.iter_rows(values_only=True):
        for v in row:
            if isinstance(v, str) and v.startswith("="):
                for lit in re.findall(r'"([^"]+)"', v):
                    twin.setdefault(norm(lit), set()).add(lit)
old = src[ws.title] if ws.title in src.sheetnames else None
for a in sorted(tgt):
    v = ws[a].value
    if old is not None and v == old[a].value:
        continue                          # an input value you kept — not one you typed
    if isinstance(v, str) and v.strip() and v not in twin.get(norm(v), [v]):
        print("SPELLING:", a, repr(v), "-> workbook spells it", twin[norm(v)])

wb.save(output_path)

chk = openpyxl.load_workbook(output_path, data_only=True)     # exactly what the grader sees
for addr in ["<cells of answer_position — sample ~20 if the range is large>"]:
    v = chk["<sheet>"][addr].value
    print(addr, repr(v), type(v).__name__, "| was:", repr(vs[addr].value))
```

If `left` is not `[]`, write those cells and run Phase 2 again before you verify. Never wrap
cell arithmetic in `try/except: pass` — a value that raises is one you read wrongly (usually a
formula string from `ws`); print its `repr()` and fix the read instead of skipping it.

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
- the output shows the `formula cells still in answer_position (must be []): []` line and no
  `SPELLING:` line. If you skipped those template lines, your check is incomplete: run them.

If every check passes, you are done: reply with a short plain-text confirmation and **no code
block**. Do not re-send working code — a resubmission of the same block changes nothing.

If a check fails, diagnose the cause and repeat Phase 2. Change the computation, not just its
formatting: re-sending near-identical code is the single most common way a task is failed here.
If your summary shows **0 non-empty** cells (or far fewer than expected), do not re-send: print
`repr()` and `type()` of the source values your loop actually tested — a `str` like `'=A2+1'` where
you expected a date or number means you read from the formula workbook instead of `vs`. If
the same check fails twice, your reading of the instruction is what is wrong — go back to the
sheet, print the cells that ought to settle it, and revise the reading rather than the code.
