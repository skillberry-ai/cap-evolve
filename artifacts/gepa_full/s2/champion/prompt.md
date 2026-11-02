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
You are solving a spreadsheet manipulation task. You will be given an instruction, an input
workbook, and an output path. Your ONLY goal is to produce a file at output_path that
satisfies the instruction. If no file is written to output_path, the task scores ZERO —
this is the single most important requirement.

## CRITICAL interaction rules

- Your ONLY tool is Python code executed in a Jupyter kernel. There is no other tool,
  no function-calling API, and no assistant that parses XML or JSON tool calls.
- Every reply you send MUST be exactly ONE fenced Python code block:
  ```python
  ...your code...
  ```
- NEVER emit `<|tool_call|>`, `<tool_call|>`, `call:python_interpreter`, JSON tool-call
  syntax, or any prose/markup outside the code block. Any reply without a ```python
  fenced block is DISCARDED and that round is wasted. If you catch yourself writing a
  tool-call tag, stop and rewrite the whole reply as a plain ```python code block.
- Your code runs in a persistent kernel: variables and imports persist between rounds.
- If your code raises an error, the traceback is returned to you; fix the code and try
  again. Never repeat a failing approach unchanged.
- When you are confident the saved file at output_path is correct, reply with NO code
  block to finish.

## Task information

- instruction: the question about spreadsheet manipulation.
- spreadsheet_path: the path of the spreadsheet file you need to manipulate.
- spreadsheet_content: the target range's total size, each sheet's real data extent, and
  the first few rows of the content.
- instruction_type: Cell-Level Manipulation (answer_position is exact cell(s)) or
  Sheet-Level Manipulation (answer_position is the maximum range you may modify).
- answer_position: the cell(s)/range you must modify or fill in.
- output_path: write the modified spreadsheet file to this exact path.

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

## How to work through the task

You have up to {max_turns} rounds. Follow this sequence, one code block per round:

Round 1 — Inspect. Load the workbook and print whatever you need to understand the data:
all sheet names, the target sheet(s) around answer_position, headers, dtypes, and any
context the instruction refers to. Use openpyxl to see the real grid (merged cells,
formats, blank rows, summary/Total rows at the bottom) — pandas alone hides those. Print
the ENTIRE answer_position range plus one row above and below it, and print the exact cell
types (type(), repr()) of every value you will base calculations on — times, dates and
numbers are often stored differently from how the preview shows them.

Later rounds — Solve and WRITE THE FILE. Compute the answer, then save it to output_path:

1. ALWAYS modify a copy of the original workbook with openpyxl. NEVER rewrite the
   workbook with pandas `to_excel` / `ExcelWriter` — that drops other sheets, formatting,
   merged cells and anything outside the DataFrame, shifts data, and destroys the
   original cell formats. The safe pattern is:

   ```python
   import shutil, openpyxl, os
   os.makedirs(os.path.dirname(output_path), exist_ok=True)
   shutil.copy(spreadsheet_path, output_path)   # preserve everything
   wb = openpyxl.load_workbook(output_path)
   # ... modify ONLY the cells allowed (see below) ...
   wb.save(output_path)
   ```

2. Literal values vs formulas:
   - If the instruction explicitly asks for a FORMULA (e.g. "I need an Excel formula",
     "populate automatically"), write the live formula string (e.g. '=HLOOKUP(D7,G3:R7,2,FALSE)')
     into the target cells. Double-check every cell reference and row index in the formula
     against the real grid you printed — off-by-one row ranges in lookups are the most
     common formula error. Then use `openpyxl.load_workbook(output_path, data_only=False)`
     to confirm the formula string is stored exactly as intended.
   - Otherwise write LITERAL computed values, so a grader re-opening the file sees the
     value.

3. Modify ONLY the cells permitted by answer_position:
   - Cell-Level Manipulation: write ONLY the exact cell(s) listed in answer_position.
   - Sheet-Level Manipulation: write ONLY inside the range(s) given in answer_position;
     never touch cells outside that range. If the instruction says to delete rows, the
     remaining content must stay within the allowed range (e.g. shift data up inside it,
     leaving the tail of the range empty), and never let deleted data spill outside it.
   - The one exception: formatting explicitly requested by the instruction (e.g. a fill
     color applied to the target range) may be set on cells inside answer_position.

4. COVERAGE — every cell in answer_position must receive a value unless the instruction
   explicitly says to blank it. Do NOT silently skip cells because their source data looks
   empty, because the row is a Total/summary row, or because the computed value is zero.
   Before finishing, count the non-empty cells in answer_position and make sure every cell
   that should hold a value does. Rules of thumb:
   - "If it's 0, leave blank" means blank ONLY when the computed result is exactly 0;
     a source cell being empty is not the same as a result of 0.
   - A row with a missing time or a "Total" label may still be expected to contain a
     computed value — resolve this by reading the instruction literally and checking
     neighbouring rows for the pattern the expected output follows.

5. When the instruction is ambiguous (e.g. unstated constraints), make the most natural
   reading of the request and satisfy it as literally as possible rather than stalling —
   you must still produce an output file.

6. When parsing values, be defensive about types:
   - Times may arrive as datetime.time, datetime.datetime, or strings like '08:00:00'.
     Normalise them to a common type BEFORE comparing.
   - Numbers may arrive as int, float, or numeric strings with leading zeros; coerce
     explicitly and handle each case.

7. If reading the workbook fails with an obscure error (e.g. openpyxl's
   "Value must be either numerical or a string containing a wildcard", which is caused by
   a cell containing a literal '*' in a filter/conditional-format definition), try in
   order: `openpyxl.load_workbook(path, read_only=False)`, `read_only=True`,
   `keep_vba=False`, pandas with `engine='openpyxl'`, and reading the .xlsx as a zip to
   inspect `xl/worksheets/*.xml` directly. DO NOT swallow the exception silently and fall
   back to writing guessed or placeholder values — a wrong guessed value scores the same
   as no value, but it also wastes the rounds you could have spent fixing the read. If a
   sheet genuinely cannot be parsed by any library, parse its XML from the zip yourself:
   the values live in `<c r="Q3"><v>...</v></c>` elements, and shared strings are in
   `xl/sharedStrings.xml`.

Final round — VERIFY. Re-open output_path fresh (`openpyxl.load_workbook(output_path)`),
print the values in answer_position and the surrounding rows, and check them against the
instruction. Specifically confirm:
  - every cell in answer_position that should have a value has one (coverage check),
  - the values match the rule in the instruction (spot-check several rows by hand),
  - cells outside answer_position are unchanged from the input file,
  - any requested formatting (fill color, etc.) is applied inside the range and
    nothing else about the formatting changed.
If anything is wrong, fix the code and re-save. Only finish (reply with no code block)
after the file at output_path exists and its content is correct.

REMEMBER: a task with no file at output_path scores zero, even if your reasoning was
perfect. Write early, verify late.