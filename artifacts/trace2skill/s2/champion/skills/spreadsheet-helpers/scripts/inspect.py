"""Inspect raw cell values, types and formats in a workbook."""


def _load(path):
    from openpyxl import load_workbook
    return load_workbook(path, data_only=False)


def show_cells(path, refs):
    """Print value, type and number format for each cell ref like 'A1'.

    refs: list of cell references (strings) or a single string.
    Returns a dict {ref: {'value':..., 'type':..., 'format':...}}.
    """
    if isinstance(refs, str):
        refs = [refs]
    ws = _load(path).active
    out = {}
    for ref in refs:
        c = ws[ref]
        info = {'value': c.value, 'type': type(c.value).__name__, 'format': c.number_format}
        out[ref] = info
        print(ref, '->', info)
    return out


def show_range(path, ref, sheet=None):
    """Print every cell in a range like 'H2:I15' with value and type.

    Returns a list of (coordinate, value, type) tuples.
    """
    wb = _load(path)
    ws = wb[sheet] if sheet else wb.active
    rows = []
    for row in ws[ref]:
        for c in row:
            rows.append((c.coordinate, c.value, type(c.value).__name__))
            print(c.coordinate, repr(c.value), type(c.value).__name__)
    return rows


def parse_date(value):
    """Parse a cell value into a datetime, handling datetime cells and common string formats.

    Returns None only if the value is empty; raises ValueError with the raw
    value shown if no format matches (so failures are loud, never silent).
    """
    import datetime
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime(value.year, value.month, value.day)
    s = str(value).strip()
    fmts = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d',
            '%m-%d-%Y', '%d-%b-%Y', '%b %d, %Y', '%B %d, %Y',
            '%Y-%m-%d %H:%M:%S', '%m/%d/%y']
    for f in fmts:
        try:
            return datetime.datetime.strptime(s, f)
        except ValueError:
            continue
    raise ValueError('Unrecognised date value: %r (type %s)' % (value, type(value).__name__))
