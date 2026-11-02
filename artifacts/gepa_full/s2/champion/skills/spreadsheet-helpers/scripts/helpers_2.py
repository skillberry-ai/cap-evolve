"""
Deterministic helpers for spreadsheet manipulation tasks.

The most common procedural failures these helpers fix:
1. Misjudging the real data extent of a sheet (previews truncate), which leads to
   missing rows in the written result.
2. Parsing filter/expression strings like ("key" = "v") AND ("key2" IN LIST a,b)
   and expanding them into one row per combination.
3. Writing a computed table into a sheet range while preserving everything
   outside that range (other sheets, cells, formatting).
4. Re-opening the saved file and checking that every cell in the target range
   holds the intended value before finishing.
"""

import itertools
import re
import shutil
import os

import openpyxl


# ---------------------------------------------------------------------------
# Reading / extent
# ---------------------------------------------------------------------------

def sheet_grid(path, sheet=None, max_rows=None, max_cols=None):
    """Return (sheet_title, list-of-rows) with real non-empty extent — call this
    to see the FULL grid of a sheet instead of trusting a truncated preview.

    Rows are lists of raw cell values; trailing fully-empty rows and columns are
    trimmed. Never assumes the preview shows everything: always check extent here.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    try:
        ws = wb[sheet] if sheet is not None else wb.active
        grid = []
        for row in ws.iter_rows(max_row=max_rows, max_col=max_cols):
            grid.append([c.value for c in row])
        # trim trailing empty rows
        while grid and all(v is None for v in grid[-1]):
            grid.pop()
        # trim trailing empty columns
        if grid:
            width = 0
            for r in grid:
                for i, v in enumerate(r):
                    if v is not None:
                        width = max(width, i + 1)
            grid = [r[:width] for r in grid]
        return ws.title, grid
    finally:
        wb.close()


def print_grid(path, sheet=None, max_rows=60, max_cols=30):
    """Print a sheet's full grid (row numbers + A1 coordinates) for inspection.

    Use in the inspect round; prints up to max_rows x max_cols cells with their
    coordinates so you can locate headers, blanks and the true end of the data.
    """
    title, grid = sheet_grid(path, sheet, max_rows, max_cols)
    print("sheet:", title, "extent:", len(grid), "rows x",
          max((len(r) for r in grid), default=0), "cols")
    for i, r in enumerate(grid, start=1):
        shown = [(openpyxl.utils.get_column_letter(j + 1) + str(i), v)
                 for j, v in enumerate(r)]
        print(i, shown)


# ---------------------------------------------------------------------------
# Filter-expression parsing and expansion
# ---------------------------------------------------------------------------

def parse_filter_expr(text):
    """Parse a boolean filter string into {key: [values]} — call when an
    instruction asks to split a filter column into separate columns.

    Handles `("key" = "value")` and `("key" IN LIST v1,v2,...)` clauses joined
    by AND/OR/and (case-insensitive). Quotes and trailing semicolons are
    stripped. Values are kept as strings exactly as written (leading zeros
    preserved); use strip_leading_zeros to normalise.
    """
    if text is None:
        return {}
    text = str(text)
    clauses = re.split(r'\b(?:AND|and|OR|or)\b', text)
    out = {}
    for clause in clauses:
        clause = clause.strip().strip('()').strip()
        m = re.match(r'^"?([^"]+?)"?\s+IN\s+LIST\s+(.*)$', clause, re.I)
        if m:
            key = m.group(1).strip().strip('"')
            raw = m.group(2).strip().rstrip(';').strip()
            vals = [v.strip().strip('"') for v in raw.split(',') if v.strip()]
            if key and vals:
                out.setdefault(key, []).extend(vals)
            continue
        m = re.match(r'^"?([^"]+?)"?\s*=\s*(.*)$', clause)
        if m:
            key = m.group(1).strip().strip('"')
            val = m.group(2).strip().strip('"').rstrip(';').strip()
            if key and val:
                out.setdefault(key, []).append(val)
    return out


def strip_leading_zeros(value):
    """Convert '03'-style numeric strings to int (dropping leading zeros) and
    leave everything else untouched — call when the instruction says leading
    zeros may be omitted."""
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return value


def cartesian_expand(row, parsed, keys):
    """Expand one input row into a list of dict rows, one per combination of
    the values under `keys` found in `parsed` (from parse_filter_expr).

    A key with no values yields None for that column (blank cell). Call this
    when splitting a filter column into one row per value combination; the
    number of output rows is the product of the list lengths.
    """
    columns = []
    for k in keys:
        vals = parsed.get(k)
        columns.append(vals if vals else [None])
    rows = []
    for combo in itertools.product(*columns):
        r = dict(row)
        for k, v in zip(keys, combo):
            r[k] = v
        rows.append(r)
    return rows


# ---------------------------------------------------------------------------
# Writing into a bounded range (preserving everything outside it)
# ---------------------------------------------------------------------------

def write_table_to_range(path, out_path, sheet, start_row, start_col,
                         header, rows, end_row=None, end_col=None):
    """Write a header + data rows into `sheet` starting at start_row/start_col,
    clipped to end_row/end_col (the allowed modification bounds), preserving
    every other sheet, cell and format — call this instead of pandas to_excel.

    Cells left blank by clipping or by None values are set to None (cleared)
    inside the written block only. Nothing outside [start_row..end_row] x
    [start_col..end_col] is ever touched. Numeric-looking strings are written
    as-is (no silent type coercion). Returns the number of rows written.
    """
    if os.path.abspath(path) != os.path.abspath(out_path):
        d = os.path.dirname(out_path)
        if d:
            os.makedirs(d, exist_ok=True)
        shutil.copy(path, out_path)
    wb = openpyxl.load_workbook(out_path)
    try:
        ws = wb[sheet]
        if end_row is None:
            end_row = start_row + len(rows)
        if end_col is None:
            end_col = start_col + len(header) - 1
        n_written = 0
        # header
        for j, h in enumerate(header):
            c = start_col + j
            if start_row <= end_row and c <= end_col:
                ws.cell(row=start_row, column=c, value=h)
        # data
        for i, r in enumerate(rows):
            rr = start_row + 1 + i
            if rr > end_row:
                break
            n_written += 1
            for j in range(len(header)):
                c = start_col + j
                if c <= end_col:
                    ws.cell(row=rr, column=c,
                            value=None if r[j] is None else r[j])
        wb.save(out_path)
        return n_written
    finally:
        wb.close()


# ---------------------------------------------------------------------------
# Final verification
# ---------------------------------------------------------------------------

def verify_range(path, sheet, min_row, min_col, max_row, max_col,
                 expected=None):
    """Re-open the saved workbook and check every cell in the target range —
    ALWAYS call this on the output file before finishing.

    Prints the current values of the range. If `expected` is given (a dict of
    {(row, col): value} or a list-of-lists matching the range), each cell is
    compared and mismatches are reported. Returns True when everything
    matches (or when no expected values were supplied and the range is
    readable), False otherwise.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    try:
        ws = wb[sheet]
        ok = True
        if expected is not None:
            if isinstance(expected, dict):
                exp_cells = expected
            else:
                exp_cells = {}
                for i, r in enumerate(expected):
                    for j, v in enumerate(r):
                        exp_cells[(min_row + i, min_col + j)] = v
        else:
            exp_cells = {}
        for r in range(min_row, max_row + 1):
            vals = []
            for c in range(min_col, max_col + 1):
                v = ws.cell(row=r, column=c).value
                vals.append(v)
                if (r, c) in exp_cells:
                    e = exp_cells[(r, c)]
                    if e is None:
                        if v is not None:
                            ok = False
                    elif v != e:
                        ok = False
            print(r, vals)
        for (r, c) in exp_cells:
            if not (min_row <= r <= max_row and min_col <= c <= max_col):
                print("out of range, skipped:", (r, c))
        print("range check:", "OK" if ok else "MISMATCH")
        return ok
    finally:
        wb.close()