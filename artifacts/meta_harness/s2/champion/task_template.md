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

You have up to {max_turns} rounds of interaction. In each round, reply with exactly ONE python code block:
(Each reply must be only that one ```python fenced block — no tool-call markers such as `<|tool_call|>` or `call:skills...{{}}`, and no other text before or after the block.)
1. Information-gathering code (e.g. inspecting the file) — the execution result is returned to you.
2. Solution code that writes the modified file to output_path.
3. Verification code: re-open output_path and print the values you wrote in answer_position,
   to confirm they are correct before finishing. If they are wrong, fix your code and write again.
Reply without a code block when you are satisfied the saved file is correct (at most a one-line statement and no code block).
If your code raises an error, the traceback will be returned to you; fix the code and try again.

Termination / print rules:
- Every code block must print something informative before it ends — never end a block silently.
- The block that saves the output file must, in the same block, re-open it, print every value now in answer_position, and print how many cells in that range are still empty.
- Never resend a code block identical or near-identical to a previous one; if the last execution succeeded but printed nothing, print a verification instead of repeating it.
- As soon as the printed target-range values look correct, finish immediately by replying without a code block.
