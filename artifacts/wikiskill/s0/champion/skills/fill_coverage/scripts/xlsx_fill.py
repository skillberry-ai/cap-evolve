"""Coverage guards against over-filling past pre-filled example cells, plus number formats."""
import openpyxl
from openpyxl.utils import get_column_letter


def _as_wb(path_or_wb):
    if isinstance(path_or_wb, str):
        return openpyxl.load_workbook(path_or_wb)
    return path_or_wb


def _box(ref):
    from openpyxl.utils import range_boundaries
    ref = str(ref)
    if '!' in ref:
        ref = ref.split('!', 1)[1]
    ref = ref.strip().replace('$', '')
    if ':' not in ref:
        ref = '%s:%s' % (ref, ref)
    c1, r1, c2, r2 = range_boundaries(ref)
    return r1, c1, r2, c2


def _nonempty(ws, r1, c1, r2, c2):
    out = {}
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            v = ws.cell(row=r, column=c).value
            if v is not None and v != '':
                out['%s%d' % (get_column_letter(c), r)] = v
    return out


def prefill_stats(path_or_wb, sheet, ref):
    """Report which cells of the target range are already filled (the user's examples)."""
    wb = _as_wb(path_or_wb)
    ws = wb[sheet]
    r1, c1, r2, c2 = _box(ref)
    nonempty = _nonempty(ws, r1, c1, r2, c2)
    total = (r2 - r1 + 1) * (c2 - c1 + 1)
    last_row = max((int(k[1:]) for k in nonempty), default=None)
    stats = {'nonempty': nonempty, 'count': len(nonempty), 'total': total,
             'last_row': last_row, 'box': (r1, c1, r2, c2)}
    print('prefill: %d of %d cell(s) already filled; last filled row %s'
          % (len(nonempty), total, last_row))
    return stats


def coverage_check(input_path, output_path, sheet, ref, max_list=20):
    """Compare non-empty counts before/after. Warn when far more values were written
    than were pre-filled (the classic 'written past where the answer ends' failure)."""
    wb_in = _as_wb(input_path)
    wb_out = _as_wb(output_path)
    r1, c1, r2, c2 = _box(ref)
    before = _nonempty(wb_in[sheet], r1, c1, r2, c2)
    after = _nonempty(wb_out[sheet], r1, c1, r2, c2)
    prefill_rows = sorted(int(k[1:]) for k in before)
    last_prefill_row = prefill_rows[-1] if prefill_rows else r1 - 1
    beyond = [k for k in after if int(k[1:]) > last_prefill_row and k not in before]
    ok = True
    if before and len(after) > max(len(before) * 2, len(before) + 3):
        ok = False
        print('OVER-FILL WARNING: %d cells were pre-filled but your output has %d values.'
              % (len(before), len(after)))
        print('The expected answer likely ends where the examples end (last pre-filled row %s).'
              % last_prefill_row)
    if beyond:
        print('Newly filled cells beyond the last pre-filled row (%s):' % last_prefill_row)
        for k in beyond[:max_list]:
            print('  %s = %r' % (k, after[k]))
        if len(beyond) > max_list:
            print('  ... and %d more' % (len(beyond) - max_list))
        print('Confirm each of these SHOULD hold a value; blanks are often the correct answer.')
    print('coverage_check: before=%d after=%d -> %s'
          % (len(before), len(after), 'OK' if ok else 'SUSPECTED OVER-FILL'))
    return ok


def set_number_format(ws, ref, fmt):
    """Apply an Excel number format to every cell in the range (display formatting,
    not value rounding)."""
    r1, c1, r2, c2 = _box(ref)
    n = 0
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            ws.cell(row=r, column=c).number_format = fmt
            n += 1
    print('set_number_format: applied %r to %d cell(s)' % (fmt, n))


def clear_cells(ws, ref):
    """Set all cells in the range to None (undo an over-fill)."""
    r1, c1, r2, c2 = _box(ref)
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            ws.cell(row=r, column=c).value = None
    print('clear_cells: cleared %s' % ref)
