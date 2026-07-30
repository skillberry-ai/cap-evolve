"""Capability snapshot reads, diffs, and per-task impact — the "what changed" layer.

Split out of ``harness.py`` (#115). Three consumers need exactly this and nothing else:
the LEDGER/RUNMAP renderers, #129's rejected-approach signature, and the dashboard's
diff view. Grouping them here is what stops the skip-list from drifting into a fourth
copy (the bug ``rundir.NON_CAPABILITY_NAMES`` exists to prevent).

Note the deliberate asymmetry documented on ``_CAP_DIFF_SKIP``: this is a read-side
FILTER, so it takes the whole shared union plus the injected read-context, unlike the
single DESTRUCTIVE consumer (``hillclimb._SNAPSHOT_IGNORE``).
"""

from __future__ import annotations

from pathlib import Path

from . import optimizer_context as _oc
from .evaluate import split_result_from_rollouts
from .rundir import NON_CAPABILITY_NAMES, RunDir, iteration_candidate

# State/handover files that are NOT part of the capability — excluded from any
# capability diff (kept in one place; mirrors dashboard._DIFF_SKIP).
# Derived from ``rundir.NON_CAPABILITY_NAMES`` — a read-side FILTER like the cache and
# component lists, so it takes the whole union (live + legacy scratch + the two
# snapshotted explainability files). It must NOT be shared with
# ``harness._SNAPSHOT_IGNORE``, which is DESTRUCTIVE and takes ``SCRATCH_NAMES`` only:
# feeding this list to the snapshot would DELETE PROCESS.md, the explainability record
# we deliberately keep. Same predicate, different operation. See the tier note in
# rundir.py; the split is pinned by
# test_gepa.py::test_scratch_ignores_are_one_shared_definition.
#
# The INJECTED_* halves matter as much as the scratch half here, for a subtler reason:
# the PARENT side of a capability diff is a snapshot (``_SNAPSHOT_IGNORE`` stripped the
# injected read-context) while the CHILD side is the live workdir (it did not) — so
# without this union every injected ``CLAUDE.md`` / ``.claude/skills/<x>/SKILL.md`` reads
# as an ADDITION, sorts to the front of the diff, and buries the real edit. Both sets are
# derived, never enumerated: a hardcoded subset of ``INJECTED_DIRS`` is exactly how the
# previous four copies drifted.
_CAP_DIFF_SKIP = set(NON_CAPABILITY_NAMES) | set(_oc.INJECTED_NAMES)


_CAP_DIFF_SKIP_DIRS = set(_oc.INJECTED_DIRS)


def _capability_files(d: Path) -> dict[str, str]:
    """Read a candidate snapshot's capability files (text), skipping injected scratch.

    Same source + skip-list the dashboard's ``build_diffs`` uses, so a diff built here
    shows only the real capability edit (not trajectories/guidance/state files)."""
    out: dict[str, str] = {}
    if not d.exists():
        return out
    for f in sorted(d.rglob("*")):
        if not f.is_file():
            continue
        rel = str(f.relative_to(d))
        top = rel.split("/", 1)[0]
        if rel in _CAP_DIFF_SKIP or top in _CAP_DIFF_SKIP_DIRS:
            continue
        try:
            out[rel] = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
    return out


def _diff_capabilities(parent_dir: Path, cand_dir: Path, *, max_chars: int = 8000) -> str:
    """Unified diff of capability files between a parent and candidate snapshot."""
    import difflib
    pf, cf = _capability_files(parent_dir), _capability_files(cand_dir)
    blocks: list[str] = []
    for path in sorted(set(cf) | set(pf)):
        a = pf.get(path, "").splitlines()
        b = cf.get(path, "").splitlines()
        if a == b:
            continue
        diff = "\n".join(ln for ln in difflib.unified_diff(
            a, b, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="", n=2))
        if diff.strip():
            blocks.append(diff)
    text = "\n".join(blocks)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (truncated)"
    return text


def _parent_map(run_dir: RunDir) -> dict[str, str]:
    """Map each candidate id -> the parent id it was forked from, from iteration events.

    Reads EVERY ``ITERATION_EVENT_KINDS`` event, not just ``step`` — GEPA bypasses
    ``run_step`` and emits ``gepa_val_gate``, so a ``kind == "step"`` filter here made
    GEPA's whole cross-iteration history channel (LEDGER/RUNMAP/prior_iterations)
    permanently empty. Falls back to "seed" when the parent edge is absent."""
    return {cid: str(rec.get("parent") or rec.get("parent_id") or "seed")
            for rec in run_dir.iteration_events()
            if (cid := iteration_candidate(rec))}


def _per_task_rewards(run_dir: RunDir, tag: str, split: str = "val") -> dict[str, float]:
    """Per-task mean reward for ``tag``, rebuilt from persisted rollouts.

    Reuses the canonical ``split_result_from_rollouts`` so scores match the loop
    exactly (the same read the dashboard's ``_per_task_from_rollouts`` uses).
    Returns {} when no rollouts were persisted for this tag."""
    try:
        sr = split_result_from_rollouts(run_dir, tag, split)
    except Exception:  # noqa: BLE001
        return {}
    return {pt["task_id"]: float(pt.get("reward", 0.0)) for pt in (sr.per_task or [])}


def _candidate_task_impact(run_dir: RunDir, cid: str, split: str = "val",
                           parent_of: dict | None = None) -> dict | None:
    """Per-task reward Δ of candidate ``cid`` vs its PARENT, from rollouts.

    Returns ``{"broke": [...], "fixed": [...], "delta": float}`` where ``broke`` are
    tasks that were PASSING (reward ≈ 1) under the parent and DROPPED under the
    candidate, and ``fixed`` are tasks that were failing under the parent and now
    PASS. ``delta`` is the mean per-task reward change over shared tasks. Returns
    ``None`` when either side has no rollouts on disk (nothing to compare)."""
    parent_of = parent_of if parent_of is not None else _parent_map(run_dir)
    parent_id = parent_of.get(cid, "seed")
    cand = _per_task_rewards(run_dir, cid, split)
    par = _per_task_rewards(run_dir, parent_id, split)
    if not cand or not par:
        return None
    shared = [t for t in cand if t in par]
    if not shared:
        return None
    eps = 1e-9
    broke = sorted(t for t in shared
                   if par[t] >= 1.0 - eps and cand[t] < par[t] - eps)
    fixed = sorted(t for t in shared
                   if par[t] < 1.0 - eps and cand[t] >= 1.0 - eps)
    delta = sum(cand[t] - par[t] for t in shared) / len(shared)
    return {"broke": broke, "fixed": fixed, "delta": delta, "parent": parent_id}
