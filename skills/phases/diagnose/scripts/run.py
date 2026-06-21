"""diagnose — turn rollouts/scores into an actionable learning signal.

Reads the most recent val rollouts for a candidate from the run dir and emits a
reflective dataset: per failing task ``{task_id, Inputs, Generated Outputs,
Feedback}`` (GEPA's shape) plus failure clusters. The algorithm/optimizer consume
this to know WHAT to change and WHY — the textual analogue of a gradient (GEPA's
Actionable Side Information).

Two fixes over the prior version:
  * ``Inputs`` carries the actual task INPUT recorded in the rollout file (it used
    to wrongly carry the task id), so the optimizer sees what the task asked for.
  * clustering is pluggable (``--cluster`` / ``CLUSTER_FNS``); the default is a
    normalized-feedback signature (lowercased, digits/punct/quoted-literals
    stripped), which groups "Expected 5 got 7" and "Expected 9 got 2" together
    instead of splitting on the first 6 words.
"""

from __future__ import annotations

import argparse
import json
import re
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


def normalized_feedback_signature(feedback: str) -> str:
    """Default clustering key: feedback with case/digits/punctuation removed.

    Collapses task-specific values (numbers, ids, quoted strings) so failures that
    share a root cause but differ in particulars land in the same cluster.
    """
    s = (feedback or "").lower()
    s = re.sub(r"['\"`].*?['\"`]", " ", s)        # drop quoted literals
    s = re.sub(r"[0-9]+", " ", s)                  # drop numbers
    s = re.sub(r"[^a-z ]+", " ", s)                # drop punctuation
    toks = [t for t in s.split() if len(t) > 2]
    return " ".join(toks[:8]) or "unknown"


def first_n_words_signature(feedback: str, n: int = 6) -> str:
    """Legacy clustering key (kept for comparison / opt-in)."""
    return " ".join((feedback or "").split()[:n]) or "unknown"


CLUSTER_FNS = {
    "normalized-feedback": normalized_feedback_signature,
    "first-words": first_n_words_signature,
}


def diagnose(records: list[dict], cluster_fn=normalized_feedback_signature) -> dict:
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
            # The actual task INPUT (carried through the rollout file), NOT the id.
            "Inputs": rec.get("input"),
            "Generated Outputs": ro.get("output"),
            "Feedback": fb,
        })
        clusters[cluster_fn(fb)].append(sc.get("task_id"))
    return {
        "reflective_dataset": reflective,
        "clusters": [{"signature": k, "tasks": v}
                     for k, v in sorted(clusters.items(), key=lambda kv: -len(kv[1]))],
        "kept_good": kept,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="diagnose")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--tag", default="seed", help="candidate tag whose val rollouts to read")
    p.add_argument("--cluster", default="normalized-feedback", choices=sorted(CLUSTER_FNS),
                   help="failure-clustering function")
    args = p.parse_args(argv)
    run_dir = RunDir.open(Path(args.run_dir))
    result = diagnose(_load_val_records(run_dir, args.tag), CLUSTER_FNS[args.cluster])
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
