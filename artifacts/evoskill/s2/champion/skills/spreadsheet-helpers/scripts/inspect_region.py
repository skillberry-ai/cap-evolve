"""Open a workbook and report the real structure around a target range.

Usage:
    from skills.spreadsheet_helpers.inspect_region import inspect_region
    report = inspect_region("/mnt/data/input.xlsx", "Sheet1", around_range="D5:G12")

Deterministic, offline, read-only. Never guesses from previews: it reads the
actual cells with openpyxl and reports every non-empty cell around the target
range, detected header rows, and the true data extent of each column/row block.
"""


def _parse_range(range_str):
    from openpyxl.utils import range_boundaries
    min_col, min_row, max_col, max_row = range_boundaries(range_str)
    return min_row, max_row, min_col, max_col


def _cell_map(ws, min_row, max_row, min_col, max_col):
    """Return {(row, col): value} for non-empty cells in the block."""
    out = {}
    for row in ws.iter_rows(min_row=min_row, max_row=max_row,
                            min_col=min_col, max_col=max_col):
        for c in row:
            if c.value is not None and str(c.value).strip() != "":
                out[(c.row, c.column)] = c.value
    return out


def _coord(row, col):
    from openpyxl.utils import get_column_letter
    return f"{get_column_letter(col)}{row}"


def _detect_header_rows(cells, min_row, max_row, min_col, max_col):
    """Rows whose cells are mostly non-numeric labels, with >=2 repeats or
    whose values look like column labels aligned above data."""
    header_candidates = []
    for r in range(min_row, max_row + 1):
        vals = [cells.get((r, c)) for c in range(min_col, max_col + 1)]
        nonempty = [v for v in vals if v is not None]
        if not nonempty:
            continue
        texty = sum(1 for v in nonempty if isinstance(v, str))
        if len(nonempty) >= 2 and texty == len(nonempty):
            header_candidates.append((r, nonempty))
    return header_candidates


def _column_extent(ws, col, start_row, max_row_down=500):
    """First and last non-empty row of a column starting at start_row."""
    first = last = None
    for r in range(start_row, min(ws.max_row, start_row + max_row_down) + 1):
        v = ws.cell(row=r, column=col).value
        if v is not None and str(v).strip() != "":
            if first is None:
                first = r
            last = r
    return first, last


def _row_extent(ws, row, start_col, max_col_right=200):
    """First and last non-empty column of a row starting at start_col."""
    first = last = None
    for c in range(start_col, min(ws.max_column, start_col + max_col_right) + 1):
        v = ws.cell(row=row, column=c).value
        if v is not None and str(v).strip() != "":
            if first is None:
                first = c
            last = c
    return first, last


def inspect_region(path, sheet, around_range=None, context_rows=6, context_cols=4):
    """Return a dict describing the real structure around `around_range`.

    Reports: every non-empty cell in the rows above and columns beside the
    target range (with coordinates and values), candidate header rows, and the
    true data extent of each column and row overlapping the range.
    """
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True, read_only=False)
    if sheet not in wb.sheetnames:
        raise KeyError(f"sheet {sheet!r} not in {wb.sheetnames}")
    ws = wb[sheet]

    if around_range is None:
        t_min_row, t_max_row = 1, ws.max_row
        t_min_col, t_max_col = 1, ws.max_column
    else:
        t_min_row, t_max_row, t_min_col, t_max_col = _parse_range(around_range)

    # Context block: rows above and columns beside the target range.
    ctx_min_row = max(1, t_min_row - context_rows)
    ctx_min_col = max(1, t_min_col - context_cols)
    ctx_max_col = min(ws.max_column, t_max_col + context_cols)
    ctx_cells = _cell_map(ws, ctx_min_row, t_max_row, ctx_min_col, ctx_max_col)

    # Full block over the target columns (to end of sheet) for extent checks.
    block_cells = _cell_map(ws, t_min_row, ws.max_row, t_min_col, t_max_col)

    headers = _detect_header_rows(ctx_cells, ctx_min_row, t_min_row - 1,
                                  t_min_col, t_max_col) if t_min_row > ctx_min_row else []

    columns = {}
    for c in range(t_min_col, t_max_col + 1):
        first, last = _column_extent(ws, c, t_min_row)
        col_cells = {r: v for (r, cc), v in block_cells.items() if cc == c}
        columns[_coord(1, c)] = {
            "first_nonempty_row": first,
            "last_nonempty_row": last,
            "nonempty_count": len(col_cells),
        }

    rows = {}
    for r in range(t_min_row, t_max_row + 1):
        first, last = _row_extent(ws, r, t_min_col)
        row_cells = {cc: v for (rr, cc), v in block_cells.items() if rr == r}
        rows[r] = {
            "first_nonempty_col": first,
            "last_nonempty_col": last,
            "nonempty_count": len(row_cells),
        }

    # Data extent of the whole block (target columns, from target start row).
    nonempty_block = sorted(block_cells)
    extent = {
        "min_row": nonempty_block[0][0] if nonempty_block else None,
        "max_row": nonempty_block[-1][0] if nonempty_block else None,
        "min_col": min(c for _, c in nonempty_block) if nonempty_block else None,
        "max_col": max(c for _, c in nonempty_block) if nonempty_block else None,
    }

    wb.close()
    return {
        "sheet": sheet,
        "target_range": around_range,
        "context_block": f"{_coord(ctx_min_row, ctx_min_col)}:{_coord(t_max_row, ctx_max_col)}",
        "context_cells": {f"{_coord(r, c)}": v for (r, c), v in sorted(ctx_cells.items())},
        "header_candidates": [{"row": r, "labels": vals} for r, vals in headers],
        "column_extent": columns,
        "row_extent": rows,
        "block_data_extent": extent,
    }
