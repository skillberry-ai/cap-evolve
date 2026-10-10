"""lineage -- DAG queries (tips, ancestors, merge-base) and append-time validation over
``graph.jsonl`` (issue #714). Layered on :class:`CandidateGraph`; tips are independent of
``best_id`` (a tip is an unfinished lineage, the champion is a claim that needs evidence)."""

from __future__ import annotations

import atexit
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


class DriverBusy(RuntimeError):
    pass


def acquire_driver_lock(run_dir_root, steal: bool = False) -> None:
    """Claim ``$R/driver.lock`` atomically (``O_EXCL``) and release it at exit.

    Raises :class:`DriverBusy` when a lock exists and its holder is alive, or cannot be
    judged (other host, unreadable file): a recycled pid or NFS run dir must not be
    silently overridden. ``steal=True`` (``round.py --steal-lock``) takes it over anyway.
    A same-host holder whose pid is dead is replaced.
    """
    path = Path(run_dir_root) / "driver.lock"
    me = {"pid": os.getpid(), "host": socket.gethostname(), "started": time.time()}
    for _ in range(2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if not steal:
                _refuse_unless_stale(path)
            path.unlink(missing_ok=True)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(me, f)
        atexit.register(_release, path, me["pid"])
        return
    raise DriverBusy(f"could not claim {path}")


def _refuse_unless_stale(path: Path) -> None:
    try:
        held = json.loads(path.read_text(encoding="utf-8"))
        pid, host = int(held["pid"]), held.get("host")
    except (OSError, ValueError, KeyError, TypeError):
        raise DriverBusy(f"{path} exists and is unreadable; remove it or pass --steal-lock")
    if host != socket.gethostname():
        raise DriverBusy(f"{path} is held by pid {pid} on host {host!r}; cannot verify it is "
                         "dead from here. Pass --steal-lock if you are sure.")
    if pid == os.getpid():
        return
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return
    except PermissionError:
        pass
    raise DriverBusy(f"another driver (pid {pid}) holds {path}; refusing to start. "
                     "If that pid is stale (recycled), pass --steal-lock.")


def _release(path: Path, pid: int) -> None:
    try:
        if json.loads(path.read_text(encoding="utf-8")).get("pid") == pid:
            path.unlink()
    except (OSError, ValueError):
        pass
