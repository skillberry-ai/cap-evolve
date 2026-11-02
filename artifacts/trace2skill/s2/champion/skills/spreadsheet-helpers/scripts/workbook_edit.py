"""In-place workbook editing and verification helpers (openpyxl-based).

Use these instead of pandas read/write round-trips: pandas coerces integer
columns to floats when NaNs are present and to_excel rewrites every cell,
destroying formatting and touching cells outside the permitted range.
"""

from openpyxl import load_workbook
from openpyxl.utils import range_boundaries


def load(path):
    """Load a workbook for in-place editing, preserving formatting and values."""
    return load_workbook(path)


def save(wb, path):
    """Save the workbook to the given path."""
    wb.save(path)


def write_range(ws, start_row, start_col, values):
    """Write a 2D list (or 1D list for a single row) starting at (start_row, start_col).

    Only the cells covered by `values` are touched; all other cells, their
    formatting and their types are left untouched. Integers stay integers.
    """
    if values and not isinstance(values[0], (list, tuple)):
        values = [values]
    for i, row in enumerate(values):
        for j, val in enumerate(row):
            ws.cell(row=start_row + i, column=start_col + j, value=val)


def read_range(path, sheet_name, cell_range):
    """Re-open the SAVED file and return the values in `sheet_name!cell_range`
    as a list of lists. Use this to verify the final artifact after saving."""
    wb = load_workbook(path, data_only=True)
    ws = wb[sheet_name]
    min_col, min_row, max_col, max_row = range_boundaries(cell_range)
    return [
        [ws.cell(row=r, column=c).value for c in range(min_col, max_col + 1)]
        for r in range(min_row, max_row + 1)
    ]


def verify_range(path, sheet_name, cell_range, expected):
    """Verify that the saved file's `sheet_name!cell_range` matches `expected`
    (2D list) with EXACT values and EXACT types (100 != 100.0).

    Returns (ok, problems) where problems is a list of human-readable strings.
    """
    actual = read_range(path, sheet_name, cell_range)
    problems = []
    if len(actual) != len(expected):
        problems.append(
            "row count mismatch: expected %d, got %d" % (len(expected), len(actual))
        )
    for i, (a_row, e_row) in enumerate(zip(actual, expected)):
        if len(a_row) != len(e_row):
            problems.append("row %d width mismatch" % i)
            continue
        for j, (a, e) in enumerate(zip(a_row, e_row)):
            if a != e or type(a) is not type(e):
                problems.append(
                    "cell (%d,%d): expected %r (%s), got %r (%s)"
                    % (i, j, e, type(e).__name__, a, type(a).__name__)
                )
    return (not problems), problems


def compare_unmodified(orig_path, out_path, sheet_name, skip_range=None):
    """Check that every cell in `sheet_name` of out_path equals the original in
    orig_path, except cells inside `skip_range` (e.g. 'A2:M70'), which are the
    cells you were allowed to modify. Returns (ok, problems)."""
    wb_o = load_workbook(orig_path, data_only=True)
    wb_n = load_workbook(out_path, data_only=True)
    problems = []
    if sheet_name not in wb_o.sheetnames or sheet_name not in wb_n.sheetnames:
        return False, ["sheet %r missing" % sheet_name]
    ws_o, ws_n = wb_o[sheet_name], wb_n[sheet_name]
    skip_cells = set()
    if skip_range:
        min_col, min_row, max_col, max_row = range_boundaries(skip_range)
        skip_cells = {
            (r, c)
            for r in range(min_row, max_row + 1)
            for c in range(min_col, max_col + 1)
        }
    for row in ws_o.iter_rows():
        for cell in row:
            if (cell.row, cell.column) in skip_cells:
                continue
            new = ws_n.cell(row=cell.row, column=cell.column).value
            if new != cell.value or type(new) is not type(cell.value):
                problems.append(
                    "cell %s changed: %r (%s) -> %r (%s)"
                    % (
                        cell.coordinate,
                        cell.value,
                        type(cell.value).__name__,
                        new,
                        type(new).__name__,
                    )
                )
    return (not problems), problems
