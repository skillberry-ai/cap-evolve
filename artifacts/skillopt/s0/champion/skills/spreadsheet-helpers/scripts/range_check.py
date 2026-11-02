"""Deterministic helpers for writing values into an exact target range and verifying coverage."""


def write_range(ws, first_cell, values, direction="down"):
    """Write `values` into worksheet `ws` starting at `first_cell` (e.g. 'C4'),
    going down a column (or across a row with direction='across').
    Only len(values) cells are written; nothing beyond is touched.
    Returns the list of (row, col) written."""
    from openpyxl.utils.cell import coordinate_from_string, column_index_from_string
    col_letter, row = coordinate_from_string(first_cell)
    col = column_index_from_string(col_letter)
    coords = []
    for i, v in enumerate(values):
        if direction == "down":
            r, c = row + i, col
        else:
            r, c = row, col + i
        ws.cell(row=r, column=c).value = v
        coords.append((r, c))
    return coords


def read_range(ws, first_cell, last_cell):
    """Read all values in the inclusive range first_cell:last_cell (e.g. 'C4','C200')
    as a list, in row-major order. Empty cells come back as None."""
    from openpyxl.utils.cell import coordinate_from_string, column_index_from_string
    c1, r1 = coordinate_from_string(first_cell)
    c2, r2 = coordinate_from_string(last_cell)
    c1, c2 = column_index_from_string(c1), column_index_from_string(c2)
    out = []
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            out.append(ws.cell(row=r, column=c).value)
    return out


def coverage_report(ws, first_cell, last_cell):
    """Print how many cells in the range are non-empty, plus first/last values,
    so off-by-one shifts and over-filling are visible before finishing."""
    vals = read_range(ws, first_cell, last_cell)
    n = sum(v is not None and v != "" for v in vals)
    print(f"range {first_cell}:{last_cell}: {n}/{len(vals)} non-empty; "
          f"first={vals[0]!r}; last={vals[-1]!r}")
    return vals
