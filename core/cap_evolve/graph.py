"""graph — append-only candidate DAG log ($R/graph.jsonl).

A VIEW over mechanics that already exist and already gate/accept candidates:
``events.jsonl`` step records (parent/accept/val), ``round.py``'s persisted gate
tables under ``work/*.json``, and ``screen.py``'s tier files under ``screens/``.
Writing a node here changes nothing about how a candidate is measured, screened,
gated, or accepted — every field but ``id``/``parents``/``status`` is a courtesy
copy of data reconstructible from those artifacts, which is what makes this a
view and not a new source of truth (issue #435, parent design #434).

Schema (``CandidateNode``, per #434 section "1. Data structure: a candidate
DAG"): one JSON object per line —

    id: str                    unique candidate tag
    parents: [str]             1 for an edit, 2+ for a merge
    cluster_ids: [str]         which diagnose() cluster(s) this targets (Phase 3+)
    edit_kind: "prompt" | "code" | "merge"
    micro_tests: [str]         micro-test ids this was designed to pass (Phase 2+)
    subset: {task_ids, rationale, tier} | None   screen.py's subset and WHY those tasks;
                               ``None`` on a gated node means the screen was skipped, and
                               such a node carries ``screen_skip_justification``
    status: one per STATE TRANSITION, append-only (last record per id wins):
            "screened"   round.py ran (or found) a screen for it; ``screen.decision``
                         says kill/promote
            "proposed"   round.py built a pairwise merge node (2 parents), not yet screened
            "superseded" screened but NOT gated on its own: a parent whose bytes a
                         better-screening merge carries (``merged_into``), or a merge that
                         lost a parent's screened gain (``reason``)
            "gated"      round.py ran the full-val gate; ``gate`` is its table row
            "accepted" | "rejected"   the terminal commit (commit.py / record_iteration)
    val_mean: float | None
    screen: {...} | None       merged screen.py tier records, if any ran
    gate: {...} | None         the round.py gate-table row, if one exists
"""

from __future__ import annotations

import json
import os
from pathlib import Path

GRAPH_FILENAME = "graph.jsonl"


def _screens_dir(run_dir) -> Path:
    return run_dir.root / "screens"


def collect_screen_info(run_dir, tag: str) -> dict | None:
    """Merge every ``screens/<tag>__screenN.json`` tier for ``tag`` into one summary.

    Returns ``None`` when no screen ever ran for this candidate (a deterministic
    algorithm's step, or an agent-optimize candidate gated under an explicit
    ``--skip-screen-*`` override — ``round.py`` screens every other one, #437).
    """
    d = _screens_dir(run_dir)
    if not d.is_dir():
        return None
    tiers = []
    for f in sorted(d.glob(f"{tag}__screen*.json")):
        try:
            tiers.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    if not tiers:
        return None
    last = tiers[-1]
    subset_ids = sorted({i for t in tiers for i in (t.get("subset") or {}).get("ids", [])})
    return {
        "tiers": [{"tier": t.get("tier"), "decision": t.get("decision"),
                   "mean_delta": t.get("mean_delta"), "se": t.get("se")}
                  for t in tiers],
        "decision": last.get("decision"),
        "subset_ids": subset_ids,
        "rationale": (last.get("subset") or {}).get("rationale"),
        "last_tier": last.get("tier"),
    }


