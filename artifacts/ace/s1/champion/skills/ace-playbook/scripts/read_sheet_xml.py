
import zipfile
import re
import xml.etree.ElementTree as ET

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def _sheet_targets(z):
    """Map sheet name -> worksheet part path via xl/_rels/workbook.xml.rels."""
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    rid_to_target = {rel.get('Id'): rel.get('Target') for rel in rels}
    mapping = {}
    for sh in wb.find('m:sheets', NS):
        rid = sh.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        target = rid_to_target.get(rid, '')
        if target and not target.startswith('/'):
            target = 'xl/' + target
        mapping[sh.get('name')] = target
    return mapping


def read_sheet_xml(path, sheet_name):
    """Read a worksheet's values directly from the xlsx zip, bypassing openpyxl.
    Returns list of rows; each row is a list of cell values (strings/numbers)."""
    with zipfile.ZipFile(path) as z:
        target = _sheet_targets(z).get(sheet_name)
        if not target:
            raise KeyError('sheet not found: %s' % sheet_name)
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            ss = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in ss:
                shared.append(''.join(t.text or '' for t in si.iter(
                    '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')))
        root = ET.fromstring(z.read(target))
        rows = []
        for row in root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
            vals = {}
            for c in row:
                ref = c.get('r') or ''
                col = re.match(r'([A-Z]+)', ref)
                idx = 0
                if col:
                    for ch in col.group(1):
                        idx = idx * 26 + (ord(ch) - 64)
                v = c.find('m:v', NS)
                if v is None:
                    continue
                if c.get('t') == 's':
                    val = shared[int(v.text)]
                elif c.get('t') == 'inlineStr':
                    val = ''.join(t.text or '' for t in c.iter(
                        '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t'))
                else:
                    txt = v.text
                    try:
                        val = float(txt) if '.' in (txt or '') else int(txt)
                    except (TypeError, ValueError):
                        val = txt
                vals[idx] = val
            if vals:
                width = max(vals)
                rows.append([vals.get(i) for i in range(1, width + 1)])
        return rows
