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

    # Behavioural: a narrow focus must render the focused task's FAILURES, not an
    # empty prompt. Comparing focus NAMES cannot see that — the schedule set stayed
    # correct the whole time the narrow schedules were shipping empty prompts.
    from cap_evolve.loop import SplitResult
    per = [{"task_id": "v1", "reward": 1.0, "feedback": "passed", "raw": {}},
           {"task_id": "v2", "reward": 0.0, "feedback": "wrong result", "raw": {}}]
    current_val = SplitResult(split="val", reward=0.5, stderr=0.5, per_task=per,
                              n_tasks=2, n_scored=2)
    rendered = harness._focus_instructions(current_val, ["v2"], "task v2")
    c.check("## (a)" in rendered,
            "a narrow focus renders no failure index — the focus set is not indexing "
            "the parent's val per-task rows",
            note="narrow focus renders the focused task's failures")
    c.check("## Currently PASSING" in rendered,
            "a narrow focus drops the protect-these-passing-tasks block",
            note="non-regression protection survives a narrow focus")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
