# Task
You are provided with a spreadsheet and an instruction to modify it.

## Inputs
- Spreadsheet Path: {spreadsheet_path}
- Spreadsheet Content: {spreadsheet_content}
- Instruction: {instruction}
- Instruction Type: {instruction_type}
- Target Answer Position: {answer_position}
- Output Path: {output_path}

## Requirements
1. Read the spreadsheet carefully.
2. Execute the requested manipulation precisely.
3. Write the final results to the output path.
4. Ensure that all answers are written as literal values, not as Excel formulas.
5. Do not modify any cells that are not explicitly requested to be changed.
6. Verify the values in the target range before finalizing. Ensure the range is fully populated where expected, that no cells outside the target range were modified, and that the data types (numbers, dates, strings) match the expected output exactly.

Your goal is to produce a spreadsheet that satisfies the instruction and matches the expected values in the target range.
