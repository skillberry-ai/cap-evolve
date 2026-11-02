from openpyxl import load_workbook
import re


def _cell_is_header_like(v):
    if v is None or isinstance(v, (int, float)):
        return False
    s = str(v).strip()
    if not s:
        return False
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9 _\-/]*", s))


def find_header_rows(path, sheet=0):
    """Return 1-based indices of rows that look like header label rows."""
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[sheet] if isinstance(sheet, int) else wb[sheet]
    rows = []
    for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
        cells = [c for c in row if c is not None]
        if not cells:
            continue
        n = len(cells)
        headerish = sum(1 for c in cells if _cell_is_header_like(c))
        # A header row: mostly short non-numeric labels, no long free text.
        if headerish >= max(1, int(0.8 * n)) and all(len(str(c)) <= 40 for c in cells):
            rows.append(r)
    wb.close()
    return rows


def _parse_ref(ref):
    m = re.fullmatch(r"([A-Za-z]+)(\d+):([A-Za-z]+)(\d+)", ref.replace("$", "").replace(" ", ""))
    if not m:
        raise ValueError("ref must look like 'F2:H10'")
    def col_num(s):
        n = 0
        for ch in s.upper():
            n = n * 26 + (ord(ch) - 64)
        return n
    c1, r1, c2, r2 = col_num(m.group(1)), int(m.group(2)), col_num(m.group(3)), int(m.group(4))
    return r1, c1, r2, c2


def verify_range(path, sheet, ref):
    """Re-open a saved workbook and return the values in an A1-style range."""
    r1, c1, r2, c2 = _parse_ref(ref)
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[sheet] if isinstance(sheet, int) else wb[sheet]
    values = []
    for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if r < r1:
            continue
        if r > r2:
            break
        values.append(list(row[c1 - 1:c2]))
    wb.close()
    return {'n_rows': r2 - r1 + 1, 'n_cols': c2 - c1 + 1, 'values': values}
