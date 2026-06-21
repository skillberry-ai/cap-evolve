"""Optimizer memory: rejected approaches + accepted history.

Two append-only records that survive across iterations:

- ``RejectedMemory`` — every candidate the gate rejected, with the reason. Its
  ``render()`` produces a markdown block fed into the *next* proposal prompt as
  STEERING: don't re-submit a regressed edit verbatim, but a better-designed version
  of the same idea may still work — so a high-value cluster is not permanently
  abandoned (prior agent-optimization work's RejectedMemory / evo-graph's Rejected Memory Store).
- ``History`` — every accepted candidate, so the loop can show the optimizer
  what worked and reconstruct the best-so-far lineage.

Backed by jsonl files in the run dir; pure stdlib.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def _store_impact(rec: dict, impact: Optional[dict]) -> None:
    """Attach a candidate's per-task broke/fixed lists to its memory record.

    ``impact`` is the dict produced by ``harness._candidate_task_impact``
    (``{"broke": [...], "fixed": [...], ...}``). Only the non-empty broke/fixed
    lists are stored, so old records (impact=None) stay byte-identical and the
    memory file is not bloated when there was no per-task movement."""
    if not impact:
        return
    broke = [str(t) for t in (impact.get("broke") or [])]
    fixed = [str(t) for t in (impact.get("fixed") or [])]
    if broke:
        rec["broke"] = broke
    if fixed:
        rec["fixed"] = fixed


def _render_impact(e: dict) -> Optional[str]:
    """One-line per-task impact for a memory entry, or None when there is none."""
    broke = e.get("broke") or []
    fixed = e.get("fixed") or []
    if not broke and not fixed:
        return None
    parts = []
    if broke:
        parts.append("broke {" + ", ".join(str(t) for t in broke) + "}")
    if fixed:
        parts.append("fixed {" + ", ".join(str(t) for t in fixed) + "}")
    return "per-task impact: " + "; ".join(parts)


class RejectedMemory:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, candidate_id: str, summary: str, reason: str, val: Optional[float] = None,
            note: Optional[str] = None, impact: Optional[dict] = None) -> None:
        rec = {
            "candidate_id": candidate_id,
            "summary": summary.strip(),
            "reason": reason.strip(),
            "val": val,
        }
        if note and note.strip():
            rec["note"] = note.strip()
        _store_impact(rec, impact)
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
        """Markdown block for the proposal prompt: approaches that regressed AS
        IMPLEMENTED — steering, not a permanent ban-list."""
        items = self.entries()[-limit:]
        if not items:
            return "_No regressed approaches yet._"
        lines = [
            "## Approaches that regressed AS IMPLEMENTED",
            "These exact edits were rejected by the gate. Don't re-submit them verbatim — "
            "but a better-designed version of the same idea MAY still work, so don't "
            "permanently abandon a high-value cluster. Each shows its reject reason "
            "(and per-task impact) so you can redesign rather than repeat.",
        ]
        for e in items:
            v = f" (val={e['val']:.4f})" if e.get("val") is not None else ""
            lines.append(f"- **{e['summary']}** — rejected: {e['reason']}{v}")
            note = (e.get("note") or "").strip()
            if note:
                lines.append(f"  - approach + lesson: {note}")
            imp = _render_impact(e)
            if imp:
                lines.append(f"  - {imp}")
        return "\n".join(lines)


class History:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, candidate_id: str, summary: str, val: float,
            note: Optional[str] = None, impact: Optional[dict] = None) -> None:
        rec = {"candidate_id": candidate_id, "summary": summary.strip(), "val": val}
        if note and note.strip():
            rec["note"] = note.strip()
        _store_impact(rec, impact)
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
            note = (e.get("note") or "").strip()
            if note:
                lines.append(f"  - approach + lesson: {note}")
            imp = _render_impact(e)
            if imp:
                lines.append(f"  - {imp}")
        return "\n".join(lines)
