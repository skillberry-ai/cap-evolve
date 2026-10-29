#!/usr/bin/env python3
"""R4E1E6 results expansion (amendment 12 erratum 122). Written and registered BEFORE the window ends.
The order scores each unique tree ONCE. The registered analysis design (design_R4E1E6.json) names cells by several labels (E1 incumbent labels, E6 chain labels, GATE-K2-s0/s1/s3).
This script copies results_long.csv and results_trials.csv of the window into new files in which a cell that has several design names appears once under EACH name,
using only (a) the order's meta.cell_map (35 labels -> 30 cells) and (b) three registered aliases GATE-K2-s0 -> E6-K2s0-0014, GATE-K2-s1 -> E6-K2s1-0013, GATE-K2-s3 -> E6-K2s3-0011.
It changes no value. A label whose target cell has no rows is an error. Output arm names are 'LABEL' with seed 0 for labels of the form LABEL/s0; the SkillOpt cells (skillopt, seeds 0 to 2), seed and seed-check are copied as they are.
    python3 -I expand_r4e1e6.py ORDER_JSONL RESULTS_ROOT OUT_ROOT
"""
import csv, json, os, shutil, sys
ORDER, ROOT, OUT = sys.argv[1:4]
meta = json.loads(open(ORDER).readline())
cm = dict(meta["cell_map"])
ALIAS = {"GATE-K2-s0": "E6-K2s0-0014", "GATE-K2-s1": "E6-K2s1-0013", "GATE-K2-s3": "E6-K2s3-0011"}
for k, v in ALIAS.items():
    assert k not in cm or cm[k] == v, (k, cm.get(k)); cm[k] = v
os.makedirs(OUT, exist_ok=True)
for name in ("results_long.csv", "results_trials.csv"):
    rows = list(csv.DictReader(open(os.path.join(ROOT, name)))); fields = list(rows[0].keys())
    by = {}
    for r in rows: by.setdefault(r["arm"], []).append(r)
    out = list(rows)
    for lab, tgt in cm.items():
        if lab == tgt: continue
        if tgt not in by: raise SystemExit(f"{name}: target cell {tgt!r} of label {lab!r} has no rows; cells present: {sorted(by)}")
        for r in by[tgt]:
            r2 = dict(r); r2["arm"] = lab; out.append(r2)
    with open(os.path.join(OUT, name), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(out)
    print(name, len(rows), "->", len(out), "rows;", len(by), "cells ->", len({r["arm"] for r in out}), "names")
for f in os.listdir(ROOT):
    if f in ("results_long.csv", "results_trials.csv"): continue
    p = os.path.join(ROOT, f)
    if os.path.isfile(p) and f in ("per_arm_report.json",): shutil.copy(p, os.path.join(OUT, f))
