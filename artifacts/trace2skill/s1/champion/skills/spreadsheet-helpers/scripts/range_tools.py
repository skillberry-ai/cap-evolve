from openpyxl import load_workbook
from openpyxl.utils import range_boundaries


def _bounds(ref):
    min_col, min_row, max_col, max_row = range_boundaries(ref)
    return min_row, min_col, max_row, max_col


def write_range(path, sheet, ref, values):
    """Write a 2D list of values into an A1-style range (e.g. "A2:M70") of an
    existing worksheet, preserving everything else in the workbook."""
    min_row, min_col, max_row, max_col = _bounds(ref)
    rows = len(values)
    cols = max(len(r) for r in values) if values else 0
    if min_row + rows - 1 > max_row or min_col + cols - 1 > max_col:
        raise ValueError(
            "values (%dx%d) do not fit inside range %s" % (rows, cols, ref)
        )
    wb = load_workbook(path)
    if sheet not in wb.sheetnames:
        raise KeyError("sheet %r not found; sheets: %s" % (sheet, wb.sheetnames))
    ws = wb[sheet]
    for i, row_vals in enumerate(values):
        for j, v in enumerate(row_vals):
            ws.cell(row=min_row + i, column=min_col + j, value=v)
    wb.save(path)


def read_range(path, sheet, ref):
    """Read back the full contents of an A1-style range as a list of lists."""
    min_row, min_col, max_row, max_col = _bounds(ref)
    wb = load_workbook(path, data_only=False)
    if sheet not in wb.sheetnames:
        raise KeyError("sheet %r not found; sheets: %s" % (sheet, wb.sheetnames))
    ws = wb[sheet]
    out = []
    for r in range(min_row, max_row + 1):
        out.append(
            [ws.cell(row=r, column=c).value for c in range(min_col, max_col + 1)]
        )
    return out


def check_duplicate_keys(df, key_col):
    """Return the list of duplicated key values in df[key_col]. Call before any
    pandas merge used as a lookup; duplicates silently multiply rows."""
    s = df[key_col]
    dup_mask = s.duplicated(keep=False)
    return sorted(set(s[dup_mask].dropna().tolist()))
