"""Optimizer memory: append-only jsonl records of rejected + accepted candidates.

Two append-only files in the run dir, one line per candidate:

- ``RejectedMemory`` (``rejected.jsonl``) — every candidate the gate rejected, with the
  reason.
- ``History`` (``history.jsonl``) — every accepted candidate.

The dashboard reads both: ``GET /api/runs/{id}/memory``
(``dashboard/backend/capevolve_dashboard/memory.py``) serves them to the Memory panel
and to the Insights "dead ends" grouping, which read
``{candidate_id, summary, val, reason}`` plus (rejections only) ``approach``.

``rejected.jsonl`` additionally feeds the optimizer's **dead-end constraint block**
(``harness.dead_end_constraints`` -> ``harness._augment_instructions``, issue #129):
``approach`` carries the normalized signature of the edit that was rejected, so the next
proposal prompt can name the failed approach instead of only its score. Records written
before #129 have no ``approach`` and degrade to being skipped.

Nothing here renders a prompt on its own — ``_augment_instructions`` is the only
function whose output reaches the optimizer (see #114). Wire new prompt content there.

Pure stdlib.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def _append(path: Path, rec: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


class RejectedMemory:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, candidate_id: str, summary: str, reason: str,
            val: Optional[float] = None, approach: str = "") -> None:
        """Record one rejection.

        ``approach`` is the normalized signature of the edit that failed (see
        ``harness.approach_signature``) — the field the #129 dead-end constraint block is
        built from. Optional so direct callers and pre-#129 records stay valid.
        """
        _append(self.path, {"candidate_id": candidate_id, "summary": summary.strip(),
                            "reason": reason.strip(), "val": val,
                            "approach": approach.strip()})


class History:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, candidate_id: str, summary: str, val: float) -> None:
        _append(self.path, {"candidate_id": candidate_id, "summary": summary.strip(),
                            "val": val})
