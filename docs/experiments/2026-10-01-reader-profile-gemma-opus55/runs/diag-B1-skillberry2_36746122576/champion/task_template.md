<!--
  THE AGENT'S JOB DESCRIPTION — editable capability text. Sent as the first user message;
  this comment is stripped. Required placeholders: {instruction} {spreadsheet_path}
  {spreadsheet_content} {instruction_type} {answer_position} {output_path}; optional {max_turns}.
  A literal brace must be doubled.
-->
You need to solve the following spreadsheet manipulation question. It contains six pieces of information:
- instruction: the question about spreadsheet manipulation.
- spreadsheet_path: the path of the spreadsheet file you need to manipulate.
- spreadsheet_content: the target range's size, each sheet's real data extent, and the first few rows of the content (a pandas preview — its index 0 is Excel row 2).
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

You have up to {max_turns} rounds of interaction. In each round, reply with exactly ONE python code block; its execution result (or traceback) is returned to you. Work in this order:
1. Inspect: open the file with openpyxl and print, with real cell addresses, the headers, the labels next to answer_position, the current contents of answer_position (values and any formulas), and any example rows/blocks the instruction refers to. Print what you need — the result only helps you if it is printed.
2. Solve: compute every answer in Python from the data in the file, write the literal values into answer_position only (openpyxl, load → set cells → save), and save to output_path.
3. Verify: re-open output_path with openpyxl and print every cell of answer_position. Check that no cell is empty, a formula string, or an error text where a value belongs, that types are right, and that any pre-filled example cells still match. If something is wrong, fix it and save again.
4. Finish: once the verified file is correct, reply with a short plain-text summary and no code block — that ends the task. Resending the same code does not help.
