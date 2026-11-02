"""Re-open a saved workbook and verify what actually landed in a range.

Usage:
    from skills.spreadsheet_helpers.verify_range import verify_range
    result = verify_range(out_path, "Sheet1", "D5:G12")
    # expected non-empty count:
    result = verify_range(out_path, "Sheet1", "D5:G12", expect_values=22)
    # expected values: flat list (row-major), 2D list, or [(cell_ref, value), ...]:
    result = verify_range(out_path, "Sheet1", "D5:G12", expect_values=results)
    result = verify_range(out_path, "Sheet1", "D5:G12", expect_values=[[a, b], [c, d]])
    result = verify_range(out_path, "Sheet1", "D5:G12", expect_values=[("D5", 1.5)])
    # cross-check against the task's answer_position:
    result = verify_range(out_path, "Sheet1", "D5:G12", answer_range="D5:H12")

Prints every non-empty cell with its coordinate, and explicit warnings when:
  - the range is empty,
  - the range is empty but values were intended (expect_values given),
  - the non-empty count differs from the expected count,
  - individual cells differ from the expected values (per-cell (cell, expected, actual)
    reports, up to max_report per run),
  - every non-empty cell is a string that looks numeric (numbers stored as text),
  - the verified range is a strict sub-range of, or extends beyond, answer_range
    (the task's answer_position) — when answer_range is passed.
Returns a dict with the cell values, counts, `mismatches` and a `warnings` list.

`expect_values` never raises on argument shape: an unusable shape produces a clear
warning message and count-only verification instead.
"""

MAX_REPORT = 10


def _normalize_expect(expect_values, min_col, min_row, max_col, max_row):
    """Return (expected_count, {coord: value} or None) from any supported shape."""
    import numbers
    if isinstance(expect_values, numbers.Number) and not isinstance(expect_values, bool):
        return int(expect_values), None

    if not isinstance(expect_values, (list, tuple)):
        return None, None

    # list of (cell_ref, value) pairs
    if (len(expect_values) > 0 and all(
            isinstance(p, (list, tuple)) and len(p) == 2
            and isinstance(p[0], str) and p[0].strip() != ""
            for p in expect_values)):
        try:
            from openpyxl.utils.cell import coordinate_from_string, column_index_from_string
        except Exception:
            return None, None
        mapping = {}
        ok = True
        for ref, val in expect_values:
            try:
                col_letter, row = coordinate_from_string(ref.strip())
                mapping[f"{col_letter}{row}"] = val
            except Exception:
                ok = False
                break
        if ok:
            return len(mapping), mapping

    # flat list or 2D list — flatten and reshape to the range shape (row-major)
    flat = []
    try:
        for item in expect_values:
            if isinstance(item, (list, tuple)):
                flat.extend(item)
            else:
                flat.append(item)
    except Exception:
        return None, None

    ncols = max_col - min_col + 1
    if len(flat) % ncols != 0 and ncols > 1:
        return len(flat), None  # can't reshape; fall back to count-only
    mapping = {}
    for i, val in enumerate(flat):
        row = min_row + i // ncols
        col = min_col + i % ncols
        mapping[ws_coord(col, row)] = val
    return len(flat), mapping


def ws_coord(col, row):
    from openpyxl.utils import get_column_letter
    return f"{get_column_letter(col)}{row}"


def _values_equal(expected, actual):
    """Numeric-tolerant comparison: 3 == 3.0, '3' != 3 (type errors are reported)."""
    if expected == actual:
        return True
    try:
        return float(expected) == float(actual)
    except (TypeError, ValueError):
        return False


def _looks_numeric(v):
    if not isinstance(v, str):
        return False
    s = v.strip().replace(",", "").replace("%", "")
    if s == "":
        return False
    try:
        float(s)
        return True
    except ValueError:
        return False


