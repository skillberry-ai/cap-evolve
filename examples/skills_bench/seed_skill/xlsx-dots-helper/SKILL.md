---
name: xlsx-dots-helper
description: >-
  Fill a derived Excel sheet with openpyxl — e.g. copy columns into a target
  sheet and append computed columns. Use for spreadsheet tasks that build one
  sheet from another (such as computing powerlifting Dots scores).
---

# Building a derived Excel sheet

Use `openpyxl` to read the source sheet and write the target sheet.

## Steps

1. Open the workbook with `openpyxl.load_workbook(path)`.
2. Read the rows you need from the source sheet.
3. Write the required columns into the target sheet, then append the computed
   columns the task asks for.
4. Save with `wb.save(path)`.

Compute values to the precision the task requires.
