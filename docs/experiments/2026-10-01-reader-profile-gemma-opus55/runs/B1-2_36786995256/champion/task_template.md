<!-- Per-task user message. Required placeholders: instruction, spreadsheet_path, spreadsheet_content, instruction_type, answer_position, output_path; optional: max_turns. Literal braces must be doubled. -->
Solve the following spreadsheet question by writing the answer into a copy of the workbook.

### instruction
{instruction}

### spreadsheet_path
{spreadsheet_path}

### spreadsheet_content (preview: the first rows of each sheet, read by pandas)
{spreadsheet_content}

### instruction_type
{instruction_type}
(Cell-Level Manipulation: answer_position is exactly the cells to fill. Sheet-Level Manipulation: answer_position is the largest range you may modify.)

### answer_position
{answer_position}

### output_path
{output_path}

## How to work
You have up to {max_turns} rounds. In each round reply with exactly ONE ```python code block; its printed output is returned to you. Keep each block self-contained: define the paths and load the workbook in it.

1. Inspect first (at least one round, no writing yet). With openpyxl, print the answer range and the rows and columns around it: values, formulas (plain load) and cached values (`data_only=True`), plus the header rows and labels that describe the target cells. Print any values already in the target range, since they are worked examples.
2. Decide the exact rule. Check it against every existing example value and every example in the instruction; if your rule does not reproduce them, revise it.
3. Compute the answers in Python and write literal values (no formulas) into the workbook loaded with `load_workbook(spreadsheet_path, data_only=True)`, changing only the cells the task requires. Save to output_path.
4. Verify: reopen output_path with `data_only=True` and print every cell of answer_position. Check that the values, types and positions are right and that no cell is a formula or an error. If something is wrong, fix it and save again.
5. When the verified output is correct, reply with a short message and no code block. That ends the task.

If your code raises an error, the traceback is returned to you; fix the cause rather than re-sending the same code. Print something in every block so each round tells you something new.
