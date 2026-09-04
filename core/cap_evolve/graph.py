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
    subset: {task_ids, rationale, tier} | None   screen.py's subset, if any ran
    status: "accepted" | "rejected"              (Phase 1 only records terminal steps)
    val_mean: float | None
    screen: {...} | None       merged screen.py tier records, if any ran
    gate: {...} | None         the round.py gate-table row, if one exists
"""

from __future__ import annotations

import json
from pathlib import Path

GRAPH_FILENAME = "graph.jsonl"


def _screens_dir(run_dir) -> Path:
    return run_dir.root / "screens"


def collect_screen_info(run_dir, tag: str) -> dict | None:
    """Merge every ``screens/<tag>__screenN.json`` tier for ``tag`` into one summary.

    Returns ``None`` when no screen ever ran for this candidate — the common
    case today, since screening stays opt-in until #434 Phase 3 makes it the
    default on-ramp.
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


def append_node(run_dir, *, node_id: str, parents: list[str], status: str,
                 val_mean: float | None = None, edit_kind: str | None = None,
                 cluster_ids: list[str] | None = None,
                 micro_tests: list[str] | None = None,
                 note: str | None = None, gate: dict | None = None,
                 screen: dict | None = None) -> dict:
    """Append one candidate node to ``$R/graph.jsonl``.

    ``gate``/``screen`` default to a fresh lookup via :func:`gate_row` /
    :func:`collect_screen_info` when not supplied — callers with the data
    already in hand (``round.py``'s in-memory table) may pass it directly to
    avoid re-reading disk.
    """
    if gate is None:
        gate = gate_row(run_dir, node_id)
    if screen is None:
        screen = collect_screen_info(run_dir, node_id)
    subset = None
    if screen and screen.get("subset_ids"):
        subset = {"task_ids": screen["subset_ids"], "rationale": None,
                  "tier": screen.get("last_tier")}
    rec = {
        "id": node_id,
        "parents": list(parents),
        "cluster_ids": cluster_ids or [],
        "edit_kind": edit_kind or ("merge" if len(parents) > 1 else "code"),
        "micro_tests": micro_tests or [],
        "subset": subset,
        "status": status,
        "val_mean": val_mean,
        "screen": screen,
        "gate": gate,
        "note": note,
    }
    path = run_dir.root / GRAPH_FILENAME
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")
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
    for n in read_nodes(run_dir):
        nid = n.get("id")
        if not nid:
            continue
        by_id[nid] = {**n, "children": by_id.get(nid, {}).get("children", [])}
    for nid, n in by_id.items():
        for parent in n.get("parents") or []:
            if parent in by_id:
                by_id[parent].setdefault("children", []).append(nid)
    return by_id
