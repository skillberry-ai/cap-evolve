"""Deterministic COUNTIF/COUNTIFS-style counting over raw worksheet cells."""


def _norm(value, match_case):
    if value is None:
        return None
    text = str(value).strip()
    if not match_case:
        text = text.casefold()
    return text


def find_rows(sheet, key, key_col, match_case=True):
    """Return 1-based row indices whose cell at key_col matches key."""
    key_n = _norm(key, match_case)
    rows = []
    for row_idx in range(1, sheet.max_row + 1):
        cell = sheet.cell(row=row_idx, column=key_col)
        if _norm(cell.value, match_case) == key_n:
            rows.append(row_idx)
    return rows


def count_values_in_range(sheet, first_row, last_row, first_col, last_col, values, match_case=True):
    """Count occurrences of each value in values over an explicit rectangular range."""
    targets = {_norm(v, match_case): v for v in values}
    counts = {v: 0 for v in values}
    for row_idx in range(first_row, last_row + 1):
        for col_idx in range(first_col, last_col + 1):
            cell_n = _norm(sheet.cell(row=row_idx, column=col_idx).value, match_case)
            if cell_n is not None and cell_n in targets:
                counts[targets[cell_n]] += 1
    return counts


def count_values_in_rows(sheet, key, key_col, count_cols, values, match_case=True):
    """For every row whose key_col matches key, count each value in values across count_cols.

    count_cols is a list of 1-based column indices. Returns {value: count}.
    """
    rows = find_rows(sheet, key, key_col, match_case=match_case)
    counts = {v: 0 for v in values}
    for row_idx in rows:
        for col_idx in count_cols:
            cell_n = _norm(sheet.cell(row=row_idx, column=col_idx).value, match_case)
            if cell_n is not None:
                for v in values:
                    if cell_n == _norm(v, match_case):
                        counts[v] += 1
                        break
    return counts
