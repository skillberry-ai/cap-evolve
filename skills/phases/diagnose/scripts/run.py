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
    # ``tag`` may be a comma-separated list: pooled evidence (e.g. every seed-equivalent run).
    for f in sorted(g for t in tag.split(",") for g in vdir.glob(f"*__{t.strip()}__t*.json")):
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


def failure_clustering_enabled(run_dir, project: str | None) -> bool:
    """``optimizer.ablation.failure_clustering`` (default on). Unreadable spec => on."""
    from cap_evolve.optimizer_config import enabled
    try:
        from cap_evolve.specfile import spec_for_run
        spec = spec_for_run(run_dir, Path(project) if project else None)
    except Exception:  # noqa: BLE001
        spec = {}
    return enabled("failure_clustering", spec)


def first_n_words_signature(feedback: str, n: int = 6) -> str:
    """Legacy lexical clustering key (opt-in via ``--cluster first-words``)."""
    return " ".join((feedback or "").split()[:n]) or "unknown"


def diagnose(records: list[dict], mode: str = "root-cause",
             traces: str | None = None) -> dict:
    reflective = []
    items: list[tuple[str, str, float]] = []
    narrated: list[tuple[str, str, float]] = []
    kept = []
    trials: list[dict] = []
    totals: dict[str, int] = defaultdict(int)
    for rec in records:
        totals[str(rec.get("score", {}).get("task_id"))] += 1
        sc = rec.get("score", {})
        ro = rec.get("rollout", {})
        reward = sc.get("reward", 0) or 0
        if reward >= 1.0:
            kept.append(sc.get("task_id"))
            continue
        fb = sc.get("feedback", "") or ""
        # Mechanical, trace-derived, and benchmark-agnostic — see cluster.narrated_without_action.
        flagged = _cluster.narrated_without_action(ro)
        reflective.append({
            "task_id": sc.get("task_id"),
            # The actual task INPUT (carried through the rollout file), NOT the id.
            "Inputs": rec.get("input"),
            "Generated Outputs": ro.get("output"),
            "Feedback": fb,
            # Where the FULL trace is. A path, not parsed content: the format is the
            # runner's business and the adapter's to expose.
            "Trajectory": traces or rec.get("__file"),
            _cluster.NARRATED_WITHOUT_ACTION: flagged,
        })
        trials.append({"task_id": str(sc.get("task_id")), "feedback": fb,
                       "lost": max(0.0, 1.0 - float(reward)), "rollout": ro,
                       "trace_id": Path(rec.get("__file") or "").stem or None})
        row = (sc.get("task_id"), fb, max(0.0, 1.0 - float(reward)))
        (narrated if flagged else items).append(row)

    if mode == "v2":
        # Pooled, tool-error-aware, with kind/headroom; narrated trials stay their own cluster.
        return {"reflective_dataset": reflective, "kept_good": kept,
                "clusters": _cluster.cluster_v2(trials, len(totals), dict(totals))}
    if mode == "per-task":      # ablation failure_clustering=false: no grouping at all
        by_task: dict[str, float] = defaultdict(float)
        for t in trials:
            by_task[t["task_id"]] += t["lost"]
        clusters = [{"signature": f"task {k}", "tasks": [k], "score_lost": round(v, 4),
                     "tag": None, "blast_radius": None} for k, v in sorted(by_task.items())]
        return {"reflective_dataset": reflective, "clusters": clusters, "kept_good": kept}
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

    # Its own named cluster, never folded into a lexical one: the scorer's wording for
    # "narrated a change it never made" is the same wording it uses for a wrong write, so
    # merging them sends the optimizer to fix the arguments of a call that never happened.
    if narrated:
        clusters.append({
            "signature": _cluster.NARRATED_WITHOUT_ACTION,
            "tasks": sorted(t for t, _, _ in narrated),
            "score_lost": round(sum(sl for _, _, sl in narrated), 4),
            "detector": "mechanical: completion language in the final message, no mutating "
                        "tool call anywhere in the trace",
            "reading": "the agent treated its own completion signal (typically the user's "
                       "confirmation) as the action and narrated the change instead of "
                       "executing it. A prose reminder to call the tool does not fix this; "
                       "the fix is structural — make 'confirmed' and 'executed' the same "
                       "call, so no code path can reach one without the other.",
            "tag": None,
            "blast_radius": None,
        })
        clusters.sort(key=lambda c: (-c["score_lost"], -len(c["tasks"]), c["signature"]))

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
                   choices=["auto", "root-cause", "first-words", "v2", "per-task"],
                   help="failure-clustering method (root-cause: site+expectation key; v2: + "
                        "tool-error signature, pooled trials, kind/headroom; per-task: no "
                        "grouping). Default is the legacy root-cause; auto = v2 unless optimizer.ablation.failure_clustering "
                        "is false in the project spec (then per-task)")
    args = p.parse_args(argv)
    run_dir = RunDir.open(Path(args.run_dir))
    mode = args.cluster
    if mode == "auto":
        mode = "v2" if failure_clustering_enabled(run_dir, args.project) else "per-task"
    result = diagnose(_load_records(run_dir, args.tag, args.split),
                      mode, trace_dir(args.project, args.split))
    result["split"] = args.split
    result["tag"] = args.tag
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
