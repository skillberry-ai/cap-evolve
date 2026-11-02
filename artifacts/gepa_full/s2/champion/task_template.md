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
formats, blank rows) — pandas alone hides those.

Later rounds — Solve and WRITE THE FILE. Compute the answer, then save it to output_path:

1. PREFER modifying a copy of the original workbook with openpyxl rather than rewriting
   the workbook with pandas `to_excel`. Rewriting with pandas drops other sheets,
   formatting, and anything outside the DataFrame, and shifts data — all of which fails
   grading. The safe pattern is:

   ```python
   import shutil, openpyxl, os
   os.makedirs(os.path.dirname(output_path), exist_ok=True)
   shutil.copy(spreadsheet_path, output_path)   # preserve everything
   wb = openpyxl.load_workbook(output_path)
   # ... modify ONLY the cells allowed (see below) ...
   wb.save(output_path)
   ```

2. Write LITERAL computed values into cells, not live formulas, unless the instruction
   explicitly asks for a formula. A grader re-opening the file must see the value.
3. Modify ONLY the cells permitted by answer_position:
   - Cell-Level Manipulation: write ONLY the exact cell(s) listed in answer_position.
   - Sheet-Level Manipulation: write ONLY inside the range(s) given in answer_position;
     never touch cells outside that range. If the instruction says to delete rows, the
     remaining content must stay within the allowed range (e.g. shift data up inside it,
     leaving the tail of the range empty), and never let deleted data spill outside it.
4. When the instruction is ambiguous (e.g. unstated constraints), make the most natural
   reading of the request and satisfy it as literally as possible rather than stalling —
   you must still produce an output file.

Final round — VERIFY. Re-open output_path (fresh: `openpyxl.load_workbook(output_path)`),
print the values in answer_position and the surrounding rows, and check them against the
instruction. If anything is wrong, fix the code and re-save. Only finish (reply with no
code block) after the file at output_path exists and its content is correct.

REMEMBER: a task with no file at output_path scores zero, even if your reasoning was
perfect. Write early, verify late.
`