def verify_range(path, sheet, range_str, expect_values=None, answer_range=None):
    from openpyxl import load_workbook
    from openpyxl.utils import range_boundaries
    wb = load_workbook(path, data_only=False)
    if sheet not in wb.sheetnames:
        raise KeyError(f"sheet {sheet!r} not in {wb.sheetnames}")
    ws = wb[sheet]

    min_col, min_row, max_col, max_row = range_boundaries(range_str)
    cells = {}
    for row in ws.iter_rows(min_row=min_row, max_row=max_row,
                            min_col=min_col, max_col=max_col):
        for c in row:
            if c.value is not None and str(c.value).strip() != "":
                cells[c.coordinate] = c.value
    n = len(cells)
    total = (max_row - min_row + 1) * (max_col - min_col + 1)
    wb.close()

    warnings = []
    expected_count = None
    expected_map = None

    # cross-check the verified range against the task's answer_position
    if answer_range is not None:
        try:
            a_min_col, a_min_row, a_max_col, a_max_row = range_boundaries(answer_range)
        except Exception as e:
            warnings.append(
                f"could not parse answer_range {answer_range!r} ({e}); skipping the "
                "answer-position cross-check.")
        else:
            if (min_col, min_row, max_col, max_row) == (a_min_col, a_min_row, a_max_col, a_max_row):
                pass  # exact match, no warning
            elif (min_col >= a_min_col and min_row >= a_min_row
                    and max_col <= a_max_col and max_row <= a_max_row):
                warnings.append(
                    f"verified range {range_str} does not cover the full answer_position "
                    f"{answer_range} — every column of the answer_position must hold its "
                    "expected values: either write it, or explicitly confirm the source "
                    "column already holds the correct values cell-by-cell.")
            else:
                warnings.append(
                    f"verified range {range_str} extends beyond the answer_position "
                    f"{answer_range} — the answer must cover exactly the answer_position; "
                    "verify the answer_position itself and clear anything written outside it.")

    if expect_values is not None:
        try:
            expected_count, expected_map = _normalize_expect(
                expect_values, min_col, min_row, max_col, max_row)
        except Exception as e:
            warnings.append(
                f"could not interpret expect_values of type {type(expect_values).__name__} "
                f"({e}); verifying coverage only. Pass an int count, a flat/2D list of "
                "values, or [(cell_ref, value), ...] pairs.")
        if expected_count is None and not warnings:
            warnings.append(
                f"could not interpret expect_values of type {type(expect_values).__name__}; "
                "verifying coverage only. Pass an int count, a flat/2D list of values, "
                "or [(cell_ref, value), ...] pairs.")

    if n == 0:
        if expected_count:
            warnings.append(
                f"RANGE {range_str} IS EMPTY but {expected_count} values were intended. "
                "The write did not land where you think it did — diagnose before finishing.")
        else:
            warnings.append(f"range {range_str} is empty (0 of {total} cells filled)")
    elif expected_count is not None and n != expected_count:
        if n > expected_count:
            warnings.append(
                f"{n} non-empty cells in {range_str} but only {expected_count} expected — "
                f"{n - expected_count} values written past where the answer ends. "
                "Clear the extra cells and rewrite.")
        else:
            warnings.append(
                f"only {n} of {expected_count} expected cells are filled in {range_str} — "
                f"{expected_count - n} missing. Continue or fix the range.")

    # per-cell value comparison (numeric-tolerant; type differences are reported)
    mismatches = []
    if expected_map:
        for coord, expected in expected_map.items():
            actual = cells.get(coord)
            if actual is None:
                mismatches.append((coord, expected, "<empty>"))
            elif not _values_equal(expected, actual):
                mismatches.append((coord, expected, actual))
        if mismatches:
            warnings.append(
                f"{len(mismatches)} cell(s) in {range_str} differ from the expected values "
                f"(showing up to {MAX_REPORT}): "
                + "; ".join(f"{c}: expected {e!r}, got {a!r}"
                            for c, e, a in mismatches[:MAX_REPORT])
                + ". Fix the computation or rounding, then rewrite.")

    # text-that-looks-numeric warning (numbers stored as strings)
    nonempty_vals = list(cells.values())
    if nonempty_vals and all(isinstance(v, str) for v in nonempty_vals) \
            and any(_looks_numeric(v) for v in nonempty_vals):
        warnings.append(
            "all cells hold text that looks numeric — write numbers as numbers, not strings. "
            "Numeric answers must be stored as int/float, never as formatted strings.")

    print(f"verify_range {path}::{sheet}!{range_str}: {n} of {total} cells non-empty")
    def _key(coord):
        i = 0
        while coord[i].isalpha():
            i += 1
        return (int(coord[i:]), coord[:i])
    for coord in sorted(cells, key=_key):
        print(f"  {coord} = {cells[coord]!r}")
    for w in warnings:
        print(f"WARNING: {w}")

    return {"nonempty_count": n, "total_cells": total,
            "cells": cells, "mismatches": mismatches, "warnings": warnings}
