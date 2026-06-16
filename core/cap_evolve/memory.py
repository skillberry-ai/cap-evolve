"""Optimizer memory: rejected approaches + accepted history.

Two append-only records that survive across iterations:

- ``RejectedMemory`` — every candidate the gate rejected, with the reason. Its
  ``render()`` produces a markdown block fed into the *next* proposal prompt so
  the optimizer never re-proposes a dead end (prior agent-optimization work's RejectedMemory / evo-graph's
  Rejected Memory Store).
- ``History`` — every accepted candidate, so the loop can show the optimizer
  what worked and reconstruct the best-so-far lineage.

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

    def add(self, candidate_id: str, summary: str, reason: str, val: Optional[float] = None) -> None:
        rec = {
            "candidate_id": candidate_id,
            "summary": summary.strip(),
            "reason": reason.strip(),
            "val": val,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def render(self, limit: int = 20) -> str:
        """Markdown block for the proposal prompt: 'do not try these again'."""
        items = self.entries()[-limit:]
        if not items:
            return "_No rejected approaches yet._"
        lines = ["## Rejected approaches (do NOT re-propose these)"]
        for e in items:
            v = f" (val={e['val']:.4f})" if e.get("val") is not None else ""
            lines.append(f"- **{e['summary']}** — rejected: {e['reason']}{v}")
        return "\n".join(lines)


class History:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, candidate_id: str, summary: str, val: float) -> None:
        rec = {"candidate_id": candidate_id, "summary": summary.strip(), "val": val}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def render(self, limit: int = 10) -> str:
        items = self.entries()[-limit:]
        if not items:
            return "_No accepted edits yet (this is the baseline)._"
        lines = ["## Accepted edits so far (what worked)"]
        for e in items:
            lines.append(f"- {e['summary']} → val={e['val']:.4f}")
        return "\n".join(lines)
