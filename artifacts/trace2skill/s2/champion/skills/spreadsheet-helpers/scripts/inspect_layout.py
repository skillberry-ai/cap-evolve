"""Deterministic worksheet layout inspection helpers (offline, no network)."""


def _norm(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return value


def dump_rows(ws, start_row, end_row, min_col=1, max_col=None):
    """Print raw values of rows [start_row, end_row] of worksheet ws.

    Blanks are shown as '.' so merged/empty cells are visible. Returns
    the printed lines as a list of strings.
    """
    if max_col is None:
        max_col = ws.max_column or min_col
    lines = []
    header = "row | " + " ".join("c%d" % c for c in range(min_col, max_col + 1))
    lines.append(header)
    for r in range(start_row, end_row + 1):
        vals = []
        for c in range(min_col, max_col + 1):
            v = _norm(ws.cell(row=r, column=c).value)
            vals.append("." if v == "" else str(v))
        lines.append("%3d | %s" % (r, " ".join(vals)))
    text = "\n".join(lines)
    print(text)
    return lines


def _merged_lookup(ws):
    """Map (row, col) -> top-left anchor of any merged cell containing it."""
    anchor = {}
    for rng in ws.merged_cells.ranges:
        anchor[(rng.min_row, rng.min_col)] = ws.cell(row=rng.min_row, column=rng.min_col).value
        for r in range(rng.min_row, rng.max_row + 1):
            for c in range(rng.min_col, rng.max_col + 1):
                if (r, c) != (rng.min_row, rng.min_col):
                    anchor[(r, c)] = None  # covered by merge anchored above
    return anchor


def key_groups(ws, key_col=1, start_row=1, end_row=None):
    """Return [(key, first_row, last_row), ...] grouping rows by key.

    The key is taken from the first row of each group and propagated down
    through blank or merged cells, so paired/merged layouts where the key
    appears only on the first row still map every row to its key.
    """
    if end_row is None:
        end_row = ws.max_row or start_row
    merged = _merged_lookup(ws)
    groups = []
    current_key = None
    current_start = None
    for r in range(start_row, end_row + 1):
        if (r, key_col) in merged:
            v = merged[(r, key_col)]
            if v is None:
                # covered by a merge anchored on an earlier row: keep current key
                v = None
            else:
                v = _norm(v)
        else:
            v = _norm(ws.cell(row=r, column=key_col).value)
        if v not in (None, ""):
            if current_key is not None:
                groups.append((current_key, current_start, r - 1))
            current_key = v
            current_start = r
        # blank/merged-covered row: extends the current group
    if current_key is not None:
        groups.append((current_key, current_start, end_row))
    return groups
