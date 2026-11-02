"""Write a 2D list of values to an exact range, preserving the rest of the workbook.

Usage:
    from skills.spreadsheet_helpers.write_range import write_range
    write_range(src_path, out_path, "Sheet1", "D5:G12", values)

or, for scattered positions:

    write_range(src_path, out_path, "Sheet1", None, [("D5", 1), ("G7", 2)])

Loads the source workbook with openpyxl, writes only the target range, sets
any cells inside the range beyond the provided values to None, and saves to
out_path. Cells outside the range are untouched. Never uses pandas to_excel,
which rewrites the whole sheet.
"""


def _write_2d(ws, range_str, values):
    from openpyxl.utils import range_boundaries
    if not isinstance(values, (list, tuple)):
        raise TypeError("values must be a 2D list (list of rows)")
    min_col, min_row, max_col, max_row = range_boundaries(range_str)
    n_rows = max_row - min_row + 1
    n_cols = max_col - min_col + 1
    if len(values) > n_rows:
        raise ValueError(
            f"values has {len(values)} rows but range {range_str} has {n_rows}")
    for i, row_vals in enumerate(values):
        if not isinstance(row_vals, (list, tuple)):
            raise TypeError(f"values[{i}] is not a list: {row_vals!r}")
        if len(row_vals) > n_cols:
            raise ValueError(
                f"values[{i}] has {len(row_vals)} cols but range {range_str} has {n_cols}")
        for j in range(n_cols):
            v = row_vals[j] if j < len(row_vals) else None
            ws.cell(row=min_row + i, column=min_col + j).value = v


def _write_scattered(ws, pairs):
    for cell_ref, v in pairs:
        ws[cell_ref].value = v


def write_range(src_path, out_path, sheet, range_str, values):
    """Write `values` to `range_str` (A1-style) in `sheet`, save to out_path.

    - values is a 2D list (rows of a rectangular block); cells inside the
      range beyond the provided values are set to None (stale content cleared).
    - Alternatively pass a list of (cell_ref, value) pairs with range_str=None.
    - Every cell outside the range is left untouched.
    """
    from openpyxl import load_workbook
    wb = load_workbook(src_path)
    if sheet not in wb.sheetnames:
        raise KeyError(f"sheet {sheet!r} not in {wb.sheetnames}")
    ws = wb[sheet]

    if range_str is None:
        if not isinstance(values, (list, tuple)) or (
                values and not all(isinstance(p, (list, tuple)) and len(p) == 2
                                   for p in values)):
            raise TypeError("scattered form needs a list of (cell_ref, value) pairs")
        _write_scattered(ws, values)
    else:
        _write_2d(ws, range_str, values)

    wb.save(out_path)
    wb.close()
    return out_path
