#!/usr/bin/env python3
"""No-LLM probe of the real adapter sandbox: starts the vendored Jupyter-gateway server, mints a container via
the docker API (podman here), runs code in it. Verifies mount layout, gold visibility and write-ability."""
import importlib.util, json, os, sys, uuid
from pathlib import Path
REPO = Path("/home/dev/projects2/cap-evolve-campaign"); BENCH = Path("/home/dev/projects2/campaign-scratch/bench")
mode, data, tid = sys.argv[1], sys.argv[2], sys.argv[3]       # mode: historical|isolated
os.environ["SPREADSHEETBENCH_HARNESS_DIR"] = str(REPO / "third_party/spreadsheetbench"); os.environ["SPREADSHEETBENCH_DATA_DIR"] = data
adapter = REPO / "templates/adapters/spreadsheetbench/adapter.py" if mode == "historical" else BENCH / "patches/new/adapter.py"
sys.path.insert(0, str(adapter.parent)); sys.path.insert(0, str(REPO / "templates/adapters")); sys.path.insert(0, str(REPO / "core"))
spec = importlib.util.spec_from_file_location("sbp", adapter); ad = importlib.util.module_from_spec(spec); spec.loader.exec_module(ad)
ad._preflight_mount(ad._data_dir())
sb = ad._get_sandbox(); conv = ad._sanitize_conv_id("probe-" + uuid.uuid4().hex[:6])
code = f'''
import os, glob
d="/mnt/data/spreadsheet/{tid}"
print("LISTING", sorted(os.listdir(d)))
print("GOLD_VISIBLE", [f for f in os.listdir(d) if "answer" in f or "golden" in f])
tgt=[f for f in os.listdir(d) if "answer" in f or "golden" in f]
if tgt:
    try:
        open(os.path.join(d,tgt[0]),"ab").close(); print("GOLD_WRITABLE_BY_AGENT_CODE", True)
    except Exception as e: print("GOLD_WRITABLE_BY_AGENT_CODE", False, type(e).__name__)
os.makedirs("/mnt/data/outputs/probe", exist_ok=True)
open("/mnt/data/outputs/probe/x.txt","w").write("ok"); print("OUTPUT_WRITE", True)
import openpyxl; print("openpyxl", openpyxl.__version__)
'''
try:
    print(sb.execute(conv, code))
finally:
    sb.release(conv); sb.shutdown()
