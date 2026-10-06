<!-- cap-evolve task template. Required placeholders: {instruction} {spreadsheet_path} {spreadsheet_content} {instruction_type} {answer_position} {output_path}; optional {max_turns}. Literal braces must be doubled. This comment is stripped before the agent sees the message. -->
Solve the following spreadsheet manipulation task. It has six parts:
- instruction: what the user wants done.
- spreadsheet_path: the input workbook.
- spreadsheet_content: a preview of the first few rows of each sheet. Column names are pandas headers, so "Unnamed: N" means the real header is not in row 1. The preview's row index is NOT the Excel row number.
- instruction_type: either "Cell-Level Manipulation", meaning answer_position lists the exact cells to fill, or "Sheet-Level Manipulation", meaning answer_position is the largest range you may change.
- answer_position: the cells that are graded. With no sheet prefix, it refers to the first sheet.
- output_path: where the modified workbook must be saved.

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

### How to work
You have up to {max_turns} rounds. In each round, reply with exactly ONE ```python code block. Its output (or traceback) comes back to you. Follow these steps in order:

1. **Inspect.** Open the input with openpyxl and print the real cells, coordinate by coordinate, for:
   - the header and label rows above and beside answer_position;
   - the first data rows of the source columns;
   - the current contents of answer_position, including any pre-filled example answers;
   - `ws.max_row` and `ws.max_column`.
   
   Decide exactly which Excel rows and columns hold the data and what each answer cell means.
2. **Solve.** Load with `openpyxl.load_workbook(spreadsheet_path, data_only=True)` and compute every answer in Python. Even if the instruction asks for a formula or VBA, compute the RESULT. Then:
   - write only literal values (number, text, datetime) into the cells of answer_position, at their exact Excel coordinates;
   - never write a string starting with "=";
   - leave all other cells untouched;
   - save with `wb.save(output_path)`.
   
   Your computed values must reproduce any example answers already present.
3. **Verify.** Reopen output_path with `data_only=True` and print the values in answer_position. Check that:
   - no expected value is None;
   - nothing is a formula string or an error text;
   - numbers are numbers;
   - the examples still match.
   
   If anything is wrong, fix the code and save again.
4. **Finish.** When the verification output is correct, reply with a one-line confirmation and NO code block. That ends the task. Do not repeat code that has already run successfully.
