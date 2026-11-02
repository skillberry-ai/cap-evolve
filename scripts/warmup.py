#!/usr/bin/env python3
"""Pre-warm the Gemma route before a search (exp895). Not part of any arm's budget.

Every run so far stalled on its FIRST burst of agent calls (all calls issued at t+0 timed out, then answered
on retry), and never later in the same run. This sends one burst shaped like real first agent turns
(~1.2k-token prompt, temperature 0, a `seed`, same concurrency) through the gateway under the tag
`<exp>-warmup:target`, and waits for all of it. The ledger then shows whether the warm-up absorbed the stall.

Usage: warmup.py <concurrency> <api_base_without_tag>   e.g. warmup.py 10 http://127.0.0.1:4113
"""
import concurrent.futures as cf
import json
import sys
import time
import urllib.request

n, base = int(sys.argv[1]), sys.argv[2].rstrip("/")
prompt = ("You are a spreadsheet agent. Write Python that opens /mnt/data/input.xlsx with openpyxl, "
          "finds the header row and prints the column names. ") * 40


def one(i):
    body = {"model": "x", "temperature": 0.0, "seed": i, "max_tokens": 64,
            "messages": [{"role": "system", "content": "Answer with Python code only."},
                         {"role": "user", "content": prompt + f"\n[warmup {i}]"}]}
    req = urllib.request.Request(f"{base}/t/exp895-warmup:target/v1/chat/completions",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            return r.status, round(time.time() - t0, 1)
    except Exception as e:  # noqa: BLE001
        return type(e).__name__, round(time.time() - t0, 1)


t0 = time.time()
with cf.ThreadPoolExecutor(n) as ex:
    res = list(ex.map(one, range(n)))
print("WARMUP", json.dumps({"n": n, "wall_s": round(time.time() - t0, 1), "status": [r[0] for r in res],
                            "latency_s": sorted(r[1] for r in res)}), flush=True)
