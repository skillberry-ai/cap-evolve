"""Helpers for discovering and validating pre-filled example (oracle) cells."""
import openpyxl


def _as_wb(path_or_wb):
    if isinstance(path_or_wb, str):
        return openpyxl.load_workbook(path_or_wb)
    return path_or_wb


def _strip_ref(ref):
    ref = str(ref)
    return ref.split('!', 1)[1] if '!' in ref else ref


def find_nonempty_cells(path_or_wb, sheet, ref):
    """Return {coordinate: value} for cells in the range that already hold data.
    Use this to discover the user's pre-filled example outputs."""
    from .xlsx_edit import parse_ref
    wb = _as_wb(path_or_wb)
    ws = wb[sheet]
    _, r1, c1, r2, c2 = parse_ref(_strip_ref(ref))
    out = {}
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            v = ws.cell(row=r, column=c).value
            if v is not None and v != '':
                coord = '%s%d' % (openpyxl.utils.get_column_letter(c), r)
                out[coord] = v
    return out


def oracle_check(path_or_wb, sheet, expected_map, computed_fn=None):
    """Validate logic against example cells. expected_map maps coordinate -> value
    the user already filled in; if computed_fn is given (coordinate -> your computed
    value), compare that instead of the file's own value. Prints each failing cell.
    Returns True if all examples are reproduced exactly (including type)."""
    wb = _as_wb(path_or_wb)
    ws = wb[sheet]
    ok = True
    for coord, exp in expected_map.items():
        got = computed_fn(coord) if computed_fn is not None else ws[coord].value
        same = got == exp and type(got) is type(exp)
        if not same:
            try:
                same = float(got) == float(exp) and isinstance(got, (int, float)) and isinstance(exp, (int, float))
            except (TypeError, ValueError):
                same = False
        if not same:
            ok = False
            print('ORACLE FAIL %s!%s: logic produced %r (%s), example is %r (%s)'
                  % (sheet, coord, got, type(got).__name__, exp, type(exp).__name__))
    print('oracle_check: %s' % ('all examples reproduced' if ok else 'EXAMPLES NOT REPRODUCED - fix logic before filling the range'))
    return ok
