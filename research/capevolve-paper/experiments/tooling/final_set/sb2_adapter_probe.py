#!/usr/bin/env python3
"""Can the CapEvolve SpreadsheetBench adapter run SB2 as-is? Zero LLM. Also measures the first-prompt size the
adapter would send (instruction + workbook preview), per category."""
import importlib.util, json, os, statistics as st, sys, types
from pathlib import Path
root = Path(sys.argv[1]); REPO = Path("/home/dev/projects2/cap-evolve-campaign")
for k in list(os.environ):
    if k.startswith("SPREADSHEETBENCH_"): del os.environ[k]
sys.path[:0] = [str(REPO / "core"), str(REPO / "templates/adapters/spreadsheetbench"), str(REPO / "templates/adapters")]
os.environ["SPREADSHEETBENCH_HARNESS_DIR"] = str(REPO / "third_party/spreadsheetbench"); os.environ["SPREADSHEETBENCH_ALLOW_GOLD_IN_MOUNT"] = "1"; os.environ["SPREADSHEETBENCH_AGENT_VIEW"] = "0"
out = {}
for cat in ("Debugging", "Financial_Model", "Template"):
    os.environ["SPREADSHEETBENCH_DATA_DIR"] = str(root / cat)
    spec = importlib.util.spec_from_file_location("sbp_" + cat, REPO / "templates/adapters/spreadsheetbench/adapter.py")
    ad = importlib.util.module_from_spec(spec); spec.loader.exec_module(ad)
    r = {}
    try:
        ad.Adapter().tasks("test"); r["tasks()"] = "ok"
    except Exception as e:
        r["tasks()"] = f"{type(e).__name__}: {e}"
    ds = json.load(open(root / cat / "dataset.json"))
    chars, nsheets, errs = [], [], 0
    for e in ds:
        p = root / cat / e["spreadsheet_path"]
        try:
            pv = ad._spreadsheet_preview(p, 5)
        except Exception as ex:
            pv = ""; errs += 1
        chars.append(len(e["instruction"]) + len(pv) + len(e["answer_position"]) + 1500)   # +1500: task template + system prompt
    r["prompt_chars_median"] = int(st.median(chars)); r["prompt_chars_p90"] = int(sorted(chars)[int(.9 * len(chars))]); r["prompt_chars_max"] = max(chars)
    r["approx_prompt_tokens_median"] = r["prompt_chars_median"] // 4; r["approx_prompt_tokens_p90"] = r["prompt_chars_p90"] // 4
    r["preview_errors"] = errs
    r["answer_position_chars_median"] = int(st.median(len(e["answer_position"]) for e in ds))
    out[cat] = r
print(json.dumps(out, indent=1))
json.dump(out, open(sys.argv[2], "w"), indent=1)
