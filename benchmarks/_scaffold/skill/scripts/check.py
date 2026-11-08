"""Per-skill gate for <skill-name>.

Every check must prove a BEHAVIORAL contract (not just that run.py imports) via
the shared ``cap_evolve.skillcheck`` harness. The import-smoke base
(``require_main``) is kept, but add at least one real assertion about what this
skill guarantees. Exit 0 only when green; the orchestration prompt requires every
involved skill's check to be green before spending optimization budget.
"""

from __future__ import annotations

import sys

import _bootstrap  # noqa: F401  (locates cap_evolve)

from cap_evolve.skillcheck import Checker, import_run


def main() -> int:
    c = Checker("<skill-name>")
    run = import_run()
    c.require_main(run)

    # TODO per skill: assert the real contract, e.g. feed a synthetic input and
    # check the output shape, or assert an honesty invariant the skill enforces.
    # c.check(<condition>, "<what went wrong>", note="<what this proves>")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
