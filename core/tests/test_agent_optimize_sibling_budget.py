"""An agent-mode wave of parallel siblings spends the whole round budget — say so.

The derived `stop_condition` defines a round as "one candidate taken to a full-val gate
decision", so candidates gated in the SAME wave each consume one. Nothing said so, and the
next clause reads as encouragement to go wide: "Use every round the budget allows."

Run 35861572021 (`iterations=3`) proposed cand_1a / cand_1b / cand_1c in a single wave. All
three rounds were booked, and the run ended with none left — having produced a clear result it
could not act on:

    cand_1a  prompt.md prose only   0.511  rejected, regressed 52216 and 53161
    cand_1b  task_template.md only  0.600  (grown to 9 trials -> 0.589)
    cand_1c  both surfaces          0.556

The agent's own note: "the composition landed BETWEEN its two single-surface parents
(1a 0.511 < 1c 0.556 < 1b 0.600), which points at the prompt.md prose surface costing
something." The obvious next round — re-test the winning surface alone — was unavailable.
`iterations=3` bought one wave and no iteration at all, which is the opposite of what an
evolutionary loop is for.

This is a briefing defect, not a harness one. `iterations` bounding GATE DECISIONS is what
bounds cost and what spend.py/grow.py reason about; redefining a round as a wave would let one
dispatch book unboundedly many gated candidates. So the fix makes the existing accounting
legible to the agent spending against it, and leaves the accounting alone.
"""

import re
import subprocess
from pathlib import Path

from pathlib import Path as _P

REPO = Path(__file__).resolve().parents[2]
RUN_SUITE = REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh"
WORKFLOW = REPO / ".github" / "workflows" / "benchmarks.yml"


def _algorithm_block() -> str:
    src = RUN_SUITE.read_text(encoding="utf-8")
    start = src.index('ALGORITHM="${ALGORITHM:-}"')
    return src[start:src.index("# ---- end algorithm selection", start)]


def _stop(**env: str) -> str:
    """The derived stop_condition, from the real block."""
    script = _algorithm_block() + '\nprintf "%s" "$STOP_CONDITION"\n'
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "ALGORITHM": "agent-optimize", **env})
    assert p.returncode == 0, p.stderr
    return p.stdout


# --- the new clause -----------------------------------------------------------------------


def test_the_briefing_says_parallel_siblings_each_consume_a_round():
    low = _stop(ITERATIONS="3").lower()
    assert "sibling" in low, "the briefing never mentions siblings at all"
    assert re.search(r"sibling[^.]*(consume|cost|spend)", low), (
        f"nothing tells the agent that a wave of siblings spends that many rounds: {low}"
    )


def test_the_briefing_tells_the_agent_to_keep_rounds_in_reserve():
    """The actionable half: knowing siblings cost rounds is useless without "so hold some back"."""
    low = _stop(ITERATIONS="3").lower()
    assert "reserve" in low or "hold back" in low, (
        f"the briefing does not ask the agent to reserve budget for follow-up: {low}"
    )


def test_the_warning_travels_with_the_round_count_it_applies_to():
    """The clause must be inside the derived text, so it scales with the dispatch rather than
    living in a doc the agent never reads."""
    for n in ("3", "12"):
        stop = _stop(ITERATIONS=n)
        assert n in stop and "sibling" in stop.lower()


# --- everything that was already load-bearing stays ----------------------------------------


def test_the_existing_round_and_spend_bounds_are_unchanged():
    stop = _stop(ITERATIONS="7", OPTIMIZER_USD_PER_ITER="4.0")
    assert "7" in stop and "spend.py" in stop
    assert "$28.00" in stop, f"7 rounds x $4 should still give a $28 ceiling: {stop}"


def test_rejections_still_do_not_end_the_run():
    """The clause this sits next to exists because a 'stop after two rejections' rule once
    ended a run at the exact point the algorithm prescribes escalation."""
    low = _stop(ITERATIONS="3").lower()
    assert "do not stop early merely because rounds were rejected" in low
    assert "two consecutive" not in low


def test_the_gate_and_control_requirements_are_unchanged():
    stop = _stop(ITERATIONS="3", GATE_K_SE="0.2", NUM_TRIALS="3")
    assert "gate_k_se=0.2" in stop and "3 trial(s)" in stop
    assert "--gate-against control" in stop
    assert "never gate on a screen subset" in stop


def test_the_briefing_still_ends_on_the_finalize_requirement():
    """Pinned by test_benchmarks_agent_optimize too — a run with no finalize has no result, and
    that must remain the last thing the agent reads."""
    assert _stop(ITERATIONS="3").endswith("a run with no finalize has no result.")


def test_the_deterministic_path_still_has_no_stop_condition():
    script = _algorithm_block() + '\nprintf "%s|%s" "$ORCH_MODE" "$STOP_CONDITION"\n'
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "ALGORITHM": "hill-climb-all"})
    assert p.returncode == 0, p.stderr
    assert p.stdout == "deterministic|", f"hill-climb gained agent-mode text: {p.stdout!r}"


def test_run_suite_is_valid_bash():
    assert subprocess.run(["bash", "-n", str(RUN_SUITE)]).returncode == 0


# --- the input description ----------------------------------------------------------------


def test_the_iterations_description_says_what_a_round_is_in_each_mode():
    """`iterations` means one optimizer call on the deterministic path and one CANDIDATE on the
    agent path. An operator picking 3 must be able to tell which they are buying."""
    src = WORKFLOW.read_text(encoding="utf-8")
    desc = src.split("\n      iterations:\n", 1)[1]
    desc = re.split(r"\n {6}(?=\S)", desc, maxsplit=1)[0].lower()
    assert "agent-optimize" in desc, (
        "the iterations description does not distinguish the agent-mode meaning"
    )
    assert "candidate" in desc, (
        f"it does not say that an agent-mode iteration is one candidate: {desc}"
    )