def gate_row(run_dir, candidate_id: str) -> dict | None:
    """The verdict row a ``round.py`` gate table recorded for ``candidate_id``.

    Reads the newest ``work/*.json`` table that mentions this tag (same lookup
    ``commit.py._gate_verdict`` already does), so a candidate never gated
    through ``round.py`` (e.g. a deterministic hill-climb/gepa/skillopt step,
    which gates via ``gate.decide`` directly) simply has no row here.
    """
    work = run_dir.root / "work"
    if not work.is_dir():
        return None
    for log in sorted(work.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not log.is_file() or log.suffix != ".json":
            continue
        try:
            payload = json.loads(log.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict):
            continue
        for row in payload.get("candidates") or []:
            if isinstance(row, dict) and str(row.get("tag")) == str(candidate_id):
                return row
    return None


def latest_node(run_dir, node_id: str) -> dict | None:
    """The most recent record for ``node_id`` in ``graph.jsonl``, or ``None``."""
    found = None
    for n in read_nodes(run_dir):
        if n.get("id") == node_id:
            found = n
    return found


def append_node(run_dir, *, node_id: str, parents: list[str] | None, status: str,
                 val_mean: float | None = None, edit_kind: str | None = None,
                 cluster_ids: list[str] | None = None,
                 micro_tests: list[str] | None = None,
                 note: str | None = None, gate: dict | None = None,
                 screen: dict | None = None, subset: dict | None = None,
                 **extra) -> dict:
    """Append one state transition of a candidate node to ``$R/graph.jsonl``.

    ``gate``/``screen`` default to a fresh lookup via :func:`gate_row` /
    :func:`collect_screen_info` when not supplied — callers with the data
    already in hand (``round.py``'s in-memory table) may pass it directly to
    avoid re-reading disk.

    ``subset`` is the fallback task subset when no screen ran — e.g. the tasks of the
    DIAGNOSIS.json clusters an agent-optimize edit targeted (#611). A screen.py subset,
    when one exists, always wins: it is what was actually measured.

    Fields a later transition does not know (``cluster_ids``/``edit_kind``/
    ``micro_tests``, and ``parents`` when passed as ``None``) carry forward from
    this node's previous record, so the terminal ``commit.py`` write does not erase
    what ``round.py`` recorded when it screened or built the node. ``extra`` keys
    (e.g. ``merged_into``, ``screen_skip_justification``) are written when not None.
    """
    prior = latest_node(run_dir, node_id) or {}
    parents = list(parents) if parents else list(prior.get("parents") or ["seed"])
    if gate is None:
        gate = gate_row(run_dir, node_id)
    if screen is None:
        screen = collect_screen_info(run_dir, node_id)
    if screen and screen.get("subset_ids"):
        subset = {"task_ids": screen["subset_ids"], "rationale": screen.get("rationale"),
                  "tier": screen.get("last_tier")}
    rec = {
        "id": node_id,
        "parents": parents,
        "cluster_ids": cluster_ids or prior.get("cluster_ids") or [],
        "edit_kind": edit_kind or ("merge" if len(parents) > 1
                                   else prior.get("edit_kind") or "code"),
        "micro_tests": micro_tests or prior.get("micro_tests") or [],
        "subset": subset,
        "status": status,
        "val_mean": val_mean,
        "screen": screen,
        "gate": gate,
        "note": note,
        **{k: v for k, v in extra.items() if v is not None},
    }
    return append_node_locked(run_dir, rec)


def append_node_locked(run_dir, rec: dict) -> dict:
    """Validate ``rec`` (no self-parent / cycle, #714) and append it as ONE ``O_APPEND``
    write under ``$R/.graph.lock``."""
    from .candidate_graph import CandidateGraph
    from .lineage import validate
    from .rundir import _file_lock
    path = run_dir.root / GRAPH_FILENAME
    line = (json.dumps(rec, default=str) + "\n").encode("utf-8")
    with _file_lock(run_dir.root / ".graph.lock"):
        validate(CandidateGraph.load(run_dir), rec["id"], rec["parents"])
        fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    return rec


def read_nodes(run_dir) -> list[dict]:
    """Every node record in ``$R/graph.jsonl``, in append order."""
    path = run_dir.root / GRAPH_FILENAME
    if not path.exists():
        return []
    nodes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            nodes.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return nodes


def build_dag(run_dir) -> dict[str, dict]:
    """Reconstruct ``{node_id: {**node, "children": [...]}}`` from ``graph.jsonl``.

    Last record wins per id — a candidate is normally committed exactly once
    (``commit.py`` refuses a second decision for the same tag without
    ``--force``), but an audit/repair re-commit re-appends, and this is the
    read-back that should reflect the latest state.
    """
    by_id: dict[str, dict] = {}
    last_clean: dict[str, list] = {}
    for n in read_nodes(run_dir):
        nid = n.get("id")
        if not nid:
            continue
        # A self-parent (seen live: cand_4 -> cand_4 on its accept record) is corrupt, never an
        # edge: fall back to this node's previous non-self parents instead of orphaning it.
        raw = n.get("parents") or []
        clean = [p for p in raw if p != nid]
        if clean:
            last_clean[nid] = clean
        if raw and not clean:
            clean = last_clean.get(nid, [])
        n = {**n, "parents": clean} if clean != raw else n
        by_id[nid] = {**n, "children": by_id.get(nid, {}).get("children", [])}
    for nid, n in by_id.items():
        for parent in n.get("parents") or []:
            if parent in by_id and parent != nid:
                by_id[parent].setdefault("children", []).append(nid)
    return by_id
