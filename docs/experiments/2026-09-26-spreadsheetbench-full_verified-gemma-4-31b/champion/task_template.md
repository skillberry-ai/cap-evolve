<!--
  THE AGENT'S JOB DESCRIPTION — editable capability text, same as prompt.md.

  Everything below is sent to the agent as its first user message, so it is part of the
  skill you are optimizing: reword it, restructure it, add or remove guidance, change the
  interaction contract. This comment block is STRIPPED before the agent sees it.

  LOAD-BEARING PLACEHOLDERS — these are filled in per task and must SURVIVE any edit:
    {instruction} {spreadsheet_path} {spreadsheet_content} {instruction_type}
    {answer_position} {output_path}
  Optional: {max_turns}. No other {braces} are allowed.

  If a required placeholder goes missing, or an unknown one appears, the candidate is
  REJECTED before any task runs — the agent would otherwise be told to write its answer to
  a path it was never given. A literal brace must be doubled: {{ or }}.
-->
Solve the following spreadsheet manipulation question.

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

## What these fields mean

- **instruction** — the change to make. Read it to the end: a clause about how to treat duplicates,
  which rows pair up, or what precision to use is part of the requirement, not commentary. It was
  written by a spreadsheet user describing their own file, so it names things loosely: the range it
  quotes may be narrower than the data, a criterion it quotes in lowercase may be capitalised in the
  cells, and a tool it asks for (VBA, a specific formula) is a preference about method, never a
  requirement — you are graded only on the resulting cell values, so solve it whichever way is
  reliable in Python.
- **spreadsheet_path** — the input workbook. Read it; never modify it in place.
- **spreadsheet_content** — the target range's size, each sheet's real data extent, and a pandas
  preview of the first rows. In that preview the leftmost column is a 0-based pandas index and row 1
  of the sheet was consumed as the header, so **preview row `i` is Excel row `i + 2`**, and pandas
  column position `j` is Excel column `j + 1`. Columns shown as `Unnamed: N` are real columns whose
  header cell is blank — not columns to skip. The preview shows only the first rows; the stated data
  extent covers the cells that hold something, and neither is a promise about where a calculation
  should stop. Derive your own ranges from the cells you print.
- **instruction_type** — `Cell-Level Manipulation`: answer_position is the exact cell(s).
  `Sheet-Level Manipulation`: answer_position is the MAXIMUM range you may modify.
- **answer_position** — the only cells you may change. Every cell in it is graded, including the
  ones the instruction does not ask about: those must still hold their original value.
- **output_path** — write the finished workbook here, at exactly this path, creating parent
  directories if needed.

## Read the inputs before you compute anything

Two loads, two purposes — one for the values you compute FROM, one for the file you save:

```python
import os, openpyxl
IN  = "{spreadsheet_path}"
OUT = "{output_path}"
SHEET = "SheetNameFromAnswerPosition"    # or wb.sheetnames[0] if answer_position names no sheet

wb  = openpyxl.load_workbook(IN)                     # edit and save THIS one
ws  = wb[SHEET]
wsv = openpyxl.load_workbook(IN, data_only=True)[SHEET]   # read numbers from THIS one

for a1 in ["C5", "H2", "E31"]:           # every cell you will read, key off, or anchor to
    print(a1, "formula:", repr(ws[a1].value), "| value:", repr(wsv[a1].value))
```

`ws[a1].value` returns a cell's formula as TEXT — `'=SUM(C5)/(C19+C20)'`, not a number. Anything you
derive from that string is wrong from the start. The computed number lives in the `data_only` copy.
Never save the `data_only` workbook: doing so freezes every other formula in the file into a static
number.

Before writing any `==` test, print what the column actually contains:

```python
vals = [wsv[f"G{{r}}"].value for r in range(2, 40)]
print("distinct:", sorted({{(repr(v), type(v).__name__) for v in vals}})[:20])
```

Years, ids and codes are stored as numbers in one column and as text in another, so `2014 == '2014'`
is False; text criteria differ in case and trailing spaces. Compare both sides normalised —
`str(a).strip().lower() == str(b).strip().lower()` — and note that `''` is a present, empty value
(zero in a numeric column), not a failed lookup.

## How to produce the output file

The output must be the INPUT workbook with the required cells changed — same sheets, same sheet
names, everything else untouched:

```python
os.makedirs(os.path.dirname(OUT), exist_ok=True)
ws["F2"] = 42                        # assign ONLY the cells the instruction asks for
wb.save(OUT)
```

You may use pandas to READ and compute. Do not use `DataFrame.to_excel` or `pd.ExcelWriter` to
produce output_path: that rebuilds the file from the frame rather than editing the original, which
renames the sheet (the grader then finds no sheet by that name and scores 0), drops the other
sheets, changes cell types, and blanks every cell pandas parsed as `NaN` — including cells whose
correct answer was their own original content. If you do read with pandas, prefer
`pd.read_excel(path, header=None, dtype=object, keep_default_na=False)` so literal text such as
`NA`, `None` or `-` is not silently turned into a blank.

For a structural change (deleting, inserting, or moving rows/columns) use openpyxl's
`ws.delete_cols`, `ws.insert_rows` and friends on the loaded workbook, not a pandas round-trip.

## The interaction contract

You have up to {max_turns} rounds. Each reply is exactly ONE ```python fenced code block — nothing
outside the fence, and no other block. Work in this order:

1. **READ** — print, with `repr()` and type, every cell you will read from, key off, or anchor to,
   plus the distinct values of any column you will filter on. Print the cells of answer_position as
   they arrive: any that already hold a value are a worked example of the intended answer, your rule
   must reproduce them, and that same rule then has to keep running over the cells that are still
   empty.
2. **DECIDE** — the instruction will be loose somewhere. Write both readings as code, score each one
   against a number the file already fixes (a pre-filled target cell, a cached formula result, a
   total the sheet holds), print both scores, and keep the reading that reproduces it. Do not settle
   it in a comment: "usually", "probably", "a bit ambiguous", "I'll assume" and "fallback" are each a
   guess you have not tested, and the file can answer the question. Anything depending on a calendar
   (days in a month, weekdays, a year fraction) depends on the year, and the year is in the sheet —
   read it and use `calendar.monthrange(year, month)[1]` rather than a literal 28, 30, 31 or 365.
3. **SOLVE** — compute the values and save the workbook to output_path.
4. **CHECK** — re-open the SAVED file and verify it, addressing cells by literal A1 names rather
   than by the indices you wrote with. Confirm: the sheet is present under its original name; no
   target cell is unintentionally empty; the set of cells whose value changed versus the input is
   exactly the set the instruction asked you to compute; and at least one written value agrees with
   a figure you did not compute yourself — a cached formula result elsewhere in the sheet, a
   pre-filled cell of the target range, or a total the sheet already contains.

An output file existing is NOT being done, and neither is a check that prints the right SHAPE — the
expected count of non-empty cells, all of the right type — on wrong values. That is the most common
way this task is now failed. You are done when the CHECK output is all-clear; reply then with no code
block, and that ends the task. If the CHECK shows a problem, the next block must be diagnostic (print
the source cells with `repr()` and their types, and the intermediate lookups) and then a corrected
write — never the same block again, and never a narrower write that simply stops touching the cells
that came out wrong. A correction fixes the rule, never which cells the rule is responsible for — and
a cell you leave alone is still graded, as a claim that its original contents were the expected
answer. If your code raises an error, the traceback comes back to you; fix it rather
than re-running it unchanged.
