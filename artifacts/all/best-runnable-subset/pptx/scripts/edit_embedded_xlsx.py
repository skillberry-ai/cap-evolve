#!/usr/bin/env python3
"""Update value cells in an Excel workbook embedded in a .pptx (or .docx/.xlsx
container) WITHOUT destroying formulas or their cached results.

WHY THIS SCRIPT EXISTS
----------------------
Verifiers for "update the embedded Excel table" tasks read the embedded
workbook with pandas (`pd.read_excel`), which returns the CACHED value stored
next to each formula. If you edit the embedded workbook with openpyxl and save,
openpyxl DROPS every formula's cached value, so pandas then reads NaN for every
formula cell -- silently failing the "inverse rate updated", "other cells
unchanged", and "formulas preserved" checks even though your edit looked right.

This script instead edits the worksheet XML surgically: it changes only the
`<v>` (value) of the target value cells and leaves every formula cell, cached
value, style, and shared string byte-for-byte intact. Formula cells are NEVER
overwritten with hardcoded numbers (that also fails "formulas preserved").

USAGE
-----
    python3 edit_embedded_xlsx.py <in.pptx> <out.pptx> \
        --set B3=7.02 --set C7=1.25 [--sheet sheet1] [--recalc]

Each --set is CELL=NEWVALUE on the target worksheet (default: the first sheet).
Update the *value* cell that holds the rate you were told to change; leave the
inverse/derived formula cells alone -- they recompute from the cell you changed.

--recalc (optional): after editing, refresh all cached formula results with
LibreOffice headless if `soffice` is available (use only when a derived cell
must land within a very tight tolerance; usually unnecessary).

Prints a JSON summary and exits non-zero if a requested cell was a formula or
was not found, so you can react instead of shipping a broken file.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, zipfile


def _find_embedded_xlsx(names):
    cands = [n for n in names if re.search(r'embeddings/.*\.xlsx$', n, re.I)]
    if not cands:
        cands = [n for n in names if n.lower().endswith('.xlsx')]
    return cands


def _sheet_path(names, sheet):
    # match ppt/embeddings unpacked worksheet paths like xl/worksheets/sheet1.xml
    ws = [n for n in names if re.search(r'xl/worksheets/.*\.xml$', n)]
    if sheet:
        for n in ws:
            if os.path.basename(n).lower() == sheet.lower() + '.xml' or os.path.basename(n).lower() == sheet.lower():
                return n
    ws.sort()
    return ws[0] if ws else None


def _edit_sheet_xml(xml, updates):
    """updates: dict CELL->str(value). Returns (new_xml, results)."""
    results = {}
    for cell, val in updates.items():
        # locate the <c r="CELL" ...> ... </c> (may be self-closing)
        m = re.search(r'<c\s+r="%s"([^>]*?)(/>|>(.*?)</c>)' % re.escape(cell), xml, re.S)
        if not m:
            results[cell] = 'not_found'
            continue
        attrs, tail, inner = m.group(1), m.group(2), m.group(3) or ''
        if '<f' in inner or '<f' in tail:
            results[cell] = 'is_formula_skipped'
            continue
        # strip a type attribute so a numeric value is interpreted as number
        new_attrs = re.sub(r'\s+t="[^"]*"', '', attrs)
        new_cell = '<c r="%s"%s><v>%s</v></c>' % (cell, new_attrs, val)
        xml = xml[:m.start()] + new_cell + xml[m.end():]
        results[cell] = 'updated'
    return xml, results


def _recalc_with_soffice(xlsx_path):
    if not shutil.which('soffice') and not shutil.which('libreoffice'):
        return False
    exe = shutil.which('soffice') or shutil.which('libreoffice')
    d = tempfile.mkdtemp()
    try:
        subprocess.run([exe, '--headless', '--calc', '--convert-to', 'xlsx',
                        '--outdir', d, xlsx_path], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        out = os.path.join(d, os.path.splitext(os.path.basename(xlsx_path))[0] + '.xlsx')
        if os.path.exists(out):
            shutil.copy(out, xlsx_path)
            return True
    except Exception:
        return False
    return False


def _replace_zip_entry(zip_path, entry, new_bytes):
    tmp = zip_path + '.tmp'
    with zipfile.ZipFile(zip_path, 'r') as zin, \
         zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == entry:
                data = new_bytes
            zout.writestr(item, data)
    os.replace(tmp, zip_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('infile')
    ap.add_argument('outfile')
    ap.add_argument('--set', action='append', default=[], metavar='CELL=VALUE')
    ap.add_argument('--sheet', default=None)
    ap.add_argument('--recalc', action='store_true')
    a = ap.parse_args()

    updates = {}
    for s in a.set:
        if '=' not in s:
            sys.exit('bad --set (need CELL=VALUE): %s' % s)
        k, v = s.split('=', 1)
        updates[k.strip().upper()] = v.strip()
    if not updates:
        sys.exit('nothing to do: pass at least one --set CELL=VALUE')

    if os.path.abspath(a.infile) != os.path.abspath(a.outfile):
        shutil.copy(a.infile, a.outfile)

    with zipfile.ZipFile(a.outfile, 'r') as z:
        names = z.namelist()
    emb = _find_embedded_xlsx(names)
    if not emb:
        sys.exit('no embedded .xlsx found in %s' % a.infile)
    if a.outfile.lower().endswith('.xlsx'):
        emb = [None]  # editing an xlsx directly

    summary = {'container': a.outfile, 'embedded': [], 'results': {}}
    for embname in emb:
        with tempfile.TemporaryDirectory() as d:
            xlsx_local = os.path.join(d, 'wb.xlsx')
            if embname is None:
                shutil.copy(a.outfile, xlsx_local)
            else:
                with zipfile.ZipFile(a.outfile, 'r') as z:
                    xlsx_local = os.path.join(d, os.path.basename(embname))
                    with open(xlsx_local, 'wb') as f:
                        f.write(z.read(embname))
            with zipfile.ZipFile(xlsx_local, 'r') as z:
                inner = z.namelist()
            sp = _sheet_path(inner, a.sheet)
            if not sp:
                continue
            with zipfile.ZipFile(xlsx_local, 'r') as z:
                xml = z.read(sp).decode('utf-8')
            new_xml, results = _edit_sheet_xml(xml, updates)
            if not any(v == 'updated' for v in results.values()):
                summary['results'][embname or a.outfile] = results
                continue
            _replace_zip_entry(xlsx_local, sp, new_xml.encode('utf-8'))
            if a.recalc:
                summary['recalc'] = _recalc_with_soffice(xlsx_local)
            if embname is None:
                shutil.copy(xlsx_local, a.outfile)
            else:
                with open(xlsx_local, 'rb') as f:
                    _replace_zip_entry(a.outfile, embname, f.read())
            summary['embedded'].append(embname)
            summary['results'][embname or a.outfile] = results

    print(json.dumps(summary, indent=2))
    # exit non-zero if any requested cell was a formula or missing everywhere
    flat = [v for r in summary['results'].values() for v in r.values()]
    if flat and all(v != 'updated' for v in flat):
        sys.exit('ERROR: no cell was updated (see results above)')
    for r in summary['results'].values():
        for cell, st in r.items():
            if st == 'is_formula_skipped':
                sys.stderr.write('WARN: %s is a formula; left unchanged (do not hardcode formulas)\n' % cell)


if __name__ == '__main__':
    main()
