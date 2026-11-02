<!-- ... --> placeholder notes kept short.
You need to solve the following spreadsheet manipulation question. It contains six pieces of information:
- instruction: the question about spreadsheet manipulation.
- spreadsheet_path: the path of the spreadsheet file you need to manipulate.
- spreadsheet_content: the target range's total size, the location of the other graded copies
  of this workbook, each sheet's real data extent, and the first few rows of the content.
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

## Output format — READ THIS FIRST, IT IS THE MOST COMMON FAILURE MODE

You have up to {max_turns} rounds of interaction. In each round, reply with exactly ONE python code block:

```python
# your code here
```

- The code block must be a fenced Markdown block starting with ```python and ending with ```.
- Do NOT reply with XML, JSON, tool-call syntax, or prose wrapped around code. If your reply
  contains no ```python fenced block, NOTHING is executed and the round is wasted — repeated
  wasted rounds are a guaranteed score of 0.
- Do not put any text outside the single code block (a short comment inside the block is fine).
- Reply without a code block ONLY when you have verified the saved file at output_path is correct.

## Recommended workflow per round

1. **Inspect** (early rounds): load spreadsheet_path, print sheet names, headers, and the
   cells around answer_position so you understand the layout before writing anything.
   - Sheet names in workbooks often have trailing/leading spaces or differ from the preview.
     Never assume a sheet name; print wb.sheetnames first and match with .strip().
   - To read what formula cells currently evaluate to, open a second copy with
     openpyxl load_workbook(path, data_only=True); to preserve existing formulas when
     writing, save from a copy loaded WITHOUT data_only=True.
2. **Solve and write**: compute the answer in Python and write LITERAL values (not live
   formulas) into answer_position, then save to output_path. Create missing parent
   directories with os.makedirs(..., exist_ok=True) first.
3. **Verify**: re-open output_path and print every cell you wrote in answer_position plus
   a few neighbouring cells, to confirm the values and their location are correct. If they
   are wrong, fix your code and write again.

## Hard rules

- ALWAYS make sure a file exists at output_path before you run out of turns. An output file
  that is never written scores 0 even if your analysis was correct. Budget your rounds: do
  not spend them all on inspection — write a best-effort answer as soon as you reasonably can,
  then verify and refine.
- For Cell-Level Manipulation questions, modify or fill in values ONLY within the exact cell(s)
  given in answer_position. For Sheet-Level Manipulation questions, modify or fill in values
  ONLY within the range given in answer_position — never touch cells outside it.
- Save the workbook with openpyxl (load spreadsheet_path, modify, save to output_path) so all
  other sheets, formulas, and formatting are preserved.
- If your code raises an error, read the traceback carefully and fix the code — do not repeat
  a failing approach unchanged, and do not let errors consume rounds without writing output.
- Prefer computing and writing LITERAL values over live spreadsheet formulas, so the result is
  unambiguous when the file is re-opened for grading.
- When the instruction asks for a formula that fixes a broken one, first derive what the
  correct value(s) should be from the data, then write those computed values into
  answer_position.