<!--
  THE FIXED FRAME of the agent's first user message — SEALED, not part of the editable skill.

  It holds only what the harness depends on: the task fields (filled in per task) and the
  facts of the interaction loop. Your editable text goes in guidance.md, which is inserted
  at {guidance}. Everything about HOW the agent should work (inspection, verification,
  type rules, examples) belongs in guidance.md or prompt.md, not here.

  This comment is stripped before the agent sees the message.
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
{guidance}
### How this session works
You have up to {max_turns} rounds. In each round, reply with exactly ONE ```python fenced code block; only that block is run. The next message you receive is the real output (stdout) or traceback of that code — it never contains the expected answer.
You are graded on the file saved at output_path. Once that file is saved and correct, reply without a code block to finish.
