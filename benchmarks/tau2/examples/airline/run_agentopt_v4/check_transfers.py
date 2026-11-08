#!/usr/bin/env python3
"""Audit whether a candidate actually changed the behaviour it was aimed at.

v3's lesson was that a candidate can be *functionally identical* to the seed on the
split it is judged on (`c5_guards_only` added tool guards that never fired on any val
rollout), so its measured delta was noise attributed to an edit that never executed.
This script makes the equivalent check mechanical for v4's candidates, whose target is
the "abandon-on-partial-refusal" cluster: it counts, per val task and per trial, whether
``transfer_to_human_agents`` was called and whether any DB-writing tool was called.

    python check_transfers.py <run_dir> [tag ...]

An edit that leaves the transfer/write pattern byte-identical to the seed's on every val
task did not run, and its delta is not evidence about the edit.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

WRITES = {
    "book_reservation",
    "update_reservation_flights",
    "update_reservation_passengers",
    "update_reservation_baggages",
    "cancel_reservation",
    "send_certificate",
}


def audit(run_dir: Path, tags: list[str]) -> dict:
    out: dict = defaultdict(dict)
    for f in sorted((run_dir / "rollouts" / "val").glob("*__*__t*.json")):
        parts = f.name[: -len(".json")].split("__")
        task, tag, trial = parts[0], "__".join(parts[1:-1]), parts[-1]
        if tags and tag not in tags:
            continue
        rec = json.loads(f.read_text(encoding="utf-8"))
        trace = (rec.get("rollout") or {}).get("trace") or []
        names = [
            tc.get("name")
            for m in trace
            if isinstance(m, dict)
            for tc in (m.get("tool_calls") or [])
        ]
        out[tag].setdefault(task, []).append(
            {
                "trial": trial,
                "reward": (rec.get("score") or {}).get("reward"),
                "transferred": "transfer_to_human_agents" in names,
                "writes": sorted({n for n in names if n in WRITES}),
            }
        )
    return out


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    run_dir, tags = Path(argv[0]), argv[1:]
    data = audit(run_dir, tags)
    for tag in sorted(data):
        print(f"=== {tag}")
        for task in sorted(data[tag], key=int):
            rows = sorted(data[tag][task], key=lambda r: r["trial"])
            xfer = sum(1 for r in rows if r["transferred"])
            rew = [r["reward"] for r in rows]
            wr = sorted({w for r in rows for w in r["writes"]})
            print(f"  task {task:>3}  rewards={rew}  transferred {xfer}/{len(rows)}  writes={wr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
