"""system-prompt capability — concrete handlers for a prompt/policy artifact.

A "system prompt" capability is one or more text files (default ``prompt.txt``)
that constitute the agent's instructions/policy. These handlers are concrete (a
prompt is just text), so there is nothing to stub — they form a small reusable
library a project adapter's ``apply`` can call.

Edit schema (what an optimizer may emit, mirrored by the mock ops):
    {"file": "prompt.txt", "op": "set"|"append"|"ensure_contains", "text": "..."}

``apply`` and ``validate`` also account for CONSTRAINT-BEARING lines, so the
never-drop-a-needed-rule invariant is reported rather than merely documented: an
optimizer that deletes a rule to make one iteration's metric go up leaves the class
permanently broken, and ``op: "set"`` can do it in a single edit. The accounting is a
crude line count -- it flags a net loss for a human or the optimizer to justify and
cannot tell a legitimate consolidation from a lost rule -- so it is a warning, never a
failure.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_FILES = ["prompt.txt", "policy.md", "SYSTEM.md"]

# Markdown scaffolding that carries no constraint on its own.
_STRUCTURE_CHARS = set("-=*_ \t")


def rule_lines(text: str) -> int:
    """Count the constraint-bearing lines of a prompt.

    Headings, code fences and horizontal rules structure a prompt without stating a
    rule; every other non-blank line might state one. Deliberately crude: the number
    only has to make a NET LOSS visible, not judge meaning.
    """
    n = 0
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("```") or set(s) <= _STRUCTURE_CHARS:
            continue
        n += 1
    return n


def _stats(parts: dict) -> dict:
    """Per-file size signals so "the preamble is too long" becomes a number."""
    return {
        name: {"lines": len(text.splitlines()),
               "tokens": len(text) // 4,  # ~chars/4, the same estimate skill-package uses
               "rule_lines": rule_lines(text)}
        for name, text in parts.items()
    }


def _rule_loss(before: str, after: str) -> int:
    """How many constraint-bearing lines an edit removed (0 when it added or held)."""
    return max(0, rule_lines(before) - rule_lines(after))


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
    report = {"changed": [], "warnings": []}
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
            lost = _rule_loss(cur, new)
            target.write_text(new, encoding="utf-8")
            report["changed"].append(e["file"])
            if lost:
                report["warnings"].append(
                    f"{e['file']}: op {op!r} removed {lost} constraint-bearing line(s) "
                    f"({rule_lines(cur)} -> {rule_lines(new)}). Change/consolidate/add rather "
                    f"than delete: confirm every dropped constraint survives somewhere "
                    f"(rewritten, merged, or enforced deterministically) and say where in "
                    f"PROCESS.md.")
    return report


def is_empty(capability_dir: Path) -> bool:
    """Return True when the capability directory has no meaningful content yet.

    "Meaningful" is judged after ``strip()`` — the same notion of non-empty that
    ``validate()`` uses — so a missing prompt file and an empty/whitespace-only one
    are both treated as an empty seed (nothing for the optimizer to build on yet)."""
    return not any(v.strip() for v in materialize(Path(capability_dir)).values())


def validate(capability_dir: Path, baseline: Path | dict | None = None) -> dict:
    """A prompt artifact is valid if it has at least one non-empty text file.

    A capability with no non-empty (non-whitespace) prompt content is accepted as a
    valid empty-seed starting state so the optimizer can create the initial content
    from failing trajectories.

    ``baseline`` is the text this candidate was derived from -- a directory (e.g. the
    parent candidate) or an already-materialized ``{file: text}`` dict. When given,
    a file carrying fewer constraint-bearing lines than its baseline is reported in
    ``warnings``. ``warnings`` is always present on both branches so a caller can read
    it without guarding.
    """
    capability_dir = Path(capability_dir)
    if is_empty(capability_dir):
        return {"ok": True, "empty": True, "files": [], "stats": {},
                "problems": [], "warnings": []}
    parts = materialize(capability_dir)
    nonempty = {k: v for k, v in parts.items() if v.strip()}
    warnings = []
    if baseline is not None:
        base = baseline if isinstance(baseline, dict) else materialize(Path(baseline))
        for name, text in sorted(base.items()):
            lost = _rule_loss(text, parts.get(name, ""))
            if lost:
                warnings.append(
                    f"{name}: {lost} constraint-bearing line(s) fewer than the baseline "
                    f"({rule_lines(text)} -> {rule_lines(parts.get(name, ''))}). A needed "
                    f"rule must be changed, consolidated, or relocated -- not dropped; "
                    f"record where each one went.")
    return {"ok": bool(nonempty), "files": list(nonempty), "stats": _stats(nonempty),
            "problems": [] if nonempty else ["no non-empty prompt file found"],
            "warnings": warnings}
