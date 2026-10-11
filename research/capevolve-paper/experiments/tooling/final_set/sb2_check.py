#!/usr/bin/env python3
"""SpreadsheetBench-2 (Debugging, Financial_Model, Template) gold-as-output check with the OFFICIAL scorer
(RUCKBReasoning/SpreadsheetBench-2@5842db8f evaluation/evaluation.py, unmodified). Zero LLM.
usage: sb2_check.py <sb2_root> <upstream_eval_py> <out.json> <soffice|-> [category ...]
Variants (all derived from the official golden): gold_asis, gold_nocache (openpyxl round-trip: formulas kept, cached
values dropped), input_unchanged.  Paths: A as-shipped, B recalc(output) only, C recalc input+golden+output (the
README's prescribed 'open_spreadsheet' on everything)."""
import importlib.util, json, os, shutil, sys, tempfile, time
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from pathlib import Path
root, ev, outp, soffice = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
cats = sys.argv[5:] or ["Debugging", "Financial_Model", "Template"]
spec = importlib.util.spec_from_file_location("sb2_eval", ev); E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
import openpyxl
sys.path.insert(0, "/home/dev/projects2/cap-evolve-campaign/templates/adapters/spreadsheetbench")
import types
stub = types.ModuleType("cap_evolve")
for n in ("CapabilityAdapter", "Rollout", "Score", "Task"): setattr(stub, n, type(n, (), {}))
sys.modules["cap_evolve"] = stub; sys.path.insert(0, "/home/dev/projects2/cap-evolve-campaign/templates/adapters")
os.environ["SPREADSHEETBENCH_HARNESS_DIR"] = "/home/dev/projects2/cap-evolve-campaign/third_party/spreadsheetbench"
os.environ["SPREADSHEETBENCH_DATA_DIR"] = "/tmp"
sp2 = importlib.util.spec_from_file_location("sbad", "/home/dev/projects2/cap-evolve-campaign/templates/adapters/spreadsheetbench/adapter.py")
ad = importlib.util.module_from_spec(sp2); sp2.loader.exec_module(ad)
tmp = Path(tempfile.mkdtemp(prefix="sb2chk_"))

def score(inp, gold, out, e, cat):
    path = e["spreadsheet_path"]
    fc = cat == "Debugging" and "Color" in path
    fm = cat == "Debugging" and "Embedded" in path
    try:
        ok, err, _, _, reg, mod = E.compare_workbooks_with_regression(str(inp), str(gold), str(out), e["answer_position"], with_font_color=fc, with_formula=fm)
    except Exception as ex:
        return {"accuracy": 0.0, "err": f"EXC {type(ex).__name__}: {str(ex)[:80]}"}
    rr = round(reg["correct"] / reg["total"], 4) if reg["total"] else 0.0
    mr = round(mod["correct"] / mod["total"], 4) if mod["total"] else 0.0
    if rr >= 0.998: rr = 1.0
    return {"accuracy": 1.0 if rr == 1.0 and mr == 1.0 else 0.0, "reg": rr, "mod": mr, "n_reg": reg["total"], "n_mod": mod["total"], "err": (err or "")[:80]}

def one(item):
    cat, e = item
    t0 = time.time(); sid = str(e["id"]); td = tmp / cat / sid; td.mkdir(parents=True)
    inp, gold = root / cat / e["spreadsheet_path"], root / cat / e["golden_response_path"]
    rec = {"cat": cat, "id": sid, "family": os.path.dirname(e["spreadsheet_path"]).replace("/input_files", ""),
           "in_bytes": inp.stat().st_size, "gold_bytes": gold.stat().st_size, "mode": ("font" if cat == "Debugging" and "Color" in e["spreadsheet_path"] else "formula" if cat == "Debugging" and "Embedded" in e["spreadsheet_path"] else "value")}
    try:
        wb = openpyxl.load_workbook(inp, data_only=False); rec["n_sheets_input"] = len(wb.sheetnames)
        rec["input_formula_cells"] = sum(1 for ws in wb.worksheets for r in ws.iter_rows() for c in r if c.data_type == "f")
        rec["input_cells"] = sum(ws.max_row * ws.max_column for ws in wb.worksheets)
    except Exception as ex:
        rec["input_load_err"] = type(ex).__name__
    var = {"gold_asis": td / "g.xlsx", "gold_nocache": td / "n.xlsx", "input_unchanged": td / "i.xlsx"}
    shutil.copyfile(gold, var["gold_asis"]); shutil.copyfile(inp, var["input_unchanged"])
    try: openpyxl.load_workbook(gold, data_only=False).save(var["gold_nocache"])
    except Exception as ex: var.pop("gold_nocache"); rec["nocache_err"] = type(ex).__name__
    rec["A"] = {v: score(inp, gold, p, e, cat) for v, p in var.items()}
    if soffice != "-":
        rc = {}
        for v, p in var.items():
            q = td / ("R_" + p.name); shutil.copyfile(p, q); rc[v] = (q, ad._recalc_workbook(q, soffice, timeout=300))
        rec["B"] = {v: (score(inp, gold, q, e, cat) if ok else {"accuracy": 0.0, "err": "recalc_failed"}) for v, (q, ok) in rc.items()}
        ri, rg = td / "Ri.xlsx", td / "Rg.xlsx"; shutil.copyfile(inp, ri); shutil.copyfile(gold, rg)
        okc = ad._recalc_workbook(ri, soffice, timeout=300) and ad._recalc_workbook(rg, soffice, timeout=300)
        rec["C"] = {v: (score(ri, rg, q, e, cat) if (ok and okc) else {"accuracy": 0.0, "err": "recalc_failed"}) for v, (q, ok) in rc.items()}
    rec["secs"] = round(time.time() - t0, 1); shutil.rmtree(td, ignore_errors=True)
    return rec

items = [(c, e) for c in cats for e in json.load(open(root / c / "dataset.json"))]
with ProcessPoolExecutor(int(os.environ.get("SB2_WORKERS", "24")), mp_context=multiprocessing.get_context("fork")) as ex: res = list(ex.map(one, items, chunksize=1))
json.dump({"engine": soffice, "upstream_eval": ev, "n": len(res), "results": res}, open(outp, "w"))
from collections import defaultdict
agg = defaultdict(lambda: defaultdict(lambda: [0, 0]))
for r in res:
    for path in ("A", "B", "C"):
        for v, s in r.get(path, {}).items():
            agg[(r["cat"], path, v)][0][0] += s["accuracy"] > 0; agg[(r["cat"], path, v)][0][1] += 1
for k in sorted(agg): print(k, "pass", agg[k][0][0], "/", agg[k][0][1])
