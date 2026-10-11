#!/usr/bin/env python3 -I
"""make_agent_view.py <gold_data_dir> <view_dir>

Build the directory that is mounted INTO the agent's sandbox: dataset.json + each task's INPUT
workbooks (+ prompt.txt where the release ships one) + an empty, writable outputs/. Every
answer/golden workbook is left out, so agent-generated code can neither read nor overwrite the gold.
The scorer reads gold from the separate, read-only tree via SPREADSHEETBENCH_GOLD_DIR."""
import os, re, shutil, sys
src, dst = sys.argv[1], sys.argv[2]
if os.path.exists(dst): shutil.rmtree(dst)
os.makedirs(dst)
GOLD = re.compile(r"(_answer|_golden|^golden|^answer)", re.I)
shutil.copy2(os.path.join(src, "dataset.json"), dst)
n = kept = skipped = 0
for sid in sorted(os.listdir(os.path.join(src, "spreadsheet"))):
    sd = os.path.join(src, "spreadsheet", sid); dd = os.path.join(dst, "spreadsheet", sid); os.makedirs(dd)
    for f in sorted(os.listdir(sd)):
        if GOLD.search(f): skipped += 1; continue
        shutil.copy2(os.path.join(sd, f), os.path.join(dd, f)); kept += 1
    n += 1
os.makedirs(os.path.join(dst, "outputs")); os.chmod(os.path.join(dst, "outputs"), 0o777)
for dp, dn, fn in os.walk(dst):
    os.chmod(dp, 0o755) if dp != os.path.join(dst, "outputs") else None
print(f"tasks={n} input files kept={kept} gold files withheld={skipped} -> {dst}")
