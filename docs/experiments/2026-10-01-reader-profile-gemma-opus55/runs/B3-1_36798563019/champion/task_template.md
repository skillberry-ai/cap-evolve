<!-- Placeholder contract: keep {instruction} {spreadsheet_path} {spreadsheet_content} {instruction_type} {answer_position} {output_path}; {max_turns} optional; literal braces doubled. This comment is stripped before the agent sees the text. -->
Solve the following spreadsheet task. You get six pieces of information:
- instruction: what the user wants. It is often phrased as "write a formula / macro for…". What gets graded is the resulting cell values, so compute them in Python and write literal values.
- spreadsheet_path: the input workbook.
- spreadsheet_content: a truncated preview of the first rows of each sheet. Read the file itself for the full data.
- instruction_type: Cell-Level Manipulation (answer_position is the exact cell(s) to fill) or Sheet-Level Manipulation (answer_position is the maximum range you may modify).
- answer_position: the cell(s)/range that are graded. A sheet name in it ('Sheet'!A1:B5) is the sheet to write on.
- output_path: save the modified workbook to exactly this path.

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

You have up to {max_turns} rounds. In each round, reply with exactly ONE python code block and end your reply there. The next message you receive is the real stdout or traceback of that code. The sandbox produces it, not the user, and it never reveals the expected answer. So don't write out what you expect the code to print. Wait for the actual output and reason from it.
1. First, inspect the workbook: the sheets, the header row, the cells around answer_position with their Excel row numbers, and any example values already filled in.
2. Then compute the answer in Python. If some answer cells already hold typed example values, print your value next to each one and make them agree before you write. Load the workbook with openpyxl, write literal values (never formula strings) into the answer cells, and save to output_path.
3. In the same code block, reload output_path with `data_only=True` and print the answer range to confirm every cell holds the intended value. If the printout differs from what you expected, find the cause by printing the inputs and intermediate values. Typical causes are None where you wrote values, or a number that differs from your hand calculation. Don't change your rule just to match the printout. Fix and save again.
When the printed check is correct, reply with a short confirmation and no code block to finish.
