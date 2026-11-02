"""Example-driven filling: pre-filled cells as oracle and fill map, plus save-and-confirm."""
import os
import openpyxl
from openpyxl.utils import get_column_letter, range_boundaries


def _box(ref):
    ref = str(ref)
    if '!' in ref:
        ref = ref.split('!', 1)[1]
    ref = ref.strip().replace('$', '')
    if ':' not in ref:
        ref = '%s:%s' % (ref, ref)
    c1, r1, c2, r2 = range_boundaries(ref)
    return r1, c1, r2, c2


def example_cells(path, sheet, ref):
    """Return {coord: {'formula': str_or_None, 'value': cached_evaluated_value}} for every
    pre-filled cell in the range. Cached values come from a data_only load, so formula
    examples are already evaluated to their results."""
    wb_v = openpyxl.load_workbook(path, data_only=True)
    wb_f = openpyxl.load_workbook(path)
    ws_v, ws_f = wb_v[sheet], wb_f[sheet]
    r1, c1, r2, c2 = _box(ref)
    out = {}
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            coord = '%s%d' % (get_column_letter(c), r)
            f = ws_f.cell(row=r, column=c).value
            v = ws_v.cell(row=r, column=c).value
            if v is None and (f is None or f == ''):
                continue
            formula = f if isinstance(f, str) and f.startswith('=') else None
            out[coord] = {'formula': formula, 'value': v}
            print('EXAMPLE %s!%s: %s -> %r' % (sheet, coord, formula or repr(v), v))
    print('example_cells: %d pre-filled cell(s) in %s' % (len(out), ref))
    return out


def _same(a, b, tol):
    if a == b:
        return True
    try:
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
                and not isinstance(a, bool) and not isinstance(b, bool):
            return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))
    except (TypeError, ValueError):
        pass
    return False


def validate_examples(computed_map, examples, tol=1e-9):
    """Compare computed {coord: value} against example_cells() output. Numbers compare with
    tolerance; everything else exactly. Prints each failure. Returns True when ALL match."""
    ok = True
    for coord, exp in examples.items():
        if coord not in computed_map:
            ok = False
            print('VALIDATE FAIL %s: your logic produced no value; example is %r'
                  % (coord, exp['value']))
            continue
        got = computed_map[coord]
        if not _same(got, exp['value'], tol):
            ok = False
            print('VALIDATE FAIL %s: your logic produced %r, example evaluates to %r'
                  % (coord, got, exp['value']))
    for coord in computed_map:
        if coord not in examples:
            print('NOTE %s: computed but not an example cell (fine if the pattern extends)' % coord)
    print('validate_examples: %s' % ('ALL EXAMPLES REPRODUCED' if ok
                                    else 'EXAMPLES NOT REPRODUCED - fix logic before writing'))
    return ok


def write_coords(ws, mapping):
    """Write a {coord: value} dict directly into the worksheet. Use for sparse fill patterns
    taken from the example coordinates. None values are skipped."""
    n = 0
    for coord, v in mapping.items():
        if v is None:
            continue
        ws[coord] = v
        n += 1
    print('write_coords: wrote %d cell(s)' % n)
    return n


def save_and_confirm(wb, output_path, sheet, ref):
    """Save the workbook, assert it exists, re-open it, and print the non-empty count and
    the first row of the answer range. Call in the FINAL code block of every task."""
    wb.save(output_path)
    if not os.path.exists(output_path):
        raise RuntimeError('save_and_confirm: output file missing after save: %s' % output_path)
    wb2 = openpyxl.load_workbook(output_path)
    ws2 = wb2[sheet]
    r1, c1, r2, c2 = _box(ref)
    vals = [[ws2.cell(row=r, column=c).value for c in range(c1, c2 + 1)]
            for r in range(r1, r2 + 1)]
    flat = [v for row in vals for v in row if v is not None and v != '']
    print('save_and_confirm: saved %s; %d of %d cell(s) in %s!%s non-empty'
          % (output_path, len(flat), (r2 - r1 + 1) * (c2 - c1 + 1), sheet, ref))
    print('first row of range:', vals[0] if vals else [])
    if not flat:
        print('WARNING: answer range is EMPTY after save - the task is not done')
    return True
