#!/usr/bin/env python3
"""watch_queue.py: median gateway queue_s of gpt-oss calls over the last N minutes (tags FINAL-B/C only).  Rule (coordinator 2026-10-12): if the median
exceeds 60 s during the B window, rebalance --class-caps using the measured slot hold time (restart run_final.py; finished jobs are kept).  Default is hl=24,default=12."""
import argparse, datetime as dt, json, statistics as st, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import fe_common as C
ap = argparse.ArgumentParser(); ap.add_argument("--minutes", type=int, default=10); ap.add_argument("--tag", default="FINAL-B"); ap.add_argument("--model", default="gpt-oss")
a = ap.parse_args()
cut = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=a.minutes)
q = []
with open(C.SCRATCH / "logs" / "gateway_calls.jsonl", "rb") as f:
    f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 60_000_000)); f.readline()
    for line in f:
        try:
            d = json.loads(line)
            t = dt.datetime.strptime(d["t"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        except Exception:
            continue
        if t >= cut and a.model in str(d.get("model", "")) and (not a.tag or a.tag in str(d.get("tag", ""))) and d.get("queue_s") is not None:
            q.append(float(d["queue_s"]))
if not q:
    print("no matching calls"); sys.exit(0)
med = st.median(q)
print("calls %d  median queue_s %.1f  p90 %.1f  -> %s" % (len(q), med, sorted(q)[int(.9 * len(q)) - 1], "REBALANCE class caps (median queue > 60 s)" if med > 60 else "ok (keep hl=24,default=12)"))
