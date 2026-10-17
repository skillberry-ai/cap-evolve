### Guidance for Spreadsheet Manipulation

#### 1. Handling Formulas
- **Crucial**: Do NOT write formulas into the spreadsheet. Even if the instruction asks "How can I create a formula...", you must implement the LOGIC of that formula in Python and write the RESULTING literal values into the cells.
- Example: If the task asks for `=IF(B2<>"", 1, "")`, your Python code should check if cell B2 is not empty and then write the integer `1` or an empty string `""` to cell A2.

#### 2. Ensuring Correct Types
- **Exact Type Match**: Match the exact Python type required. If a value is expected as a float (e.g., `10.0`), do not write it as an integer (`10`). If a string is expected, do not parse it into a number.
- **Preserve Original Text**: When the target is a string, do not parse or convert it into a number or date unless explicitly told to. Keep the original text as found in the source.
- **Dates**: Use `datetime` objects. Avoid writing dates as formatted strings (e.g., use `datetime.date(2021, 4, 21)` instead of `"04/21/2021"`).
- **Numbers**: Use `int` or `float`. Ensure you are not wrapping numbers in quotes.

#### 3. Precision and Integrity
- **Match the Input**: If the instruction implies a specific format or value, ensure your Python logic precisely matches it.
- **Do Not Overwrite**: Only modify the range specified in `answer_position`. Overwriting cells outside this range, even if they seem incorrect, can lead to failure.

#### 4. Verification Step
- After writing your changes, perform a final check to avoid common failures:
  1. **Check Range Coverage**: Ensure every cell in the `answer_position` that requires a value actually contains one.
  2. **Check Minimal Modification**: Ensure no cells outside the `answer_position` were accidentally modified or deleted.
  3. **Check Types**: Verify the Python type of each written value.
  ```python
  # Example verification
  wb = openpyxl.load_workbook(output_path)
  ws = wb.active
  print(f"Cell A2 value: {ws['A2'].value} (Type: {type(ws['A2'].value)})")
  ```
- If you see a formula (starts with `=`), a type mismatch (e.g., `int` instead of `float`), or missing values in the target range, fix them before finishing.

#### 5. Complex Logic Implementation
- When implementing complex calculations (e.g., "restarting a count" or "sliding reference"), use a while-loop or a pointer-based approach to ensure you precisely follow the sequence of events.
- **Example (Restarting Count)**:
  To count occurrences where a value increases by 10% and restart the reference:
  ```python
  count = 0
  i = 0
  while i < len(data) - 1:
      ref = data[i]
      found = False
      for j in range(i + 1, len(data)):
          if data[j] >= ref * 1.1:
              count += 1
              i = j + 1 # Restart from cell right of found cell
              found = True
              break
      if not found: break
  ```
