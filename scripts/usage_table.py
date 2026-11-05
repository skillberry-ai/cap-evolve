#!/usr/bin/env python3
"""Measured usage per search and per test window, from the metering-gateway ledgers (run on an LSF node).

Writes runs/.watch/usage_table.json: for each <arm>|<seed>, the search's and the test window's
  calls, prompt tokens, completion tokens (agent = Gemma, optimizer = GLM), and wall time.
Tokens only: no price list exists for these endpoints, so no dollar figure is computed. Retry rows are skipped
(they repeat a call), and only 200 replies carry token counts. Wall time is the sum of each job's start..end in
run_meta.txt; for CapEvolve and resumed jobs there can be several segments.
"""
import json, re, sys
from datetime import datetime
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
ARMS = ["capevolve", "capevolve_v2", "skillopt", "trace2skill", "meta_harness", "evoskill", "gepa", "gepa_full", "miprov2", "wikiskill", "ace"]


def ledger(path: Path) -> dict:
    out = {"calls": 0, "ok": 0, "prompt": 0, "completion": 0, "cached": 0}
    if not path.exists():
        return out
    with path.open() as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("event"):          # retry rows, guard rows
                continue
            out["calls"] += 1
            if r.get("status") == 200:
                out["ok"] += 1
                out["prompt"] += int(r.get("prompt_total") or r.get("prompt_tokens") or 0)
                out["completion"] += int(r.get("completion_tokens") or 0)
                out["cached"] += int(r.get("cached_tokens") or 0)
    return out


def wall_hours(meta: Path):
    if not meta.exists():
        return None
    t = meta.read_text(errors="ignore")
    starts = [datetime.fromisoformat(s.replace("Z", "+00:00")) for s in re.findall(r"start=(\S+Z)", t)]
    ends = [datetime.fromisoformat(s.replace("Z", "+00:00")) for s in re.findall(r"^end=(\S+Z)", t, re.M)]
    if not starts or not ends:
        return None
    # pair each start with the first end after it (resumed jobs append a new start/end pair)
    tot, ei = 0.0, 0
    for s in starts:
        nxt = [e for e in ends if e >= s]
        if nxt:
            tot += (min(nxt) - s).total_seconds()
    return round(tot / 3600, 2)


res = {}
for arm in ARMS:
    for s in (0, 1, 2):
        run = EXP / "runs" / arm / f"search_s{s}"
        gw = EXP / "runs" / "test" / f".gw_{arm}_s{s}"
        tw = EXP / "runs" / "test" / f"{arm}_s{s}" / "results.jsonl"
        test_wall = None
        if tw.exists():
            ts = [json.loads(l)["t_end"] for l in tw.read_text().splitlines() if l.strip()]
            ws = [json.loads(l)["wall_s"] for l in tw.read_text().splitlines() if l.strip()]
            test_wall = round((max(ts) - min(ts) + max(ws)) / 3600, 2) if ts else None
        res[f"{arm}|{s}"] = {
            "search_agent": ledger(run / "calls_gemma.jsonl"),
            "search_optimizer": ledger(run / "calls_glm.jsonl"),
            "search_wall_h": wall_hours(run / "run_meta.txt"),
            "test_agent": ledger(gw / "calls_gemma.jsonl"),
            "test_wall_h": test_wall,
        }
        print(arm, s, res[f"{arm}|{s}"]["search_optimizer"]["completion"], res[f"{arm}|{s}"]["search_wall_h"], test_wall, flush=True)
(EXP / "runs/.watch/usage_table.json").write_text(json.dumps(res, indent=1))
print("WROTE", len(res))
