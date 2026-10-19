"""Ablation switch ``abl_gate`` (none | disjoint): GATE-NONE and GATE-DISJOINT.

Spec keys (top level of capevolve.yaml, read with ``specfile.spec_for_run``)::

    abl_gate: none | disjoint
    abl_feedback_ids: [...]   # disjoint: the proposer sees these tasks (F)
    abl_gate_ids:     [...]   # disjoint: the gate decides on these tasks (G)

Absent key => every function here is a no-op and the stock path is untouched.

GATE-NONE      every scored, valid candidate is accepted; the stock decision is still computed and
               logged as ``abl_gate_shadow``.
GATE-DISJOINT  candidates are evaluated on ALL val tasks (cost matched); the gate (paired deltas,
               footprint, statistics, movement) sees only G; the proposer sees only F (failure index,
               protect block, trajectories, LEDGER/RUNMAP/JOURNAL lists and val/delta columns, and the
               rejected/history summaries). Gate reason strings are scrubbed of task-id lists.

Residual leakage in DISJOINT (by design, same as any gate): the accept/reject bit, the aggregate
paired delta / SE / k on G in the gate reason, and the fact that the accept bit is consistent with
the (visible) F-side traces. Nothing else about G is written to a proposer-readable file; the sandbox
must hide run_main/rollouts, native_sims, eval_index.jsonl, graph.jsonl (and events.jsonl, which keeps
full per-task detail for analysis).
"""

from __future__ import annotations

import re
from pathlib import Path

from . import specfile
from .loop import SplitResult, aggregate_scores
from .types import Score

MODES = (None, "none", "disjoint")


def _ids(v, key) -> list:
    if v is None:
        return []
    if not isinstance(v, (list, tuple)):
        raise ValueError(f"{key} must be a list of task ids, got {v!r}")
    return [str(x) for x in v]


def settings(run_dir) -> tuple:
    """``(mode, feedback_ids, gate_ids)``; ``(None, [], [])`` when the run has no ``abl_gate``."""
    spec = specfile.spec_for_run(run_dir) or {}
    mode = spec.get("abl_gate")
    if mode is not None:
        mode = str(mode).strip().lower()
    if mode == "":
        mode = None
    if mode not in MODES:
        raise ValueError(f"abl_gate must be one of none|disjoint, got {spec.get('abl_gate')!r}")
    if mode != "disjoint":
        return mode, [], []
    f = _ids(spec.get("abl_feedback_ids"), "abl_feedback_ids")
    g = _ids(spec.get("abl_gate_ids"), "abl_gate_ids")
    if not f or not g:
        raise ValueError("abl_gate: disjoint needs non-empty abl_feedback_ids and abl_gate_ids")
    if len(set(f)) != len(f) or len(set(g)) != len(g):
        raise ValueError("abl_feedback_ids / abl_gate_ids contain duplicates")
    if set(f) & set(g):
        raise ValueError(f"abl_feedback_ids and abl_gate_ids overlap: {sorted(set(f) & set(g))}")
    val = {str(t) for t in run_dir.read_splits().val}
    if set(f) | set(g) != val:
        raise ValueError("abl_feedback_ids + abl_gate_ids must partition the run's val ids exactly "
                         f"(missing {sorted(val - set(f) - set(g))}, extra {sorted((set(f) | set(g)) - val)})")
    return mode, f, g


def proposer_ids(run_dir):
    """F as a set in disjoint mode, else ``None`` (= no restriction)."""
    mode, f, _ = settings(run_dir)
    return set(f) if mode == "disjoint" else None


def restrict(sr: SplitResult, ids) -> SplitResult:
    """``sr`` limited to ``ids``; reward/stderr/pass_k recomputed by ``loop.aggregate_scores``
    (the harness's own aggregation); original per_task rows are kept verbatim."""
    ids = {str(i) for i in ids}
    rows = [pt for pt in (sr.per_task or []) if str(pt.get("task_id")) in ids]
    agg = aggregate_scores(sr.split, [Score.from_dict(pt) for pt in rows])
    agg.per_task = rows
    agg.cost_usd, agg.tokens, agg.seconds = sr.cost_usd, sr.tokens, sr.seconds
    agg.cost_source = dict(sr.cost_source)
    return agg


def gate_views(run_dir, current_val, cand_val):
    """``(cur, cand)`` the gate should see: G-restricted in disjoint mode, the inputs otherwise."""
    mode, _, g = settings(run_dir)
    if mode != "disjoint":
        return current_val, cand_val
    from . import gatecfg
    if gatecfg.GateConfig.for_run(run_dir).coverage_policy == "tipping":
        raise ValueError("abl_gate: disjoint is not supported with coverage_policy: tipping")
    return restrict(current_val, g), restrict(cand_val, g)


def for_proposer(run_dir, current_val):
    """``current_val`` as the proposer may see it (F only in disjoint mode)."""
    f = proposer_ids(run_dir)
    return current_val if f is None else restrict(current_val, f)


def proposer_val(run_dir, tag, split: str = "val"):
    """F-restricted reward of ``tag`` rebuilt from persisted rollouts, or None."""
    f = proposer_ids(run_dir)
    if f is None:
        return None
    from . import harness
    try:
        sr = harness.split_result_from_rollouts(run_dir, tag, split)
    except Exception:  # noqa: BLE001
        return None
    r = restrict(sr, f)
    return r.reward if r.n_scored else None


def proposer_val_delta(run_dir, cid, parent_id, val, delta):
    """``(val, delta)`` for proposer-facing text: F-restricted in disjoint mode, unchanged otherwise."""
    if proposer_ids(run_dir) is None or val is None:
        return val, delta
    v, p = proposer_val(run_dir, cid), proposer_val(run_dir, parent_id or "seed")
    return v, (v - p if v is not None and p is not None else None)


def filter_trajectories(dst, feedback_ids) -> None:
    """Delete every file under ``dst`` whose task id (prefix before ``__``) is not in F."""
    dst = Path(dst)
    if not dst.exists():
        return
    keep = {str(i) for i in feedback_ids}
    for p in sorted(dst.rglob("*")):
        if p.is_file() and p.name.split("__")[0] not in keep:
            p.unlink()


def filter_step_trajectories(run_dir, dst) -> None:
    f = proposer_ids(run_dir)
    if f is not None:
        filter_trajectories(dst, f)


_LIST = re.compile(r"[\[\{][^\[\]{}]*[\]\}]")


def scrub_reason(text: str, gate_ids) -> str:
    """Drop task-id lists (and any bare non-numeric G id) from a gate reason; aggregates stay."""
    g = {str(i) for i in gate_ids}

    def sub(m):
        items = [x.strip().strip("'\"") for x in re.split(r"[,\s]+", m.group(0)[1:-1]) if x.strip()]
        return f"[{len(items)} gate task(s) withheld]" if any(i in g for i in items) else m.group(0)

    out = _LIST.sub(sub, text or "")
    for i in g:
        if not i.isdigit():
            out = re.sub(rf"(?<![\w-]){re.escape(i)}(?![\w-])", "<gate-task>", out)
    return out
