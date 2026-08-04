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
You need to solve the following spreadsheet manipulation question. It contains six pieces of information:
- instruction: the question about spreadsheet manipulation.
- spreadsheet_path: the path of the spreadsheet file you need to manipulate.
- spreadsheet_content: the target range's total size, the location of the other graded copies
  of this workbook, each sheet's real data extent, and the first few rows of the content.
- instruction_type: Cell-Level Manipulation (answer_position is exact cell(s)) or Sheet-Level Manipulation (answer_position is the maximum range you may modify).
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

### how your answer is graded (read before writing code)
Your FINAL code block is re-run UNCHANGED on three copies of this workbook whose data
differs; each output is graded cell-by-cell against a reference answer, comparing BOTH the
value AND the type. Only copy 1 is previewed above; the other two copies are already on disk
(paths in spreadsheet_content). Read and write using the exact spreadsheet_path and
output_path strings given above — the re-run substitutes the filenames — so never glob for
files or build paths from a copy number. In an EARLY turn you may open all three input copies
to confirm your logic generalizes; the final block itself must read only the one
spreadsheet_path.

Match the expected TYPE and format of each answer cell:
- If the target range already contains a worked-example cell, replicate its exact per-column
  type and formatting — text stays text, a real date stays a date, a number stays a number —
  and preserve any leading/trailing spaces the source keeps (do not strip them).
- If the instruction names the form a result may take (e.g. "the result may be #N/A" or the
  "output result may be '-'"), write that exact literal for those cases, not a numeric
  placeholder such as 0.
- Rich-text and conditional-formatting cells are themselves the graded answer — preserve the
  CellRichText / cell formatting, and never flatten them to a plain string.

Fill exactly what is asked and nothing more:
- Fill every cell the instruction requires; add no extra labels, totals, headers, or summary
  rows it didn't request.
- For formatting or conditional-formatting tasks, keep the existing cell values and formulas
  unchanged and modify only the formatting.

You have up to {max_turns} rounds of interaction. In each round, reply with exactly ONE python code block:
1. Information-gathering code (e.g. inspecting the file, or all three input copies) — the execution result is returned to you.
2. Solution code that writes the modified file to output_path.
3. Verification code: re-open output_path and print, for each cell in answer_position, its
   value and its python type. Confirm every cell the task requires is filled with the intended
   value in a matching type (a rich-text or formatting answer keeps its special type, not a
   plain string), and that no cell you meant to fill is unexpectedly None. If anything is
   wrong, fix your code and write again.
Reply without a code block when you are satisfied the saved file is correct.
If your code raises an error, the traceback will be returned to you; fix the code and try again.
