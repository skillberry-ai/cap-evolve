You need to solve the following spreadsheet manipulation question. It contains six pieces of information:
- instruction: the question about spreadsheet manipulation.
- spreadsheet_path: the path of the spreadsheet file you need to manipulate.
- spreadsheet_content: the first few rows of the spreadsheet (a preview only — the real data may be longer).
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

You have up to {max_turns} rounds of interaction. In each round, reply with exactly ONE python code block. Work in this order:
1. Inspect: open the file with openpyxl (and a data_only=True copy) and print the sheet names, sizes, header rows, the rows around answer_position and any values already present in answer_position — those are examples of the expected answer.
2. Solve: compute every answer in Python and write LITERAL VALUES (never formulas, never strings starting with "=") into the answer_position cells of the original workbook loaded with openpyxl, then save to output_path. Even if the instruction asks for a formula or VBA, write the values it would produce.
3. Verify: in the same code, re-open output_path with openpyxl data_only=True and print every answer_position cell. Check the values are complete, correctly typed and reproduce the examples; if not, fix and rewrite.
4. Finish: when the printed values are correct, reply with plain text and no code block.
If your code raises an error, the traceback will be returned to you; fix the code and try again. Do not resend identical code.
