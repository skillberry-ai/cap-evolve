"""lineage -- DAG queries (tips, ancestors, merge-base) and append-time validation over
``graph.jsonl`` (issue #714). Layered on :class:`CandidateGraph`; tips are independent of
``best_id`` (a tip is an unfinished lineage, the champion is a claim that needs evidence)."""

from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path

from .candidate_graph import CandidateGraph

ROOT = "seed"


def tips(g: CandidateGraph) -> list[str]:
    return g.frontier()


def ancestors(g: CandidateGraph, node_id: str) -> dict[str, int]:
    """``{ancestor: min edge distance}`` over all parents, including ``node_id`` at 0.
    ``seed`` is included as the universal ancestor even though it has no node record."""
    depth = {node_id: 0}
    queue = [node_id]
    while queue:
        cur = queue.pop(0)
        for p in g.parents_of(cur):
            if p != cur and p not in depth:
                depth[p] = depth[cur] + 1
                queue.append(p)
    if node_id != ROOT:
        depth.setdefault(ROOT, max(depth.values()) + 1)
    return depth


def merge_base(g: CandidateGraph, a: str, b: str, score: dict | None = None) -> str:
    """Common ancestor minimising ``depth_a + depth_b``; ties -> higher ``score[id]``
    (posterior mean, when given) else lexicographic."""
    da, db = ancestors(g, a), ancestors(g, b)
    common = da.keys() & db.keys()
    return min(common, key=lambda n: (da[n] + db[n], -(score or {}).get(n, 0.0), n))


def fold_merge_base(g: CandidateGraph, merged: list[str], nxt: str, score: dict | None = None) -> str:
    """Base for one fold step of an N-way merge: the LCA of ``nxt`` and the ancestor set
    of the already-merged parents ``merged`` (the merge node itself need not exist yet)."""
    bases = [merge_base(g, m, nxt, score) for m in merged]
    da = ancestors(g, nxt)
    return min(bases, key=lambda n: (da[n], n))


def validate(g: CandidateGraph, node_id: str, parents: list[str]) -> None:
    """Raise ``ValueError`` on a self-parent or a parent that is a descendant of ``node_id``."""
    if node_id in parents:
        raise ValueError(f"{node_id!r} lists itself as a parent")
    for p in parents:
        if g.is_descendant(p, node_id):
            raise ValueError(f"parent {p!r} descends from {node_id!r}: would create a cycle")


def acquire_driver_lock(run_dir_root) -> str | None:
    """Claim ``$R/driver.lock`` for this process. Returns an error message when another
    live pid on this host holds it, else ``None`` (a dead holder's lock is stolen)."""
    path = Path(run_dir_root) / "driver.lock"
    try:
        held = json.loads(path.read_text(encoding="utf-8"))
        pid = int(held["pid"])
        if held.get("host") == socket.gethostname() and pid != os.getpid():
            try:
                os.kill(pid, 0)
                return f"another driver (pid {pid}) holds {path}; refusing to start"
            except ProcessLookupError:
                pass
            except PermissionError:
                return f"another driver (pid {pid}) holds {path}; refusing to start"
    except (OSError, ValueError, KeyError, TypeError):
        pass
    path.write_text(json.dumps({"pid": os.getpid(), "host": socket.gethostname(),
                                "started": time.time()}), encoding="utf-8")
    return None
