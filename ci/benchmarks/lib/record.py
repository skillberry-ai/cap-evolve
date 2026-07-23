#!/usr/bin/env python3
"""Build & aggregate benchmark-history records for the CI history page.

  record.py build <metrics.jsonl> --runmeta <runmeta.json>   # -> record JSON on stdout
  record.py aggregate <records_dir> --now <iso> --out <dir>  # -> benchmarks.json + meta.json

One record per (run x benchmark): the run metadata (from runmeta.json) merged with the
per-task rows (from the suite's metrics.jsonl) plus a suite rollup. The aggregate step
concatenates all committed records into benchmarks.json (newest first) for the Pages page.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA = 1


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def rollup(tasks: list[dict]) -> dict | None:
    """Suite rollup matching metrics.py table(): mean rewards, flip count, n, optimizer $."""
    rb = [t["reward_baseline"] for t in tasks if _num(t.get("reward_baseline"))]
    ro = [t["reward_opt"] for t in tasks if _num(t.get("reward_opt"))]
    if not (rb and ro):
        return None
    return {
        "reward_base": round(sum(rb) / len(rb), 6),
        "reward_opt": round(sum(ro) / len(ro), 6),
        "flips": sum(1 for t in tasks if t.get("flipped")),
        "n": len(tasks),
        "optimizer_usd": round(sum(t.get("optimizer_usd") or 0 for t in tasks), 6),
    }


def build_record(metrics_jsonl: Path, runmeta: dict) -> dict:
    tasks: list[dict] = []
    if metrics_jsonl.exists():
        for line in metrics_jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                tasks.append(json.loads(line))
    rec = dict(runmeta)
    rec["schema"] = SCHEMA
    rec["tasks"] = tasks
    rec["suite"] = rollup(tasks) if runmeta.get("conclusion") == "success" else None
    return rec


def aggregate(records_dir: Path, now: str) -> tuple[list[dict], dict]:
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(records_dir.glob("*.json"))]
    recs.sort(key=lambda r: (r.get("date", ""), r.get("run_id", 0)), reverse=True)
    meta = {"count": len(recs), "runs": len({r.get("run_id") for r in recs}), "updated": now}
    return recs, meta


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("metrics")
    b.add_argument("--runmeta", required=True)
    a = sub.add_parser("aggregate")
    a.add_argument("records_dir")
    a.add_argument("--now", required=True)
    a.add_argument("--out", required=True)
    ns = ap.parse_args(argv[1:])

    if ns.cmd == "build":
        runmeta = json.loads(Path(ns.runmeta).read_text(encoding="utf-8"))
        print(json.dumps(build_record(Path(ns.metrics), runmeta)))
        return 0
    if ns.cmd == "aggregate":
        recs, meta = aggregate(Path(ns.records_dir), ns.now)
        out = Path(ns.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "benchmarks.json").write_text(json.dumps(recs, indent=2), encoding="utf-8")
        (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
