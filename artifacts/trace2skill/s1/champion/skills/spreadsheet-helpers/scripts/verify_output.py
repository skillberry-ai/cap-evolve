"""Deterministic post-save verification for spreadsheet outputs."""


def read_range(path, sheet, ref):
    """Read a rectangular range like 'F2:H10' from a saved workbook.

    Returns a list of rows (lists of cell values). Raises if the range
    cannot be parsed or the sheet does not exist.
    """
    import re
    from openpyxl import load_workbook

    m = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", ref.upper().replace(" ", ""))
    if not m:
        raise ValueError("ref must look like 'F2:H10', got %r" % ref)
    c1, r1, c2, r2 = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))

    def col_to_idx(col):
        idx = 0
        for ch in col:
            idx = idx * 26 + (ord(ch) - ord("A") + 1)
        return idx

    wb = load_workbook(path, data_only=True)
    if sheet not in wb.sheetnames:
        raise ValueError("sheet %r not in %r (sheets: %s)" % (sheet, path, wb.sheetnames))
    ws = wb[sheet]
    i1, i2 = col_to_idx(c1), col_to_idx(c2)
    rows = []
    for r in range(r1, r2 + 1):
        rows.append([ws.cell(row=r, column=c).value for c in range(i1, i2 + 1)])
    wb.close()
    return rows


def check_order(rows, required_first, key_col=0):
    """Check that rows whose key_col value appears in required_first come first,
    in required_first order, with all other rows after them in their given order.

    Returns (ok, message). key_col is a 0-based column index into each row.
    """
    wanted = [str(v).strip().upper() if v is not None else "" for v in required_first]
    keys = [str(r[key_col]).strip().upper() if r[key_col] is not None else "" for r in rows]
    matched = [k for k in keys if k in wanted]
    expected = [k for k in wanted if k in keys]
    if matched != expected:
        return False, "ordering mismatch: got %r, expected leading order %r" % (matched, expected)
    return True, "ordering OK: %r" % matched


def check_no_blanks(rows):
    """Check that no cell in the range is None/empty. Returns (ok, message)."""
    blanks = [(i, j) for i, r in enumerate(rows) for j, v in enumerate(r)
              if v is None or (isinstance(v, str) and not v.strip())]
    if blanks:
        return False, "blank cells at (row_idx, col_idx): %r" % (blanks[:20],)
    return True, "no blank cells"


def check_no_header_text(rows, header_words=("NAME", "REF", "ITEM", "ID")):
    """Check that header-like strings did not leak into the data range."""
    leaks = [(i, j, v) for i, r in enumerate(rows) for j, v in enumerate(r)
             if isinstance(v, str) and v.strip().upper() in header_words]
    if leaks:
        return False, "header text leaked into data range: %r" % (leaks[:10],)
    return True, "no header text in data range"


def check_extent(path, sheet_name, allowed_range):
    """Verify the data extent of `sheet_name` in the saved workbook at `path`
    fits within `allowed_range` (e.g. 'A2:M70').

    Returns a dict with the extent, the allowed bounds, and an 'ok' flag.
    """
    from openpyxl import load_workbook
    from openpyxl.utils import range_boundaries

    wb = load_workbook(path, read_only=False, data_only=False)
    if sheet_name not in wb.sheetnames:
        result = {
            "ok": False,
            "error": "sheet %r not found; sheets: %s" % (sheet_name, wb.sheetnames),
        }
        print(result)
        return result
    ws = wb[sheet_name]
    min_col, min_row, max_col, max_row = range_boundaries(allowed_range)
    data_max_row, data_max_col = 0, 0
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                if cell.row > data_max_row:
                    data_max_row = cell.row
                if cell.column > data_max_col:
                    data_max_col = cell.column
    ok = data_max_row <= max_row and data_max_col <= max_col
    result = {
        "ok": ok,
        "sheet": sheet_name,
        "allowed_range": allowed_range,
        "allowed_max_row": max_row,
        "allowed_max_col": max_col,
        "data_max_row": data_max_row,
        "data_max_col": data_max_col,
        "overflow_rows": max(0, data_max_row - max_row),
        "overflow_cols": max(0, data_max_col - max_col),
    }
    print(result)
    return result
