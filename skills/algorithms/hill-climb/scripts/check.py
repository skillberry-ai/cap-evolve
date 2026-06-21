"""Contract: hill-climb wires to the shared loop and resolves every focus schedule
(including the legacy skill names) to a valid focus.
"""

from __future__ import annotations

import sys

import _bootstrap  # noqa: F401

from cap_evolve.skillcheck import Checker, import_run


def main() -> int:
    c = Checker("hill-climb")
    run = import_run()
    c.require_main(run)

    from cap_evolve import harness
    c.check(hasattr(harness, "hill_climb_loop"), "core harness missing hill_climb_loop")

    c.check(set(run.FOCUS_CHOICES) == {"all", "cyclic", "hardest-first"},
            f"unexpected focus choices: {run.FOCUS_CHOICES}",
            note=f"focus schedules: {run.FOCUS_CHOICES}")

    # Back-compat: the three old skill names must translate to a valid focus.
    for legacy in ("all-at-once", "cyclic", "hardest-first"):
        mapped = run._LEGACY_FOCUS.get(legacy, legacy)
        c.check(mapped in run.FOCUS_CHOICES,
                f"legacy name {legacy!r} does not map to a valid focus")
    c.note("legacy all-at-once/cyclic/hardest-first translate to --focus")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
