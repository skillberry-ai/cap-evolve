"""Contract: the probe reports presence of the three declared fields, and NEVER rejects.

The behavioral bar, in three parts:
  1. a filled declaration parses all three fields;
  2. the seed's ``<...>`` placeholders count as MISSING (otherwise the check would pass
     vacuously on an untouched PROCESS.md);
  3. a genuine mechanism-style declaration is NOT rejected — there is no reject path at
     all. This is the false-rejection probe: the gate is advisory by construction.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import proposal_quality
from cap_evolve.skillcheck import Checker, import_run


class StubRunDir:
    """Minimal log_event sink — the check asserts on the event, not on a real run dir."""

    def __init__(self):
        self.logged: list[dict] = []

    def log_event(self, kind: str, **fields) -> None:
        self.logged.append({"kind": kind, **fields})


def main() -> int:
    c = Checker("mechanism-probe")
    run = import_run()
    c.require_main(run)

    with tempfile.TemporaryDirectory() as d:
        wd = Path(d)

        # 1. a real declaration parses all three fields.
        (wd / "PROCESS.md").write_text(
            "# PROCESS\n\n## Proposal declaration\n"
            "- Mechanism: quote_price recomputes the total in-body and refuses a "
            "mismatch with an actionable error.\n"
            "- Hypothesis: the four tax-line failures share one root cause — the total "
            "is derived by the agent, not by code.\n"
            "- Expected observable: get_total precedes every quote_price call and the "
            "'expected N got M' feedback disappears.\n", encoding="utf-8")
        q = proposal_quality.parse(wd)
        c.check(q["declared"] and not q["missing"],
                f"a filled declaration did not parse as declared: {q}",
                note="all three declared fields parse from PROCESS.md")
        c.check("quote_price" in q["mechanism"] and "get_total" in q["observable"],
                f"field values not carried through: {q}")

        # 3. FALSE-REJECTION PROBE — a genuine mechanism-style proposal must not be
        # rejected. record() returns advisory metadata and there is no reject path.
        rd = StubRunDir()
        out = proposal_quality.record(rd, wd, "cand_0001")
        c.check(out["declared"] is True and "reject" not in str(out).lower(),
                f"record() produced a rejection signal for a genuine mechanism: {out}",
                note="false-rejection probe: a real mechanism proposal is never rejected")
        ev = rd.logged[-1] if rd.logged else {}
        c.check(ev.get("kind") == "proposal_quality"
                and ev.get("enforcement") == "advisory"
                and ev.get("declared") is True,
                f"the logged event is not an advisory proposal_quality record: {ev}",
                note="declaration is recorded per candidate as advisory")

        # 2. the seed's placeholders are MISSING, not a vacuous pass.
        (wd / "PROCESS.md").write_text(
            "## Proposal declaration\n"
            "- Mechanism: <what now behaves differently, and why>\n"
            "- Hypothesis: <which cluster this fixes>\n"
            "- Expected observable: \n", encoding="utf-8")
        q2 = proposal_quality.parse(wd)
        c.check(not q2["declared"] and sorted(q2["missing"]) ==
                ["hypothesis", "mechanism", "observable"],
                f"seed placeholders were accepted as a declaration: {q2}",
                note="unfilled placeholders count as missing (no vacuous pass)")

        # a missing PROCESS.md must not raise.
        (wd / "PROCESS.md").unlink()
        c.check(proposal_quality.parse(wd)["declared"] is False,
                "a missing PROCESS.md did not degrade to declared=False")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
