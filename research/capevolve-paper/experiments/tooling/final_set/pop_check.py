#!/usr/bin/env python3
"""Population ceiling check, zero LLM: for EVERY task/case, score the official gold file AS the agent output.
  A = as-saved compare(gold, gold)                       -> tasks that can never score under the as-saved reward (data defects)
  B = recalc(copy of gold) then compare(gold, recalced)  -> tasks whose gold itself changes under the engine's recalculation,
                                                            i.e. cannot score under the recalc-reward (SPREADSHEETBENCH_REWARD_RECALC=1)
usage: pop_check.py <repo> <data_dir> <outjson> [soffice]   (soffice omitted -> only A)"""
import json, os, shutil, sys, tempfile, types, importlib.util
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
repo, data, outp = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
soffice = sys.argv[4] if len(sys.argv) > 4 else None
stub = types.ModuleType("cap_evolve")
for n in ("CapabilityAdapter", "Rollout", "Score", "Task"): setattr(stub, n, type(n, (), {}))
sys.modules["cap_evolve"] = stub
adir = repo / "templates/adapters"; sys.path.insert(0, str(adir / "spreadsheetbench")); sys.path.insert(0, str(adir))
os.environ["SPREADSHEETBENCH_HARNESS_DIR"] = str(repo / "third_party/spreadsheetbench"); os.environ["SPREADSHEETBENCH_DATA_DIR"] = str(data)
spec = importlib.util.spec_from_file_location("sbpop", adir / "spreadsheetbench/adapter.py"); ad = importlib.util.module_from_spec(spec); spec.loader.exec_module(ad)
cmp = ad._Vendor.get()["compare_workbooks"]
ds = json.load(open(data / "dataset.json")); tmp = Path(tempfile.mkdtemp(prefix="pop_"))
def one(e):
    sid = str(e["id"]); d = data / "spreadsheet" / sid; out = {"task": sid, "cases": []}
    for idx in ad._case_indices(d, sid):
        g = ad._resolve_case_file(d, idx, sid, "answer"); rec = {"case": idx, "gold_exists": g.exists()}
        try: rec["A"] = bool(cmp(str(g), str(g), e["instruction_type"], e["answer_position"])[0])
        except Exception as ex: rec["A"] = False; rec["A_err"] = type(ex).__name__
        if soffice and g.exists():
            c = tmp / f"{sid}_{idx}.xlsx"; shutil.copyfile(g, c)
            rec["recalc_ok"] = ad._recalc_workbook(c, soffice)
            try: rec["B"] = bool(cmp(str(g), str(c), e["instruction_type"], e["answer_position"])[0])
            except Exception: rec["B"] = False
            c.unlink(missing_ok=True)
        out["cases"].append(rec)
    return out
with ThreadPoolExecutor(int(os.environ.get("POP_WORKERS", "24"))) as ex: res = list(ex.map(one, ds))
tot = sum(len(r["cases"]) for r in res)
A_fail = [r["task"] for r in res if any(not c["A"] for c in r["cases"])]
summ = {"data": str(data), "n_tasks": len(res), "n_cases": tot, "A_tasks_with_any_case_failing": len(A_fail), "A_failing_tasks": A_fail[:40]}
if soffice:
    B_fail = [r["task"] for r in res if any(not c.get("B", False) for c in r["cases"])]
    rf = [r["task"] for r in res if any(not c.get("recalc_ok", True) for c in r["cases"])]
    summ.update({"soffice": soffice, "B_tasks_with_any_case_failing": len(B_fail), "B_failing_tasks_sample": B_fail[:40], "recalc_process_failures": len(rf)})
json.dump({"summary": summ, "results": res}, open(outp, "w"))
print(json.dumps(summ, indent=1))
