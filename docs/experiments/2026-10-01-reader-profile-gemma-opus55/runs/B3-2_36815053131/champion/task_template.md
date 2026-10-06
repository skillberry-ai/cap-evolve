You need to solve the following spreadsheet manipulation question. It contains six pieces of information:
- instruction: the question about spreadsheet manipulation, as a user of Excel would ask it.
- spreadsheet_path: the path of the spreadsheet file you need to manipulate.
- spreadsheet_content: a pandas preview of the first few rows. It can hide leading empty rows (the real header may be in row 2 or lower) and rename headers to "Unnamed: n", so inspect the real cells with openpyxl before relying on positions.
- instruction_type: Cell-Level Manipulation (answer_position is the exact cell(s) to fill) or Sheet-Level Manipulation (answer_position is the maximum range you may modify).
- answer_position: the cell(s)/range that will be checked. Each must end up holding the final computed VALUE (number or text), not a formula.
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

You have up to {max_turns} rounds of interaction. In each round, reply with exactly ONE python code block; its printed output (or traceback) is returned to you.
1. Inspect: print sheet names and the relevant cells with coordinates, showing both formula text and cached value (headers, a few data rows, the answer area and the rows just beyond it, and any example/expected values in the sheet or in the instruction).
2. Solve: compute the answer in Python and print it next to those examples; if any disagree, fix the logic first. Then load the original workbook with openpyxl, write the literal values into the answer_position cells only (starting where the instruction says, if it names a cell), and save to output_path. The file is graded as saved, without recalculation, so a formula string in an answer cell counts as empty.
3. Verify: reopen output_path with `openpyxl.load_workbook(output_path, data_only=True)` and print the answer_position values. If anything is None, a formula, an error, or inconsistent with the sheet's examples, fix it and save again. After the file exists you get only a few more rounds, so verify right away.
When the verified file is saved, reply with a short sentence and no code block to finish.
