"""The offline `mock` optimizer body — a deterministic, zero-API edit proposer.

``run-optimizer --name mock`` shells this (per the registry ``mock`` row). It
mutates files in ``--workdir`` in place from a JSON edit script
(``CAPEVOLVE_MOCK_SCRIPT`` env var, or ``mock_script.json`` near the workdir),
so the full optimize loop (propose → evaluate → gate → finalize) runs in CI with
no model and a reproducible outcome. ``apply_edits`` is imported by check.py.

Edit ops:
  - ``ensure_contains``: append ``text`` to ``file`` only if not already present
  - ``append``: always append ``text``
  - ``set``: overwrite ``file`` with ``text``
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _find_script(workdir: Path) -> Path | None:
    env = os.environ.get("CAPEVOLVE_MOCK_SCRIPT")
    if env and Path(env).exists():
        return Path(env)
    for cand in (workdir / "mock_script.json", workdir.parent / "mock_script.json"):
        if cand.exists():
            return cand
    return None


def _append_mock_journal(workdir: Path) -> None:
    """Append a minimal handover entry to JOURNAL.md, if the harness seeded one.

    The harness now escalates (logs + visibly flags) an iteration whose optimizer wrote
    an empty JOURNAL.md handover (see ``harness._reconcile_journal``). The mock optimizer
    stands in for a real one in tests, so it writes a (trivial but non-empty) handover too
    instead of tripping that escalation.
    """
    journal = workdir / "JOURNAL.md"
    if not journal.exists():
        return
    text = journal.read_text(encoding="utf-8")
    if "cap-evolve:journal-append-below" not in text:
        return
    text += "\n## Iteration (mock) — applied mock_script.json edits\n- deterministic mock edit, see mock_script.json\n"
    journal.write_text(text, encoding="utf-8")


def apply_edits(workdir: Path, edits: list[dict]) -> list[dict]:
    applied = []
    for e in edits:
        target = workdir / e["file"]
        op = e.get("op", "ensure_contains")
        text = e.get("text", "")
        target.parent.mkdir(parents=True, exist_ok=True)
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if op == "set":
            target.write_text(text, encoding="utf-8")
            applied.append({"file": e["file"], "op": op, "changed": current != text})
        elif op == "append":
            target.write_text(current + text, encoding="utf-8")
            applied.append({"file": e["file"], "op": op, "changed": True})
        elif op == "ensure_contains":
            if text.strip() and text.strip() in current:
                applied.append({"file": e["file"], "op": op, "changed": False})
            else:
                target.write_text(current + text, encoding="utf-8")
                applied.append({"file": e["file"], "op": op, "changed": True})
        else:
            raise ValueError(f"unknown mock edit op: {op!r}")
    return applied


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="mock optimizer")
    p.add_argument("--workdir", required=True)
    p.add_argument("--prompt", default=None, help="INSTRUCTIONS.md (read but, being a mock, not interpreted)")
    args = p.parse_args(argv)

    workdir = Path(args.workdir)
    script = _find_script(workdir)
    if script is None:
        # The note goes to STDERR: stdout is the machine-readable payload, and a
        # diagnostic buried in it is dropped by every layer that only parses cost.
        note = "no mock_script.json found; no edits made"
        print(f"mock optimizer: {note} (looked under {workdir} and $CAPEVOLVE_MOCK_SCRIPT)",
              file=sys.stderr, flush=True)
        print(json.dumps({"optimizer": "mock", "applied": [], "note": note}))
        return 0
    edits = json.loads(script.read_text(encoding="utf-8")).get("edits", [])
    applied = apply_edits(workdir, edits)
    _append_mock_journal(workdir)
    print(json.dumps({"optimizer": "mock", "script": str(script), "applied": applied}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
