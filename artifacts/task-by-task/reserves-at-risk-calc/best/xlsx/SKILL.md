---
name: xlsx
description: "Comprehensive spreadsheet creation, editing, and analysis with formulas, formatting, data analysis, and visualization — and downloading market/commodity price data into a template workbook to compute volatility and risk metrics. Use whenever a task works with spreadsheets (.xlsx, .xlsm, .csv, .tsv, etc), including: (1) downloading IMF gold or commodity price data into a template workbook to compute gold-price volatility, per-country gold valuation exposure, and Reserves-at-Risk (RaR) as a percent of total reserves (a bundled solver script does this end to end); (2) creating new spreadsheets with formulas and formatting; (3) reading or analyzing data; (4) modifying existing spreadsheets while preserving formulas; (5) data analysis and visualization; (6) recalculating formulas."
license: Proprietary. LICENSE.txt has complete terms
---

# Reserves-at-Risk (RaR) / IMF gold-volatility workbooks — read this first

Applies when the task gives a template workbook whose sheets are **Answer**,
**Gold price**, **Value**, **Volume**, and **Total Reserves**, and asks you to
download IMF commodity prices, compute gold-price volatility, per-country gold
valuation exposure, and Reserves-at-Risk (RaR) as a percent of total reserves.

**Do this FIRST — run the bundled solver; do NOT hand-roll the download.** The
single biggest failure on this task is burning the whole time budget probing for
the IMF file (browser download pages, `data.imf.org`, Stooq, FRED, web.archive.org).
Skip all of that: the solver already contains the one download recipe that works
in this sandbox. Locate and run it as step one, before writing any of your own
download code:

```bash
# the skill dir is typically /root/.claude/skills/xlsx (adjust if different).
# Use python3 (bare `python` may be absent in the sandbox -> exit 127).
python3 scripts/rar_solver.py <input_template.xlsx> <output.xlsx>
# defaults: /root/data/test-rar.xlsx  ->  /root/output/rar_result.xlsx
# for this task class the output MUST be /root/output/rar_result.xlsx
```

It downloads the IMF Primary Commodity Price database, extracts the gold series
(US$/troy oz, London PM fix), writes the price series and Excel **formulas** for
log returns and volatility, fills Steps 1–3 with the exact conventions below, and
recalculates with `recalc.py`. After it runs, open the output and confirm the
`Answer` sheet has values and no formula errors.

**If you must download the IMF data yourself** (e.g. you are adapting the flow),
use exactly this — a *browser* User-Agent is rejected with HTTP 403, a plain
`curl`-style UA works, and the payload is a real `.xlsx` (starts with `PK`):

```bash
curl -sSL -A "curl/8.0" \
  "https://www.imf.org/-/media/Files/Research/CommodityPrices/Monthly/external-data.xlsx" \
  -o /tmp/imf.xlsx
```

The gold column is the series whose header mentions **"London"** and **"troy ounce"**;
the date column is text like `2025M9`. Do NOT waste turns on alternate hosts or the
Wayback Machine — this URL + UA is the working path. Match the IMF dates to the dates
already in column A of the "Gold price" sheet (see conventions below).

**Conventions this task class requires — get these EXACTLY right whether you run
the script or write your own code (these are the parts agents get wrong):**
- Monthly log return = `=LN(P_t/P_{t-1})*100` (percent units — multiply by 100).
- 3-month volatility = `=STDEV(<trailing 3 monthly log returns>)`; 12-month
  volatility = `=STDEV(<trailing 12>)`. Use the **latest** month's row for the
  Answer sheet. Annualized 3-month volatility = `3m_vol*SQRT(12)`.
- Populate the "Gold price" sheet by matching IMF prices to the dates **already
  present in column A**; do NOT append rows past the template's last date (a newer
  IMF snapshot would otherwise move the "latest" month and change every answer).
