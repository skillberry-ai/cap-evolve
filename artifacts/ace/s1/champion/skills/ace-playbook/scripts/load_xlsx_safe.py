
import zipfile, shutil, re, tempfile, os
import openpyxl


def sheet_xml_path(path, sheet_name):
    """Resolve sheet name -> 'xl/worksheets/sheetN.xml' via workbook.xml and its rels.
    Never search for sheetId inside worksheet parts — that attribute only exists
    in xl/workbook.xml, and the file mapping comes from xl/_rels/workbook.xml.rels."""
    import xml.etree.ElementTree as ET
    NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
          'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
          'pr': 'http://schemas.openxmlformats.org/package/2006/relationships'}
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    rid_to_target = {rel.get('Id'): rel.get('Target') for rel in rels.findall('pr:Relationship')}
    for sh in wb.find('m:sheets', NS):
        if str(sh.get('name')).strip() == sheet_name:
            target = rid_to_target[sh.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
            if not target.startswith('xl/'):
                target = 'xl/' + target.lstrip('/')
            return target
    raise KeyError(f'sheet {sheet_name!r} not found')


def load_xlsx_safe(path, data_only=False, **kwargs):
    """Load a workbook, falling back to a sanitized copy if openpyxl fails.
    Sanitization strips <dataValidations> and <conditionalFormatting> elements
    (metadata only — cell values are untouched) from worksheet XML in a temp copy."""
    try:
        return openpyxl.load_workbook(path, data_only=data_only, **kwargs)
    except Exception as e:
        print('direct load failed:', e)
    try:
        return openpyxl.load_workbook(path, data_only=data_only, read_only=True, **kwargs)
    except Exception as e:
        print('read_only load failed:', e)
    tmp = tempfile.mktemp(suffix='.xlsx')
    shutil.copy(path, tmp)
    strip_pattern = re.compile(rb'<(dataValidations|conditionalFormatting)\b.*?</\1>', re.DOTALL)
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.namelist():
            data = zin.read(item)
            if item.startswith('xl/worksheets/') and item.endswith('.xml'):
                data = strip_pattern.sub(b'', data)
                data = re.sub(rb'<(dataValidations|conditionalFormatting)\b[^>]*/>', b'', data)
            zout.writestr(item, data)
    wb = openpyxl.load_workbook(tmp, data_only=data_only, **kwargs)
    print('loaded sanitized copy:', tmp)
    return wb
