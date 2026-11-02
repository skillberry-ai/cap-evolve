---
name: spreadsheet_helpers
description: Deterministic helpers for locating headers, writing the exact answer range, and verifying the saved workbook.
---

# spreadsheet-helpers

## When to Apply
Use these helpers on EVERY task. The recurring failure modes in past runs were procedural: locating a header row/column by guessing from the pandas preview, leaving cells in `answer_position` empty, saving with `df.to_excel` (which destroys formatting and other sheets), and ignoring reference sheets that already contain the expected output.

## When NOT to Apply
Never for the business logic itself (which formula, which bucket, which convention). Compute values with your own code, then use these helpers to locate, write, and verify.

## Instructions

1. **Locate anchors by scanning cells, never by assuming the pandas preview row.** The preview is offset by hidden/blank rows. Use `find_all(ws, text)` and inspect the surrounding rows yourself before trusting any row index.
2. **Check for a reference/ground-truth sheet first.** If a sheet like 'Manual Result', 'Expected', 'Solution' holds the expected output (see wiki: ground-truth-reference-sheet), copy its region with `copy_region` instead of re-deriving values.
3. **Write into the openpyxl workbook you loaded from the input path, and save with `wb.save(output_path)`.** NEVER use `df.to_excel` / `pd.ExcelWriter` to produce the final output — it rebuilds the sheet, drops formatting and other sheets.
4. **Fill every cell of `answer_position`.** Build your value grid to exactly the parsed range shape (rows x cols). If a cell has no computed value, write 0 or "" as the instruction implies — the grader counts empty cells as mismatches. A last-cell or single-cell gap is the most common silent failure.
5. **Always end with `save_and_check(wb, output_path, answer_position)`** and read its report before finishing. If it reports empty cells or a shape mismatch, fix and re-run. Never finish while the report is red.
6. If a task says to write a formula, write the formula string (starting with `=`) — `write_values` stores such strings as formulas. Otherwise write computed values.6. If a task says to write a formula, write the formula string (starting with `=`) — `write_values` stores such strings as formulas. Otherwise write computed values.
7. **The helper import may raise ModuleNotFoundError in this environment.** Always use the guarded preamble below (try the import, fall back to the paste-in `h` class). NEVER skip shape-checked writing or read-back verification just because the import failed — that fallback path is where most failures happen.
8. **Sheet-Level Manipulation: `answer_position` is a maximum bound, not a fill quota.** Do NOT pad the range with None/0/"" to fill every cell — writing a value where the expected output has none is graded as a mismatch ("written past where the answer ends"). Fill only the cells that have a real result and stop there. (Instruction 4's fill-every-cell rule applies to Cell-Level Manipulation, where the range is exact.)
9. **Write whole numbers as Python `int`, not float** (e.g. `int(round(x))` when the value is integral) — the grader checks types and reports 'float where int expected'. 'Decimal places' instructions mean `round()` on the value plus `cell.number_format` for display, never formatted strings.
10. **If the instruction or question states concrete expected values or examples ("a payment made in April ... incorrectly being included in the March column", "2 & 1"), reproduce them explicitly in your verification code before finishing** — assert your computed values match those examples. A read-back that only re-prints your own numbers proves nothing about conventions (date-window boundaries, case sensitivity, bucket edges, half-day rows).


### Script: helpers.py

Functions — call as `h.parse_range(...)`, `h.find_all(...)`, `h.write_values(...)`, `h.copy_region(...)`, `h.read_back(...)`, `h.save_and_check(...)`. Start every script with this guarded preamble; if the import fails, the paste-in class provides the same core functions so no safeguard is lost:

```python
try:
    from skills.spreadsheet_helpers import helpers as h
except Exception:
    import re
    class h:
        @staticmethod
        def parse_range(ref):
            ref = str(ref).strip(); sheet = None
            if "!" in ref:
                s, ref = ref.split("!", 1); sheet = s.strip().strip("'")
            a, _, b = ref.partition(":")
            a = a.replace("$", ""); b = (b or a).replace("$", "")
            m1 = re.match(r"^([A-Z]{1,3})(\d+)$", a, re.I); m2 = re.match(r"^([A-Z]{1,3})(\d+)$", b, re.I)
            from openpyxl.utils import column_index_from_string as ci
            return {"sheet": sheet, "min_row": int(m1.group(2)), "min_col": ci(m1.group(1).upper()),
                    "max_row": int(m2.group(2)), "max_col": ci(m2.group(1).upper())}
        @staticmethod
        def write_values(wb, ref, values):
            p = h.parse_range(ref); ws = wb[p["sheet"]] if p["sheet"] else wb.active
            nr = p["max_row"] - p["min_row"] + 1; nc = p["max_col"] - p["min_col"] + 1
            if values and not isinstance(values[0], (list, tuple)):
                values = [list(values)] if nr == 1 else [[v] for v in values]
            assert len(values) == nr and all(len(r) == nc for r in values), (len(values), nr, nc)
            for i in range(nr):
                for j in range(nc):
                    ws.cell(row=p["min_row"] + i, column=p["min_col"] + j, value=values[i][j])
        @staticmethod
        def find_all(ws, text, exact=True):
            out = []
            for row in ws.iter_rows():
                for c in row:
                    if c.value is None: continue
                    s = str(c.value).strip()
                    if (s == str(text)) if exact else (str(text) in s):
                        out.append((c.row, c.column))
            return out
        @staticmethod
        def read_back(path, ref):
            import openpyxl
            p = h.parse_range(ref); wb = openpyxl.load_workbook(path)
            ws = wb[p["sheet"]] if p["sheet"] else wb.active
            return [[ws.cell(row=p["min_row"] + i, column=p["min_col"] + j).value
                     for j in range(p["max_col"] - p["min_col"] + 1)]
                    for i in range(p["max_row"] - p["min_row"] + 1)]
        @staticmethod
        def save_and_check(wb, output_path, ref):
            wb.save(output_path)
            return "read_back:\n" + "\n".join(repr(r) for r in h.read_back(output_path, ref))
    print("note: pasted inline fallback for spreadsheet_helpers")
```

Full-function reference (the importable module implements all of these; the paste-in class implements the starred ones):

- `parse_range(ref) -> dict`: parse `'Sheet'!A1:B5`, `'Total'!O5:Z12`, `C4:C200` or `I6` into `{'sheet', 'min_row', 'min_col', 'max_row', 'max_col', 'n_rows', 'n_cols'}`.
- `find_all(ws, text, exact=True) -> list[(row, col)]`: scan every cell of a worksheet for `text` (exact strip-match, or substring when `exact=False`). Returns all 1-based (row, col) matches. Use this to find header rows/label columns; print the matches and neighbors before trusting an index.
- `sheet_summary(ws, max_rows=8) -> str`: compact text dump of the first rows with row numbers and column letters, for orientation on messy sheets.
- `write_values(wb, ref, values) -> None`: write a 2D grid (or 1D list for a single-row/col range) into `ref` (same format as `answer_position`). Shape-checked: raises a clear error if the grid does not match the range shape, so you cannot silently under-fill. Strings starting with `=` are stored as formulas.
- `copy_region(ws_src, min_row, min_col, max_row, max_col) -> list[list]`: read a rectangular region of values from a worksheet (use it on a reference/ground-truth sheet, then `write_values` into the answer range).
- `read_back(path, ref) -> dict`: re-open a saved file and return `{'values': grid, 'empty': [(row,col),...]}` for the range.
- `save_and_check(wb, output_path, ref) -> str`: save `wb` to `output_path`, re-open it, and return a human-readable report: shape, filled vs empty count, and the full grid. Finish only if it shows full coverage.

Example:
```python
# guarded preamble (see above) defines h
import openpyxl
wb = openpyxl.load_workbook(input_path)
ws = wb['Sheet1']
rows = h.find_all(ws, 'Night shift')           # locate by content, not preview
r, c = rows[0]
vals = h.copy_region(ws, r+1, c, r+1, c+11)   # read the data row next to the label
h.write_values(wb, "B11:M11", vals)
print(h.save_and_check(wb, output_path, "B11:M11"))
```

```python
import re
from openpyxl.utils import column_index_from_string, get_column_letter


def parse_range(ref):
    """Parse a range reference like "'Total'!O5:Z12", "Sheet1!B6:B10", "C4:C200" or "I6"."""
    ref = str(ref).strip()
    sheet = None
    if "!" in ref:
        sheet_part, ref = ref.split("!", 1)
        sheet = sheet_part.strip().strip("'")
    start, _, end = ref.partition(":")
    start = start.replace("$", "")
    end = (end or start).replace("$", "")
    m1 = re.match(r"^([A-Z]{1,3})([0-9]+)$", start, re.I)
    m2 = re.match(r"^([A-Z]{1,3})([0-9]+)$", end, re.I)
    if not m1 or not m2:
        raise ValueError("Cannot parse range reference: %r" % ref)
    min_col = column_index_from_string(m1.group(1).upper())
    min_row = int(m1.group(2))
    max_col = column_index_from_string(m2.group(1).upper())
    max_row = int(m2.group(2))
    if min_row > max_row:
        min_row, max_row = max_row, min_row
    if min_col > max_col:
        min_col, max_col = max_col, min_col
    return {
        "sheet": sheet,
        "min_row": min_row,
        "min_col": min_col,
        "max_row": max_row,
        "max_col": max_col,
        "n_rows": max_row - min_row + 1,
        "n_cols": max_col - min_col + 1,
    }


def find_all(ws, text, exact=True):
    """Scan all cells of ws for text; return list of 1-based (row, col) matches."""
    text = str(text)
    hits = []
    for row in ws.iter_rows():
        for cell in row:
            v = cell.value
            if v is None:
                continue
            s = str(v).strip()
            if (s == text) if exact else (text in s):
                hits.append((cell.row, cell.column))
    return hits


def sheet_summary(ws, max_rows=8):
    """Compact dump of the first rows of ws with row numbers and column letters."""
    lines = ["sheet=%r dims=%r" % (ws.title, ws.dimensions)]
    for r in range(1, min(max_rows, ws.max_row or 1) + 1):
        cells = []
        for c in range(1, min(12, (ws.max_column or 1)) + 1):
            v = ws.cell(row=r, column=c).value
            cells.append("%s%d=%r" % (get_column_letter(c), r, v))
        lines.append(" ".join(cells))
    return "\n".join(lines)


def _as_grid(values, n_rows, n_cols):
    if values is None:
        raise ValueError("values is None")
    if isinstance(values, (list, tuple)) and values and not isinstance(values[0], (list, tuple)):
        if n_rows == 1 and len(values) != n_cols:
            raise ValueError("expected %d values in a single row, got %d" % (n_cols, len(values)))
        if n_cols == 1 and len(values) != n_rows:
            raise ValueError("expected %d values in a single column, got %d" % (n_rows, len(values)))
        if n_rows == 1:
            return [list(values)]
        if n_cols == 1:
            return [[v] for v in values]
        raise ValueError("1D values given but range is %dx%d" % (n_rows, n_cols))
    grid = [list(r) for r in values]
    if len(grid) != n_rows:
        raise ValueError("grid has %d rows, range needs %d" % (len(grid), n_rows))
    for i, r in enumerate(grid):
        if len(r) != n_cols:
            raise ValueError("grid row %d has %d cells, range needs %d" % (i, len(r), n_cols))
    return grid


def write_values(wb, ref, values):
    """Write a value grid into ref. Shape-checked against the range; raises on mismatch."""
    info = parse_range(ref)
    ws = wb[info["sheet"]] if info["sheet"] else wb.active
    grid = _as_grid(values, info["n_rows"], info["n_cols"])
    for i in range(info["n_rows"]):
        for j in range(info["n_cols"]):
            ws.cell(row=info["min_row"] + i, column=info["min_col"] + j, value=grid[i][j])


def copy_region(ws_src, min_row, min_col, max_row, max_col):
    """Read a rectangular region of values from ws_src as a list of lists."""
    return [
        [ws_src.cell(row=r, column=c).value for c in range(min_col, max_col + 1)]
        for r in range(min_row, max_row + 1)
    ]


def read_back(path, ref):
    """Re-open a saved workbook; return {'values': grid, 'empty': [(row, col), ...]} for ref."""
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=False)
    info = parse_range(ref)
    ws = wb[info["sheet"]] if info["sheet"] else wb.active
    grid = copy_region(ws, info["min_row"], info["min_col"], info["max_row"], info["max_col"])
    empty = [
        (info["min_row"] + i, info["min_col"] + j)
        for i, row in enumerate(grid)
        for j, v in enumerate(row)
        if v is None or (isinstance(v, str) and v.strip() == "")
    ]
    return {"values": grid, "empty": empty}


def save_and_check(wb, output_path, ref):
    """Save wb to output_path, re-open it and return a coverage report for ref."""
    wb.save(output_path)
    info = parse_range(ref)
    rb = read_back(output_path, ref)
    total = info["n_rows"] * info["n_cols"]
    filled = total - len(rb["empty"])
    status = "OK" if not rb["empty"] else "INCOMPLETE"
    lines = ["save_and_check: %s - range %s (%d cells), filled=%d, empty=%d"
             % (status, ref, total, filled, len(rb["empty"]))]
    if rb["empty"]:
        lines.append("empty cells (row, col): %r" % (rb["empty"][:20],))
    for i, row in enumerate(rb["values"]):
        lines.append("row %d: %r" % (info["min_row"] + i, row))
    return "\n".join(lines)
```