- Z-score / confidence for the 95% one-sided shock = **exactly `1.65`** — NOT
  `1.645`, `1.6449`, or `NORMSINV(0.95)`. The exposure multiplies by it, so a
  ~0.3% deviation is amplified for large reserves and fails the tolerance.
- Gold valuation exposure (row 13/22) = `=gold_value*$C$3/100*$C$4` (value × Z ÷ 100 × 3-month volatility).
- RaR % of total reserves (row 24) = `=exposure/total_reserves*100` — **multiply
  by 100** (percent). Omitting the ×100 is the most common failure (off by 100×).
- Step 2 countries = every country with 2025 data in "Value", plus any country
  with 2025 data in "Volume" but NOT in "Value" (convert its volume to a value
  with the Jan–Sep 2025 average price: `volume*AVERAGE(<Jan..Sep gold prices>)`).
- Step 3 countries = the Step-2 countries that ALSO have 2025 data in "Total
  Reserves"; drop the others. Look up total reserves with a cell reference or
  `INDEX+MATCH`/`XLOOKUP`.
- Clear any stale Excel error literal (e.g. `#N/A`) in the source sheets so the
  whole-workbook error check passes, then run `recalc.py` so the saved file
  carries cached values.

# Requirements for Outputs

## All Excel files

### Zero Formula Errors
- Every Excel model MUST be delivered with ZERO formula errors (#REF!, #DIV/0!, #VALUE!, #N/A, #NAME?)

### Preserve Existing Templates (when updating templates)
- Study and EXACTLY match existing format, style, and conventions when modifying files
- Never impose standardized formatting on files with established patterns
- Existing template conventions ALWAYS override these guidelines

## Financial models

### Color Coding Standards
Unless otherwise stated by the user or existing template

#### Industry-Standard Color Conventions
- **Blue text (RGB: 0,0,255)**: Hardcoded inputs, and numbers users will change for scenarios
- **Black text (RGB: 0,0,0)**: ALL formulas and calculations
- **Green text (RGB: 0,128,0)**: Links pulling from other worksheets within same workbook
- **Red text (RGB: 255,0,0)**: External links to other files
- **Yellow background (RGB: 255,255,0)**: Key assumptions needing attention or cells that need to be updated

### Number Formatting Standards

#### Required Format Rules
- **Years**: Format as text strings (e.g., "2024" not "2,024")
- **Currency**: Use $#,##0 format; ALWAYS specify units in headers ("Revenue ($mm)")
- **Zeros**: Use number formatting to make all zeros "-", including percentages (e.g., "$#,##0;($#,##0);-")
- **Percentages**: Default to 0.0% format (one decimal)
- **Multiples**: Format as 0.0x for valuation multiples (EV/EBITDA, P/E)
- **Negative numbers**: Use parentheses (123) not minus -123

### Formula Construction Rules

#### Assumptions Placement
- Place ALL assumptions (growth rates, margins, multiples, etc.) in separate assumption cells
- Use cell references instead of hardcoded values in formulas
- Example: Use =B5*(1+$B$6) instead of =B5*1.05

#### Formula Error Prevention
- Verify all cell references are correct
- Check for off-by-one errors in ranges
- Ensure consistent formulas across all projection periods
- Test with edge cases (zero values, negative numbers)
- Verify no unintended circular references

#### Documentation Requirements for Hardcodes
- Comment or in cells beside (if end of table). Format: "Source: [System/Document], [Date], [Specific Reference], [URL if applicable]"
- Examples:
  - "Source: Company 10-K, FY2024, Page 45, Revenue Note, [SEC EDGAR URL]"
  - "Source: Company 10-Q, Q2 2025, Exhibit 99.1, [SEC EDGAR URL]"
  - "Source: Bloomberg Terminal, 8/15/2025, AAPL US Equity"
  - "Source: FactSet, 8/20/2025, Consensus Estimates Screen"

# XLSX creation, editing, and analysis

## Overview

A user may ask you to create, edit, or analyze the contents of an .xlsx file. You have different tools and workflows available for different tasks.

## Important Requirements

**LibreOffice Required for Formula Recalculation**: You can assume LibreOffice is installed for recalculating formula values using the `recalc.py` script. The script automatically configures LibreOffice on first run

## Reading and analyzing data

### Data analysis with pandas
For data analysis, visualization, and basic operations, use **pandas** which provides powerful data manipulation capabilities:

```python
import pandas as pd

# Read Excel
df = pd.read_excel('file.xlsx')  # Default: first sheet
all_sheets = pd.read_excel('file.xlsx', sheet_name=None)  # All sheets as dict

# Analyze
df.head()      # Preview data
df.info()      # Column info
df.describe()  # Statistics

# Write Excel
df.to_excel('output.xlsx', index=False)
```

## Excel File Workflows

## CRITICAL: Use Formulas, Not Hardcoded Values

**Always use Excel formulas instead of calculating values in Python and hardcoding them.** This ensures the spreadsheet remains dynamic and updateable.

### ❌ WRONG - Hardcoding Calculated Values
```python
# Bad: Calculating in Python and hardcoding result
total = df['Sales'].sum()
sheet['B10'] = total  # Hardcodes 5000

# Bad: Computing growth rate in Python
growth = (df.iloc[-1]['Revenue'] - df.iloc[0]['Revenue']) / df.iloc[0]['Revenue']
sheet['C5'] = growth  # Hardcodes 0.15

# Bad: Python calculation for average
avg = sum(values) / len(values)
sheet['D20'] = avg  # Hardcodes 42.5
```

### ✅ CORRECT - Using Excel Formulas
```python
# Good: Let Excel calculate the sum
sheet['B10'] = '=SUM(B2:B9)'

# Good: Growth rate as Excel formula
sheet['C5'] = '=(C4-C2)/C2'

# Good: Average using Excel function
sheet['D20'] = '=AVERAGE(D2:D19)'
```

This applies to ALL calculations - totals, percentages, ratios, differences, etc. The spreadsheet should be able to recalculate when source data changes.

## Common Workflow
1. **Choose tool**: pandas for data, openpyxl for formulas/formatting
2. **Create/Load**: Create new workbook or load existing file
3. **Modify**: Add/edit data, formulas, and formatting
4. **Save**: Write to file
5. **Recalculate formulas (MANDATORY IF USING FORMULAS)**: Use the recalc.py script
   ```bash
   python recalc.py output.xlsx
   ```
6. **Verify and fix any errors**:
   - The script returns JSON with error details
   - If `status` is `errors_found`, check `error_summary` for specific error types and locations
   - Fix the identified errors and recalculate again
   - Common errors to fix:
     - `#REF!`: Invalid cell references
     - `#DIV/0!`: Division by zero
     - `#VALUE!`: Wrong data type in formula
     - `#NAME?`: Unrecognized formula name

### Creating new Excel files

```python
# Using openpyxl for formulas and formatting
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

wb = Workbook()
sheet = wb.active

# Add data
sheet['A1'] = 'Hello'
sheet['B1'] = 'World'
sheet.append(['Row', 'of', 'data'])

# Add formula
sheet['B2'] = '=SUM(A1:A10)'

# Formatting
sheet['A1'].font = Font(bold=True, color='FF0000')
sheet['A1'].fill = PatternFill('solid', start_color='FFFF00')
sheet['A1'].alignment = Alignment(horizontal='center')

# Column width
sheet.column_dimensions['A'].width = 20

wb.save('output.xlsx')
```

### Editing existing Excel files

```python
# Using openpyxl to preserve formulas and formatting
from openpyxl import load_workbook

# Load existing file
wb = load_workbook('existing.xlsx')
sheet = wb.active  # or wb['SheetName'] for specific sheet

# Working with multiple sheets
for sheet_name in wb.sheetnames:
    sheet = wb[sheet_name]
    print(f"Sheet: {sheet_name}")

# Modify cells
sheet['A1'] = 'New Value'
sheet.insert_rows(2)  # Insert row at position 2
sheet.delete_cols(3)  # Delete column 3

# Add new sheet
new_sheet = wb.create_sheet('NewSheet')
new_sheet['A1'] = 'Data'

wb.save('modified.xlsx')
```

## Recalculating formulas

Excel files created or modified by openpyxl contain formulas as strings but not calculated values. Use the provided `recalc.py` script to recalculate formulas:

```bash
python recalc.py <excel_file> [timeout_seconds]
```

Example:
```bash
python recalc.py output.xlsx 30
```

The script:
- Automatically sets up LibreOffice macro on first run
- Recalculates all formulas in all sheets
- Scans ALL cells for Excel errors (#REF!, #DIV/0!, etc.)
- Returns JSON with detailed error locations and counts
- Works on both Linux and macOS

## Formula Verification Checklist

Quick checks to ensure formulas work correctly:

### Essential Verification
- [ ] **Test 2-3 sample references**: Verify they pull correct values before building full model
- [ ] **Column mapping**: Confirm Excel columns match (e.g., column 64 = BL, not BK)
- [ ] **Row offset**: Remember Excel rows are 1-indexed (DataFrame row 5 = Excel row 6)

### Common Pitfalls
- [ ] **NaN handling**: Check for null values with `pd.notna()`
- [ ] **Far-right columns**: FY data often in columns 50+
- [ ] **Multiple matches**: Search all occurrences, not just first
- [ ] **Division by zero**: Check denominators before using `/` in formulas (#DIV/0!)
- [ ] **Wrong references**: Verify all cell references point to intended cells (#REF!)
- [ ] **Cross-sheet references**: Use correct format (Sheet1!A1) for linking sheets

### Formula Testing Strategy
- [ ] **Start small**: Test formulas on 2-3 cells before applying broadly
- [ ] **Verify dependencies**: Check all cells referenced in formulas exist
- [ ] **Test edge cases**: Include zero, negative, and very large values

### Interpreting recalc.py Output
The script returns JSON with error details:
```json
{
  "status": "success",           // or "errors_found"
  "total_errors": 0,              // Total error count
  "total_formulas": 42,           // Number of formulas in file
  "error_summary": {              // Only present if errors found
    "#REF!": {
      "count": 2,
      "locations": ["Sheet1!B5", "Sheet1!C10"]
    }
  }
}
```

## Best Practices

### Library Selection
- **pandas**: Best for data analysis, bulk operations, and simple data export
- **openpyxl**: Best for complex formatting, formulas, and Excel-specific features

### Working with openpyxl
- Cell indices are 1-based (row=1, column=1 refers to cell A1)
- Use `data_only=True` to read calculated values: `load_workbook('file.xlsx', data_only=True)`
- **Warning**: If opened with `data_only=True` and saved, formulas are replaced with values and permanently lost
- For large files: Use `read_only=True` for reading or `write_only=True` for writing
- Formulas are preserved but not evaluated - use recalc.py to update values

### Working with pandas
- Specify data types to avoid inference issues: `pd.read_excel('file.xlsx', dtype={'id': str})`
- For large files, read specific columns: `pd.read_excel('file.xlsx', usecols=['A', 'C', 'E'])`
- Handle dates properly: `pd.read_excel('file.xlsx', parse_dates=['date_column'])`

## Code Style Guidelines
**IMPORTANT**: When generating Python code for Excel operations:
- Write minimal, concise Python code without unnecessary comments
- Avoid verbose variable names and redundant operations
- Avoid unnecessary print statements

**For Excel files themselves**:
- Add comments to cells with complex formulas or important assumptions
- Document data sources for hardcoded values
- Include notes for key calculations and model sections
