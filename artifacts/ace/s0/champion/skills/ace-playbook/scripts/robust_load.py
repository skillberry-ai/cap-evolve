import zipfile
from openpyxl import load_workbook


def _norm(s):
    return str(s).strip().lower() if s is not None else ''


def _grid_from_xml(path):
    """Last-resort: parse shared strings + each sheet's XML into a grid dict."""
    import re
    from xml.etree import ElementTree as ET
    NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
          'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
    shared = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if 'xl/sharedStrings.xml' in names:
            root = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in root.findall('m:si', NS):
                shared.append(''.join(t.text or '' for t in si.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')))
        wb_xml = ET.fromstring(z.read('xl/workbook.xml'))
        rels = ET.fromstring(z.read('xl/_rels/xl/workbook.xml.rels'.replace('xl/_rels/xl/', 'xl/_rels/')) if 'xl/_rels/workbook.xml.rels' in names else z.read('xl/_rels/workbook.xml.rels'))
        rel_map = {r.get('Id'): r.get('Target') for r in rels}
        sheets = {}
        for sh in wb_xml.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet'):
            rid = sh.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            target = rel_map.get(rid, '')
            if not target.startswith('xl/'):
                target = 'xl/' + target.lstrip('/')
            if target not in names:
                continue
            root = ET.fromstring(z.read(target))
            grid = {}
            for cell in root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                ref = cell.get('r')
                if not ref:
                    continue
                m = re.match(r'([A-Z]+)(\d+)', ref)
                col, row = m.group(1), int(m.group(2))
                t = cell.get('t')
                v = cell.find('m:v', NS)
                val = None
                if v is not None:
                    if t == 's':
                        val = shared[int(v.text)]
                    elif t == 'str':
                        val = v.text
                    else:
                        try:
                            val = float(v.text)
                            if val == int(val):
                                val = int(val)
                        except (TypeError, ValueError):
                            val = v.text
                grid[(row, col)] = val
            sheets[sh.get('name')] = grid
    return sheets


class _GridSheet:
    """Minimal read-only sheet wrapper over a {(row, 'COL'): value} grid."""
    def __init__(self, grid):
        self._grid = grid
        self.max_row = max((r for r, _ in grid), default=1)
        self.max_column = 0
        from openpyxl.utils import column_index_from_string
        self._ci = column_index_from_string
        self.max_column = max((self._ci(c) for _, c in grid), default=1)

    def cell(self, row, column):
        from openpyxl.utils import get_column_letter
        val = self._grid.get((row, get_column_letter(column)))
        return type('C', (), {'value': val})()


def load_workbook_robust(path, data_only=True):
    """Load a workbook resilient to sheet-name wildcard/defined-name errors.
    Returns (wb, get_sheet) where get_sheet(name_or_index) returns a worksheet
    (openpyxl or grid fallback) regardless of special characters in titles."""
    try:
        wb = load_workbook(path, data_only=data_only)
        def get(name):
            if isinstance(name, int):
                return wb.worksheets[name]
            for s in wb.worksheets:
                if _norm(s.title) == _norm(name):
                    return s
            raise KeyError('sheet not found: %r in %r' % (name, wb.sheetnames))
        return wb, get
    except Exception as e:
        grids = _grid_from_xml(path)
        wrapped = {name: _GridSheet(g) for name, g in grids.items()}
        def get2(name):
            if isinstance(name, int):
                return list(wrapped.values())[name]
            for n, s in wrapped.items():
                if _norm(n) == _norm(name):
                    return s
            raise KeyError('sheet not found: %r in %r' % (name, list(wrapped)))
        return wrapped, get2
