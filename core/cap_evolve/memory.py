"""Optimizer memory: rejected approaches + accepted history.

Two append-only, WRITE-ONLY-BY-DESIGN audit records in the run dir:

- ``RejectedMemory`` — every candidate the gate rejected, with the reason.
- ``History`` — every accepted candidate, so the run's lineage is reconstructable.

Nothing in the core re-reads them. The readers are the dashboard
(``GET /api/runs/{id}/memory`` → the Deep-Dive Memory panel, and the static
export) and any optimizer prompt that greps ``rejected.jsonl`` itself. What the
optimizer is *told* each iteration comes from the framework-owned LEDGER.md /
JOURNAL.md instead (see ``harness._augment_instructions``).

Backed by jsonl files in the run dir; pure stdlib.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class RejectedMemory:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, candidate_id: str, summary: str, reason: str,
            val: Optional[float] = None) -> None:
        rec = {
            "candidate_id": candidate_id,
            "summary": summary.strip(),
            "reason": reason.strip(),
            "val": val,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")


class History:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, candidate_id: str, summary: str, val: float) -> None:
        rec = {"candidate_id": candidate_id, "summary": summary.strip(), "val": val}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
