"""system-prompt capability — concrete handlers for a prompt/policy artifact.

A "system prompt" capability is one or more text files (default ``prompt.txt``)
that constitute the agent's instructions/policy. These handlers are concrete (a
prompt is just text), so there is nothing to stub — they form a small reusable
library a project adapter's ``apply`` can call.

Edit schema (what an optimizer may emit, mirrored by the mock ops):
    {"file": "prompt.txt", "op": "set"|"append"|"ensure_contains", "text": "..."}
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_FILES = ["prompt.txt", "policy.md", "SYSTEM.md"]


def materialize(capability_dir: Path) -> dict:
    """Read the prompt artifact into a named-component dict (gepa's view)."""
    capability_dir = Path(capability_dir)
    parts = {}
    for name in DEFAULT_FILES:
        f = capability_dir / name
        if f.exists():
            parts[name] = f.read_text(encoding="utf-8")
    if not parts:
        # fall back to any single .txt/.md file present
        for f in sorted(capability_dir.glob("*.txt")) + sorted(capability_dir.glob("*.md")):
            parts[f.name] = f.read_text(encoding="utf-8")
    return parts


def apply(capability_dir: Path, edits: list[dict] | None = None) -> dict:
    """Apply edits to the prompt files. Returns a report of what changed."""
    capability_dir = Path(capability_dir)
    report = {"changed": []}
    for e in edits or []:
        target = capability_dir / e["file"]
        op = e.get("op", "set")
        text = e.get("text", "")
        cur = target.read_text(encoding="utf-8") if target.exists() else ""
        if op == "set":
            new = text
        elif op == "append":
            new = cur + text
        elif op == "ensure_contains":
            new = cur if text.strip() and text.strip() in cur else cur + text
        else:
            raise ValueError(f"unknown op {op!r}")
        if new != cur:
            target.write_text(new, encoding="utf-8")
            report["changed"].append(e["file"])
    return report


def is_empty(capability_dir: Path) -> bool:
    """Return True when the capability directory has no meaningful content yet.

    "Meaningful" is judged after ``strip()`` — the same notion of non-empty that
    ``validate()`` uses — so a missing prompt file and an empty/whitespace-only one
    are both treated as an empty seed (nothing for the optimizer to build on yet)."""
    return not any(v.strip() for v in materialize(Path(capability_dir)).values())


def validate(capability_dir: Path) -> dict:
    """A prompt artifact is valid if it has at least one non-empty text file.

    A capability with no non-empty (non-whitespace) prompt content is accepted as a
    valid empty-seed starting state so the optimizer can create the initial content
    from failing trajectories."""
    capability_dir = Path(capability_dir)
    if is_empty(capability_dir):
        return {"ok": True, "empty": True, "files": [], "problems": [], "warnings": []}
    parts = materialize(capability_dir)
    nonempty = {k: v for k, v in parts.items() if v.strip()}
    return {"ok": bool(nonempty), "files": list(nonempty),
            "problems": [] if nonempty else ["no non-empty prompt file found"]}
