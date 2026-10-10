"""candidate_graph — a query layer over ``graph.jsonl``'s candidate DAG (issue #665,
workstream 2).

``cap_evolve.graph`` already owns the on-disk format and the two primitives that
read it (``read_nodes``/``build_dag``); this module adds NOTHING to that schema and
never writes ``graph.jsonl`` itself. It exists only because the planning layer
(``plan_round.py``) and anything reasoning over "which lineages are still live"
needs more than a flat node list — parent/child lookups, ancestry checks, and the
current active frontier — and re-deriving those by hand at every call site is how
ad-hoc graph-walking bugs happen. ``dashboard.reduce_run`` and ``build_dag`` keep
working exactly as before; this is a second, independent reader of the same view.
"""

from __future__ import annotations

from . import graph as _graph
from . import schema_v2 as _schema_v2

#: Statuses that close a lineage — nothing should ever branch from or re-measure
#: these again. Everything else (``"screened"``, ``"proposed"``, ``"gated"``,
#: ``"accepted"``) is still active: see ``graph.py``'s module docstring for the
#: full status vocabulary.
_INACTIVE_STATUSES = frozenset({"rejected", "superseded"})


class CandidateGraph:
    """In-memory query view over one run's ``graph.jsonl``.

    Construct via :meth:`load`; the two-argument constructor exists mainly for
    tests that want to hand it a synthetic ``{id: node}`` map directly without
    touching disk.
    """

    def __init__(self, nodes: dict[str, dict]) -> None:
        self._nodes = nodes  # id -> {**node, "children": [...]}  (graph.build_dag's shape)

    @classmethod
    def load(cls, run_dir) -> "CandidateGraph":
        """Build the view from ``$R/graph.jsonl`` via ``graph.build_dag`` (last-record-wins)."""
        return cls(_graph.build_dag(run_dir))

    def node(self, node_id: str) -> dict | None:
        return self._nodes.get(node_id)

    def node_v2(self, node_id: str, *, val_ids=None, evals=None) -> dict | None:
        """:meth:`node` with Run schema v2 keys filled from legacy fields
        (docs/RUN_SCHEMA_V2.md). Parents come from :meth:`parents_of`, so any self-parent
        filtering there (#719) applies; ``val_ids``/``evals`` give real eval coverage."""
        n = self._nodes.get(node_id)
        return (_schema_v2.normalize_node(n, val_ids=val_ids, evals=evals,
                                          parents=self.parents_of(node_id)) if n else None)

    def __contains__(self, node_id: str) -> bool:
        return node_id in self._nodes

    def __len__(self) -> int:
        return len(self._nodes)

    def parents_of(self, node_id: str) -> list[str]:
        """``node_id``'s parent ids (1 for an edit, 2+ for a merge, ``[]`` unknown/root)."""
        n = self._nodes.get(node_id)
        # a self-parent (seen live: cand_4 -> cand_4) is corrupt data, never an edge
        return [p for p in n.get("parents") or [] if p != node_id] if n else []

    def children_of(self, node_id: str) -> list[str]:
        """Ids of every node whose ``parents`` names ``node_id`` (``build_dag``'s edge)."""
        n = self._nodes.get(node_id)
        return list(n.get("children") or []) if n else []

    def is_descendant(self, a: str, b: str) -> bool:
        """Is ``a`` reachable from ``b`` by following parent edges (i.e. is ``b`` an
        ancestor of ``a``)? Walks a merge's multiple parent edges too. ``False`` for
        ``a == b`` (a node is not its own descendant) and for either id missing."""
        if a == b or a not in self._nodes:
            return False
        seen: set[str] = set()
        stack = list(self.parents_of(a))
        while stack:
            p = stack.pop()
            if p == b:
                return True
            if p in seen or p not in self._nodes:
                continue
            seen.add(p)
            stack.extend(self.parents_of(p))
        return False

    def frontier(self) -> list[str]:
        """Active, non-dominated candidates: not rejected/superseded, and with no
        active (non-rejected/superseded) child yet.

        These are the lineage tips a planner should consider extending next. A
        rejected or superseded node is never in the frontier even with zero
        children — a closed lineage, not a live dead end. Sorted for determinism.
        """
        out = []
        for nid, n in self._nodes.items():
            if n.get("status") in _INACTIVE_STATUSES:
                continue
            children = n.get("children") or []
            if any(self._nodes.get(c, {}).get("status") not in _INACTIVE_STATUSES
                   for c in children):
                continue
            out.append(nid)
        return sorted(out)

    def branches(self) -> list[list[str]]:
        """One root->tip path per independent active lineage.

        Each :meth:`frontier` tip is one branch; its path is built by walking the
        FIRST parent back to a node with no parent on the graph (a root, e.g. the
        candidate forked straight off ``"seed"``). Two branches may share a prefix
        (both descend from the same accepted ancestor) — they are still reported
        separately because each is a distinct point the planner may choose to grow.
        """
        out = []
        for tip in self.frontier():
            lineage = [tip]
            seen: set[str] = {tip}
            cur = tip
            while True:
                parents = self.parents_of(cur)
                if not parents or parents[0] not in self._nodes:
                    break
                cur = parents[0]
                if cur in seen:
                    raise ValueError(f"candidate graph has a parent cycle at {cur!r}")
                seen.add(cur)
                lineage.append(cur)
            lineage.reverse()
            out.append(lineage)
        return out
