"""Hypotheses — a candidate must state which cluster it targets and be big enough to measure.

Forensics (issue #716): after the first big candidate, every edit aimed at ONE task, whose
ceiling is 1/n_tasks of the mean — below the run-to-run sd, so unreadable. ``validate`` is the
minimum-edit-size rule; records live append-only in ``$R/hypotheses.jsonl``:

    {id, cluster_ids, claim, predicted_tasks, predicted_mechanism,
     edit_scope: [policy|tools|reference], repeat_of?, status?}

``status: "pruned"`` (set by whoever prunes a hypothesis) is what makes a later hypothesis on
the same clusters + scope a ``repeat_of``.
"""

from __future__ import annotations

import json
from pathlib import Path

#: Same task-count / headroom bar as the issue: >= 2 tasks or >= 0.06 reward units.
MIN_TASKS = 2
MIN_HEADROOM = 0.06


def validate(h: dict, clusters: list[dict], justification: str = "") -> tuple[bool, str]:
    """``(ok, reason)``. ``clusters`` are cluster_v2 dicts (``cluster_id``, ``tasks``, ``headroom``).

    ``justification`` is the written override (``--small-edit-justification``): a too-small
    edit passes with it, but the reason says so. Everything else is never overridable."""
    ids = list(h.get("cluster_ids") or [])
    cs = [c for c in clusters if c.get("cluster_id") in ids]
    if not ids or len(cs) != len(set(ids)):
        return False, f"unknown cluster_ids {sorted(set(ids) - {c.get('cluster_id') for c in cs})}"
    pool = {str(t) for c in cs for t in c.get("tasks") or []}
    predicted = {str(t) for t in h.get("predicted_tasks") or []}
    if not predicted <= pool:
        return False, f"predicted_tasks {sorted(predicted - pool)} are not in the targeted clusters"
    headroom = round(sum(float(c.get("headroom") or 0.0) for c in cs), 4)
    if len(predicted) >= MIN_TASKS or headroom >= MIN_HEADROOM:
        return True, ""
    msg = (f"covers {len(predicted)} task(s), headroom {headroom} < {MIN_HEADROOM}: "
           "merge with a related cluster or widen the fix")
    return (True, f"small edit allowed by justification ({msg})") if justification.strip() else (False, msg)


def repeat_of(h: dict, prior: list[dict]) -> str | None:
    """Id of the first PRUNED earlier hypothesis with the same cluster_ids and edit_scope."""
    key = (sorted(h.get("cluster_ids") or []), sorted(h.get("edit_scope") or []))
    for p in prior:
        if p.get("status") == "pruned" and \
                (sorted(p.get("cluster_ids") or []), sorted(p.get("edit_scope") or [])) == key:
            return p.get("id")
    return None


def _root(run_dir) -> Path:
    return Path(run_dir) if isinstance(run_dir, (str, Path)) else run_dir.root


def load(run_dir) -> list[dict]:
    f = _root(run_dir) / "hypotheses.jsonl"
    if not f.exists():
        return []
    return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]


def append(run_dir, h: dict) -> dict:
    """Append ``h`` (setting ``repeat_of`` from the earlier records) and return the record."""
    prior = load(run_dir)
    h = dict(h)
    rep = repeat_of(h, prior)
    if rep and not h.get("repeat_of"):
        h["repeat_of"] = rep
    f = _root(run_dir) / "hypotheses.jsonl"
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(h, sort_keys=True) + "\n")
    return h
