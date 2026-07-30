"""The proposal-quality declaration: what the optimizer said it was doing, and why.

Issue #140 asks for a "mechanism, not knob" gate on proposal quality. Two halves,
with very different epistemic standing — kept separate on purpose:

  * **The judgement** ("is this a real mechanism change or just a config knob?") is not
    something pure Python can decide. A regex over a diff cannot tell a one-line guard
    that fixes a whole failure class from a one-line knob tweak, and a false rejection
    silently discards a real improvement. So that half is ADVISORY: it lives as a bar in
    the prompt, carried by the ``mechanism-probe`` reasoning skill that
    ``optimizer_context.inject`` copies into the optimizer's workdir.

  * **The declaration** ("did the optimizer state a mechanism, a hypothesis and an
    expected observable?") IS precisely checkable — it is presence of three named
    fields in the ``PROCESS.md`` the optimizer already writes. That is what this module
    parses, and it is recorded per candidate as a ``proposal_quality`` event.

**Nothing here rejects a candidate.** ``parse``/``record`` are read-only: they log. The
val significance gate remains the only thing that can reject an edit, exactly as before
— the same "advisory at the prompt, hard at the val gate" split #129 settled on. A
missing declaration is a signal that the iteration skipped its reasoning step, not proof
that the edit is bad; treating it as proof would throw away real gains invisibly.

Pure stdlib, zero model calls (see #205: every auxiliary step in core is pure Python).
"""

from __future__ import annotations

import re
from pathlib import Path

# The three declared fields, in prompt order. The key is the log field; the pattern is
# the heading the optimizer writes in PROCESS.md (seeded by ``harness._PROCESS_SEED``).
FIELDS = ("mechanism", "hypothesis", "observable")
_LABELS = {
    "mechanism": r"mechanism",
    "hypothesis": r"hypothesis",
    "observable": r"expected\s+observable",
}
# A value that is still the seed's angle-bracket prompt, or empty, is not a declaration.
_PLACEHOLDER_RE = re.compile(r"^\s*(<.*>|[-–—.]*|n/?a|tbd|todo)\s*$", re.I)
MAX_VALUE_CHARS = 400


def _field(text: str, label: str) -> str:
    """The value the optimizer wrote for one declared field, or "".

    Tolerant of the shapes an agent actually writes: an optional leading list marker or
    bold/emphasis markup, then the label, then ``:``, then the value up to end of line.
    """
    m = re.search(rf"^[ \t]*(?:[-*+][ \t]*)?[*_]{{0,2}}{label}[*_]{{0,2}}[ \t]*:[ \t]*(.*)$",
                  text, re.I | re.M)
    if not m:
        return ""
    value = m.group(1).strip().strip("*_` ")
    if _PLACEHOLDER_RE.match(value):
        return ""
    return value[:MAX_VALUE_CHARS]


def parse(workdir: Path) -> dict:
    """Read the proposal declaration out of ``workdir/PROCESS.md``.

    Returns ``{declared, missing, mechanism, hypothesis, observable}``. ``declared`` is
    True only when all three fields carry a real (non-placeholder) value. A missing
    PROCESS.md yields ``declared=False`` with every field missing — never raises, since
    a proposal step must not be able to crash a run.
    """
    proc = Path(workdir) / "PROCESS.md"
    try:
        text = proc.read_text(encoding="utf-8") if proc.is_file() else ""
    except Exception:  # noqa: BLE001
        text = ""
    out = {k: _field(text, _LABELS[k]) for k in FIELDS}
    out["missing"] = [k for k in FIELDS if not out[k]]
    out["declared"] = not out["missing"]
    return out


def record(run_dir, workdir: Path, cid: str) -> dict:
    """Parse the declaration and log it as a ``proposal_quality`` event for ``cid``.

    Called right after the optimizer returns, by every algorithm. ADVISORY ONLY — the
    return value is informational and no caller branches on it to reject; the candidate
    goes to the val gate either way.
    """
    q = parse(workdir)
    try:
        run_dir.log_event("proposal_quality", candidate=cid, declared=q["declared"],
                          missing=q["missing"], mechanism=q["mechanism"],
                          hypothesis=q["hypothesis"], observable=q["observable"],
                          enforcement="advisory")
    except Exception:  # noqa: BLE001 — logging must never break a step
        pass
    return q


# The prompt-side half: the bar itself. Appended by ``harness._augment_instructions`` so
# all three deterministic algorithms get it identically, and capped with everything else
# by ``optimizer_context.cap_instructions``. Kept SHORT (~1.4 KB) on purpose: it lands in
# the 30%-of-budget tail that survives an overflow, so it must not crowd out #129's
# dead-end constraints (~7 KB at 200 rejections) that live there too.
PROMPT_BLOCK = (
    "## Proposal quality — declare the MECHANISM, not a knob (advisory bar)\n"
    "Read `./guidance/reasoning/mechanism-probe/SKILL.md` BEFORE you decide what to edit. "
    "It counters the failure mode this framework keeps paying for: skipping the analysis "
    "and shipping a plausible one-line tweak.\n"
    "Fill the **Proposal declaration** block in `./PROCESS.md` — three fields:\n"
    "- `Mechanism:` what in the system now behaves differently, and WHY that changes the "
    "outcome. A *knob* restates an existing rule or retunes a value the agent already "
    "ignores; a *mechanism* changes what is structurally possible (an in-code guard, a "
    "computation, a new/composite tool, a narrowed decision rule).\n"
    "- `Hypothesis:` which failure cluster this fixes and why it generalizes beyond the "
    "exact failing inputs.\n"
    "- `Expected observable:` the concrete change you expect in the NEXT iteration's "
    "trajectories if the hypothesis holds — something a reader could check.\n"
    "**How this is judged:** the declaration is RECORDED per candidate, not enforced — a "
    "missing or knob-shaped declaration does NOT reject your edit, and a well-declared one "
    "does not get it accepted. The val significance gate remains the only thing that "
    "accepts or rejects. Declare it anyway: an edit you cannot state a mechanism and an "
    "observable for is the edit that historically wasted the iteration.\n"
)
