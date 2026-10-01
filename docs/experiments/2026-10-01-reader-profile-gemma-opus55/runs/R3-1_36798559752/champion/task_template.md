<!-- Placeholder contract: instruction, spreadsheet_path, spreadsheet_content, instruction_type, answer_position, output_path are required; max_turns is optional. Literal braces must be doubled. -->
Solve the following spreadsheet manipulation task. It has six pieces of information:
- instruction: what the user wants done to the spreadsheet.
- spreadsheet_path: the input workbook to read.
- spreadsheet_content: a short pandas preview of each sheet. Its row index is NOT the Excel row number, and it shows only the first rows, so read the real cells with openpyxl before deciding which rows and columns to use.
- instruction_type: Cell-Level Manipulation (answer_position lists the exact cells to fill) or Sheet-Level Manipulation (answer_position is the largest range you may change; it is compared cell by cell, so cells must land at their exact coordinates).
- answer_position: the cells that are graded. Only these should change.
- output_path: save the modified workbook to this exact path.

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

You have up to {max_turns} rounds. In each round, reply with exactly ONE python code block (only the first block of a reply is executed); its output (or traceback) is returned to you.
1. Inspect: run the dump script from your instructions on spreadsheet_path, then print any rows it cut off that you need (around answer_position and any example or expected-result block).
2. Specify: list the cells that already show desired results (pre-filled answers, expected-result blocks, neighbouring formula columns, marker numbers) and the row/column labels beside answer_position; note any start cell the instruction names ("from D4", "starting at") and whether it asks to append below existing rows; decide your rule from them.
3. Solve: compute every answer in Python, check it against those example cells (for an expected-result block, run the rule on that block's own source rows and print coordinate, computed, expected for every cell; change the rule until all match), write the literal values (numbers as int/float, dates as datetime, not formula strings) into the original workbook loaded with openpyxl, replace any formula left inside answer_position by its value, and save to output_path.
4. Verify: reload output_path with `data_only=True` and print each answer cell with its type; fix and re-save if any cell is empty, a formula string, an error, the wrong type, or inconsistent with the sheet's examples.
5. When the verified file is correct, or when your verify output repeats the previous round's, reply with plain text (e.g. DONE) and no code block to finish.
