"""diagnose — turn rollouts/scores into an actionable learning signal.

Reads a candidate's persisted rollouts for one split and emits the reflective
dataset (per failing task ``{task_id, Inputs, Generated Outputs, Feedback,
Trajectory}`` — GEPA's shape) plus failure clusters ranked by score lost, plus
``kept_good``. The algorithm/optimizer consume this to know WHAT to change and WHY.

Trace access is schema-agnostic by construction. The rollout record (a cap-evolve
core format) supplies the score and the feedback; the full trace lives wherever the
RUNNER puts it, so its location comes from ``adapter.trajectories(split)`` and is
attached as a PATH only — this script never parses a runner's trace format. With no
``--project``, or when the adapter has no native trajectory store, the pointer falls
back to the rollout record's own file, which core wrote and therefore owns.

Clustering is deterministic and lives in ``cluster.py``; see its docstring for the
(site, expectation) signature. ``--cluster first-words`` keeps the old lexical key
available for comparison.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import _bootstrap  # noqa: F401

import cluster as _cluster

from cap_evolve import RunDir


def _load_records(run_dir: RunDir, tag: str, split: str = "val") -> list[dict]:
    """Every persisted rollout for ``tag`` on ``split``, each tagged with its path.

    ``split`` exists because TRAIN is the honest surface to diagnose from: val is what
    the gate scores, so reading the learning signal off val and then gating on val
    fits the split you are being judged on. Hardcoding "val" here made train-based
    diagnosis unreachable for every caller.
    """
    out = []
    vdir = run_dir.rollouts / split
    if not vdir.exists():
        return out
    for f in sorted(vdir.glob(f"*__{tag}__t*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        rec["__file"] = str(f)
        out.append(rec)
    return out


def trace_dir(project: str | None, split: str) -> str | None:
    """The runner's native trajectory directory, via the adapter — never guessed.

    Returns ``None`` when there is no project to load or the adapter declares no
    native store (the documented default); callers then fall back to the per-rollout
    record. Any adapter failure is non-fatal: a missing trace pointer must not stop a
    diagnosis that the rollouts alone can still produce.
    """
    if not project:
        return None
    try:
        from cap_evolve.check import load_adapter
        d = load_adapter(Path(project)).trajectories(split)
        return str(d) if d else None
    except Exception:  # noqa: BLE001
        return None


def first_n_words_signature(feedback: str, n: int = 6) -> str:
    """Legacy lexical clustering key (opt-in via ``--cluster first-words``)."""
    return " ".join((feedback or "").split()[:n]) or "unknown"


def diagnose(records: list[dict], mode: str = "root-cause",
             traces: str | None = None) -> dict:
    reflective = []
    items: list[tuple[str, str, float]] = []
    kept = []
    for rec in records:
        sc = rec.get("score", {})
        ro = rec.get("rollout", {})
        reward = sc.get("reward", 0) or 0
        if reward >= 1.0:
            kept.append(sc.get("task_id"))
            continue
        fb = sc.get("feedback", "") or ""
        reflective.append({
            "task_id": sc.get("task_id"),
            # The actual task INPUT (carried through the rollout file), NOT the id.
            "Inputs": rec.get("input"),
            "Generated Outputs": ro.get("output"),
            "Feedback": fb,
            # Where the FULL trace is. A path, not parsed content: the format is the
            # runner's business and the adapter's to expose.
            "Trajectory": traces or rec.get("__file"),
        })
        items.append((sc.get("task_id"), fb, max(0.0, 1.0 - float(reward))))

    if mode == "first-words":
        groups = defaultdict(list)
        lost = defaultdict(float)
        for tid, fb, sl in items:
            k = first_n_words_signature(fb)
            groups[k].append(tid)
            lost[k] += sl
        clusters = [{"signature": k, "tasks": sorted(v),
                     "score_lost": round(lost[k], 4), "tag": None, "blast_radius": None}
                    for k, v in groups.items()]
        clusters.sort(key=lambda c: (-c["score_lost"], -len(c["tasks"]), c["signature"]))
    else:
        clusters = _cluster.cluster(items)

    return {
        "reflective_dataset": reflective,
        "clusters": clusters,
        "kept_good": kept,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="diagnose")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--tag", default="seed", help="candidate tag whose rollouts to read")
    p.add_argument("--project", default=None,
                   help="project dir — resolves the runner's native trace dir via "
                        "adapter.trajectories(split); optional")
    p.add_argument("--split", default="val", choices=["train", "val"],
                   help="which split's rollouts to diagnose (train is the honest "
                        "learning surface; val is what the gate scores)")
    p.add_argument("--cluster", default="root-cause",
                   choices=["root-cause", "first-words"],
                   help="failure-clustering method (root-cause: site+expectation key)")
    args = p.parse_args(argv)
    run_dir = RunDir.open(Path(args.run_dir))
    result = diagnose(_load_records(run_dir, args.tag, args.split),
                      args.cluster, trace_dir(args.project, args.split))
    result["split"] = args.split
    result["tag"] = args.tag
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
