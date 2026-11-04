"""Launch gate (README: Isolation): is there a passing isolation check for this mode?

    python isolation_gate.py AW_EVAL MODE SETTINGS_JSON

Exit 0 iff the newest ``$AW_EVAL/runs/isolation_check/<MODE>-*/report.json`` passed and is newer
than ``SETTINGS_JSON`` (the rendered settings the run will use) and than the isolation code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
CODE = (EX / "sandbox" / "claude", EX / "sandbox" / "ns_exec.sh")


def gate(aw_eval: Path, mode: str, settings: Path) -> tuple[bool, str]:
    if not settings.is_file():
        return False, f"settings {settings} missing (run scripts/setup_project.sh)"
    reports = sorted((aw_eval / "runs" / "isolation_check").glob(f"{mode}-*/report.json"))
    if not reports:
        return False, f"no isolation check for mode {mode!r}"
    newest = reports[-1]
    rep = json.loads(newest.read_text())
    if not rep.get("pass"):
        return False, f"latest {mode} isolation check FAILED ({newest})"
    stale = [p for p in (settings, *CODE) if p.is_file() and p.stat().st_mtime > newest.stat().st_mtime]
    if stale:
        return False, f"latest {mode} isolation check predates {', '.join(map(str, stale))}"
    return True, f"isolation check {mode} PASS ({newest})"


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    ok, why = gate(Path(argv[1]), argv[2], Path(argv[3]))
    print(why, file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
