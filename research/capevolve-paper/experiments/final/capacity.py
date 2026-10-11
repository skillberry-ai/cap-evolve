#!/usr/bin/env python3
"""capacity.py: rollouts and wall clock of the final evaluation at current throughput (stdlib; reads analysis/out/metrics/rollout_metrics.csv).

    capacity.py [--TA 70 --TB 40 --TC 20] [--start 2026-10-13T06:30:00Z]

Throughput inputs (decisions.md): Gemma-4-31B (Suite A) 185-300 rollouts/h; gpt-oss-120b 127 calls/min shared by Suites B and C (and by any
simulator/target call), so B and C add up, while A (Gemma) runs concurrently with them.  Calls per rollout are measured from the search-time
rollout records (main + chaser rows).  Hard stop = 72 h after start (2026-10-14 07:00 UTC); analysis wants the data by 2026-10-14 00:05.
"""
import argparse
import csv
import datetime as dt
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fe_common as C  # noqa: E402

M = C.PAPER / "analysis/out/metrics/rollout_metrics.csv"


def num(x):
    try:
        return float(x)
    except Exception:
        return None


def measured():
    rows = list(csv.DictReader(open(M)))
    out = {}
    for s in "BC":
        rs = [r for r in rows if r["suite"] == s and r["category"] in ("main", "chaser_eval")]
        tg = [num(r["n_target_calls"]) for r in rs if num(r["n_target_calls"]) is not None]
        us = [num(r["n_usersim_calls"]) for r in rs if num(r["n_usersim_calls"]) is not None]
        w = [num(r["wall_s"]) for r in rs if num(r["wall_s"]) is not None]
        out[s] = {"oss_calls_per_rollout": st.mean(tg) + st.mean(us), "median_wall_s": st.median(w), "n_records": len(rs)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--TA", type=int, default=70)
    ap.add_argument("--TB", type=int, default=40)
    ap.add_argument("--TC", type=int, default=20)
    ap.add_argument("--end-distinct", type=float, default=0.5, help="fraction of (arm,seed) cells whose end-of-run artifact differs from the B* one")
    ap.add_argument("--start", default="2026-10-13T06:30:00Z")
    a = ap.parse_args()
    m = measured()
    start = dt.datetime.strptime(a.start, "%Y-%m-%dT%H:%M:%SZ")
    stop = dt.datetime(2026, 10, 14, 7, 0, 0)
    want = dt.datetime(2026, 10, 14, 0, 5, 0)
    avail_h = (want - start).total_seconds() / 3600
    hard_h = (stop - start).total_seconds() / 3600
    # cells: A 7 main + 3 cheap = 10 arms x 3 seeds; B hc ao gepa harnesslens x3 + oneshot x3; C hc ao gepa x3 + oneshot x3
    cells = {"A": 30, "B": 15, "C": 12}
    T = {"A": a.TA, "B": a.TB, "C": a.TC}
    n_arm = {"A": 1, "B": 2, "C": 3}
    n_seed = {"A": 2, "B": 2, "C": 3}
    res = {}
    for s in "ABC":
        prim = cells[s] * T[s] * n_arm[s]
        end = int(round((cells[s] - (3 if s != "A" else 0)) * a.end_distinct)) * T[s] * n_arm[s]
        seed = T[s] * n_seed[s] + (T[s] * n_seed[s] if s == "B" else 0)       # B also scores HarnessLens's own v0 harness
        canary = int(avail_h) * 5
        res[s] = {"primary": prim, "end_artifacts": end, "seed_and_v0": seed, "canary": canary, "total": prim + end + seed + canary}
    out = {"inputs": {"measured": m, "T": T, "trials_arm": n_arm, "trials_seed": n_seed, "end_distinct_fraction": a.end_distinct, "window_to_0005_h": round(avail_h, 1), "window_to_hard_stop_h": round(hard_h, 1)}}
    for lo_hi, ra in (("pessimistic", 185.0), ("optimistic", 300.0)):
        h = {"A": res["A"]["total"] / ra}
        oss_per_h = 127 * 60
        for s in "BC":
            h[s] = res[s]["total"] * m[s]["oss_calls_per_rollout"] / oss_per_h
        h["B+C (share gpt-oss)"] = h["B"] + h["C"]
        h["critical path (A || B+C)"] = max(h["A"], h["B+C (share gpt-oss)"])
        out[lo_hi] = {k: round(v, 1) for k, v in h.items()}
    out["rollouts"] = res
    out["verdict"] = {"fits_before_0005": out["pessimistic"]["critical path (A || B+C)"] <= avail_h, "fits_before_hard_stop": out["pessimistic"]["critical path (A || B+C)"] <= hard_h}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
