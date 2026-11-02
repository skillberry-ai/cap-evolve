"""Helpers for inspecting worksheet structure before computing.

All functions take an openpyxl worksheet and plain arguments.
No task-specific logic, no network, no writes.
"""

from openpyxl import load_workbook


def _cell_str(value):
    if value is None:
        return ""
    return str(value).strip()


def dump_region(ws, max_row=12, min_row=1):
    """Print raw cell values for rows [min_row, max_row], all used columns.

    Use this to SEE where headers and names actually live before writing
    lookups, and whenever a lookup returns empty results.
    Returns a list of row-lists of the printed values.
    """
    grid = []
    for row in ws.iter_rows(min_row=min_row, max_row=max_row):
        values = [_cell_str(c.value) for c in row]
        grid.append(values)
        print(f"row {row[0].row}: {values}")
    return grid


def _merged_value_map(ws):
    """Return {(row, col): top_left_value} for every cell inside a merged range."""
    mapping = {}
    for rng in ws.merged_cells.ranges:
        min_col, min_row, max_col, max_row = rng.min_col, rng.min_row, rng.max_col, rng.max_row
        top_left = ws.cell(row=min_row, column=min_col).value
        for r in range(min_row, max_row + 1):
            for c in range(min_col, max_col + 1):
                if (r, c) != (min_row, min_col):
                    mapping[(r, c)] = top_left
    return mapping


def effective_value(ws, row, col, merged=None):
    """Value at (row, col), falling back to the merged-range top-left value."""
    v = ws.cell(row=row, column=col).value
    if v is None and merged is None:
        merged = _merged_value_map(ws)
    if v is None:
        v = merged.get((row, col))
    return v


def find_header_row(ws, required_terms, max_row=20):
    """Return the 1-based row index containing the most of `required_terms`
    (case-insensitive substring match across all cells in the row).
    Returns None if no row contains any term."""
    terms = [str(t).lower() for t in required_terms]
    best_row, best_count = None, 0
    for row in ws.iter_rows(min_row=1, max_row=max_row):
        cells = " ".join(_cell_str(c.value).lower() for c in row)
        count = sum(1 for t in terms if t in cells)
        if count > best_count:
            best_row, best_count = row[0].row, count
    return best_row if best_count > 0 else None


def find_name_rows(ws, name, name_col=1, max_row=None):
    """Return sorted list of 1-based row indices where column `name_col`
    effectively equals `name` (exact, case-insensitive, whitespace-stripped).
    Merged cells are resolved: a name merged across rows matches every row
    it spans."""
    target = _cell_str(name).lower()
    merged = _merged_value_map(ws)
    rows = []
    last_row = max_row or ws.max_row
    for r in range(1, last_row + 1):
        v = effective_value(ws, r, name_col, merged)
        if _cell_str(v).lower() == target:
            rows.append(r)
    return rows


def read_back_range(ws, min_row, min_col, max_row, max_col):
    """Read values from a rectangular range as a list of row-lists.
    Use after writing to verify what was actually stored."""
    return [[ws.cell(row=r, column=c).value for c in range(min_col, max_col + 1)]
            for r in range(min_row, max_row + 1)]


def is_uniform(grid, value=0):
    """True if every numeric cell in `grid` equals `value`. Use to detect
    implausible all-zero verification output."""
    for row in grid:
        for v in row:
            try:
                if float(v) != float(value):
                    return False
            except (TypeError, ValueError):
                if v != value:
                    return False
    return True


def open_workbook(path, data_only=False):
    """Load a workbook for inspection."""
    return load_workbook(path, data_only=data_only)
