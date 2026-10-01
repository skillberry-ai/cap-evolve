Solve the following spreadsheet manipulation task. It has six parts:
- instruction: what the user wants done.
- spreadsheet_path: the input file to read.
- spreadsheet_content: a preview of the first rows of each sheet (row 1 is treated as the header, so check the real layout yourself).
- instruction_type: Cell-Level Manipulation (answer_position is the exact cell(s) to fill) or Sheet-Level Manipulation (answer_position is the maximum range you may modify).
- answer_position: the cell(s)/range that will be graded.
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

You have up to {max_turns} rounds. In each round, reply with exactly ONE python code block; its output (or traceback) is returned to you.
- Start by printing the actual cells around answer_position and any example or expected-result cells with openpyxl.
- Compute the answer in Python and write literal values (not formulas — they are not recalculated and would grade as empty) into the answer cells with openpyxl, then save to output_path.
- After saving, reopen output_path with `data_only=True` and print the answer cells to confirm they match the instruction and any examples.
- Once the printed result is correct, reply with a brief confirmation and no code block.
