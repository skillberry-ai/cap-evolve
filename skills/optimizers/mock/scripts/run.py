"""Mock optimizer — a deterministic, zero-API edit proposer.

It mutates files in ``--workdir`` in place (the same contract every optimizer
follows), driven by a JSON edit script (``CAPEVOLVE_MOCK_SCRIPT`` env var, or
``mock_script.json`` near the workdir). This lets the full optimize loop be
exercised in tests and CI with no model and a reproducible outcome. Real
optimizer skills (claude-code, codex, ...) replace this with an actual agent that
reads ``INSTRUCTIONS.md`` and edits the files.

Edit ops:
  - ``ensure_contains``: append ``text`` to ``file`` only if not already present
  - ``append``: always append ``text`` to ``file``
  - ``set``: overwrite ``file`` with ``text``
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import _bootstrap  # noqa: F401


def _find_script(workdir: Path) -> Path | None:
    env = os.environ.get("CAPEVOLVE_MOCK_SCRIPT")
    if env and Path(env).exists():
        return Path(env)
    for cand in (workdir / "mock_script.json", workdir.parent / "mock_script.json"):
        if cand.exists():
            return cand
    return None


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
        print(json.dumps({"optimizer": "mock", "applied": [],
                          "note": "no mock_script.json found; no edits made"}))
        return 0
    edits = json.loads(script.read_text(encoding="utf-8")).get("edits", [])
    applied = apply_edits(workdir, edits)
    print(json.dumps({"optimizer": "mock", "script": str(script), "applied": applied}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
