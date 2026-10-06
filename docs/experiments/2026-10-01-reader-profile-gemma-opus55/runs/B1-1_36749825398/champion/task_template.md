<!-- cap-evolve task template. Required placeholders: {instruction} {spreadsheet_path} {spreadsheet_content} {instruction_type} {answer_position} {output_path}; optional {max_turns}. Literal braces must be doubled. This comment is stripped before the agent sees the message. -->
Solve the following spreadsheet question. You are given:
- instruction: the user's question, often written as a request for an Excel formula or macro. Deliver the resulting values in the cells.
- spreadsheet_path: the input workbook.
- spreadsheet_content: a pandas preview of the first few rows of each sheet. Its column labels are Excel row 1 and its row index 0 is Excel row 2. It can hide the real header row, blank rows and cells further down, so inspect the file itself.
- instruction_type: Cell-Level Manipulation (answer_position is the exact cells to fill) or Sheet-Level Manipulation (answer_position is the largest range you may change).
- answer_position: the cells that are graded. A reference without a sheet name refers to the first sheet.
- output_path: where to save the modified workbook, exactly as written.

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

You have up to {max_turns} rounds. In each round, reply with exactly ONE ```python code block; its output is returned to you. If it raises, you get the traceback: fix it and try again.
1. Inspect first: print the header rows, the answer range and its neighbours by Excel coordinate, including any example values already in the sheet.
2. Solve: one complete script that loads the input with openpyxl, computes the answers in Python, writes literal values (not formulas) into the answer cells only, and saves to output_path. The last script that writes the output is re-run on its own, so it must do the whole job from the input.
3. Verify: after saving, reload output_path with `data_only=True` and print each answer cell's value and type. If any is None, a formula string, an error or inconsistent with the examples, re-run the complete corrected script. You get at most 3 rounds after the first save that don't rewrite the file.
When the verified output is correct, reply with a short confirmation and no code block to finish.
