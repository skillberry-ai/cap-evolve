"""Contract: implement-and-check is a real gate — it reports ok=False (and exit
nonzero) for a project whose adapter is missing or stubbed, rather than passing.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.check import run_check
from cap_evolve.skillcheck import Checker, import_run


def main() -> int:
    c = Checker("implement-and-check")
    c.require_main(import_run())

    # A project with no adapter must NOT pass the gate.
    with tempfile.TemporaryDirectory() as d:
        empty = Path(d) / "project"
        empty.mkdir()
        rep = run_check(empty)
        c.check(not rep.ok and rep.problems,
                "check passed a project with no adapter (gate is a no-op)",
                note="refuses a project with no/stubbed adapter")

    # A stubbed adapter (IMPLEMENT-ME methods) must be flagged as stubs.
    with tempfile.TemporaryDirectory() as d:
        proj = Path(d) / "project"
        (proj / "adapters").mkdir(parents=True)
        (proj / "adapters" / "adapter.py").write_text(
            "from cap_evolve import CapabilityAdapter\n"
            "class Adapter(CapabilityAdapter):\n    pass\n", encoding="utf-8")
        rep = run_check(proj)
        c.check(not rep.ok, "check passed a stubbed adapter",
                note="flags unimplemented adapter methods")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
