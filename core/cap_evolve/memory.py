"""Optimizer memory: append-only jsonl records of rejected + accepted candidates.

These are **audit/UI records, not optimizer input.** Two append-only files in the run
dir, one line per candidate:

- ``RejectedMemory`` (``rejected.jsonl``) — every candidate the gate rejected, with the
  reason.
- ``History`` (``history.jsonl``) — every accepted candidate.

Their only consumer is the dashboard: ``GET /api/runs/{id}/memory``
(``dashboard/backend/capevolve_dashboard/memory.py``) serves them to the Memory panel
and to the Insights "dead ends" grouping, which read exactly
``{candidate_id, summary, val, reason}`` — nothing else.

They are NOT fed back into any proposal prompt: the framework-owned LEDGER.md /
JOURNAL.md / RUNMAP.md files (see ``harness._augment_instructions``) are the sole
cross-iteration channel the optimizer actually reads. Do not add a ``render()`` here
expecting it to reach a prompt — wire it through ``_augment_instructions`` instead.

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
            val: Optional[float] = None) -> None:
        _append(self.path, {"candidate_id": candidate_id, "summary": summary.strip(),
                            "reason": reason.strip(), "val": val})


class History:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, candidate_id: str, summary: str, val: float) -> None:
        _append(self.path, {"candidate_id": candidate_id, "summary": summary.strip(),
                            "val": val})
