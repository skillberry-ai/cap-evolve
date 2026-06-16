"""diagnose — turn rollouts/scores into an actionable learning signal.

Reads the most recent val rollouts for a candidate from the run dir, groups
failures by a coarse signature, and emits a reflective dataset: per failing task
{Inputs, Generated Outputs, Feedback} (gepa's shape) plus failure clusters. The
algorithm/optimizer consume this to know WHAT to change and WHY — the textual
analogue of a gradient (gepa's Actionable Side Information).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import RunDir


def _load_val_records(run_dir: RunDir, tag: str) -> list[dict]:
    out = []
    vdir = run_dir.rollouts / "val"
    if not vdir.exists():
        return out
    for f in sorted(vdir.glob(f"*__{tag}__t*.json")):
        out.append(json.loads(f.read_text(encoding="utf-8")))
    return out


def diagnose(records: list[dict]) -> dict:
    reflective = []
    clusters = defaultdict(list)
    kept = []
    for rec in records:
        sc = rec.get("score", {})
        ro = rec.get("rollout", {})
        if sc.get("reward", 0) >= 1.0:
            kept.append(sc.get("task_id"))
            continue
        fb = sc.get("feedback", "")
        reflective.append({
            "task_id": sc.get("task_id"),
            "Inputs": ro.get("task_id"),
            "Generated Outputs": ro.get("output"),
            "Feedback": fb,
        })
        # coarse signature = first 6 words of feedback
        sig = " ".join(fb.split()[:6]) or "unknown"
        clusters[sig].append(sc.get("task_id"))
    return {
        "reflective_dataset": reflective,
        "clusters": [{"signature": k, "tasks": v} for k, v in sorted(clusters.items(), key=lambda kv: -len(kv[1]))],
        "kept_good": kept,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="diagnose")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--tag", default="seed", help="candidate tag whose val rollouts to read")
    args = p.parse_args(argv)
    run_dir = RunDir.open(Path(args.run_dir))
    result = diagnose(_load_val_records(run_dir, args.tag))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
