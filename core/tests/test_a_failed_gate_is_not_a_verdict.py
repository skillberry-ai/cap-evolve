"""A gate that FAILED must not be written to the round table as a gate that decided nothing.

Observed on run 33492876620 round 3 (spreadsheetbench smoke, agent-optimize). The whole table
came back with ``reward``/``gate_delta``/``gate_threshold``/``verdict`` null for all three
candidates AND for the control, ``control_replicates: []`` and ``evidence_bar: null`` — while
``eval_rc: 0`` and all 100 rollouts were on disk, fully scored. The round was booked anyway.

Three things had to line up, and this file pins all three:

1. ``round.py``'s ``--mode`` had ``default="paired"`` and no ``choices=``, so argparse accepted
   ``--mode val`` (the agent confused it with ``--split val``, which is the default and a no-op).
   ``gate_check.py`` DOES validate ``--mode``, so it exited 2 with empty stdout.
2. ``_gate`` caught the ``json.loads`` failure and returned ``{"error": ...}`` — a dict with no
   verdict keys. The caller ``.get()``s the keys it wants, so every one came back ``None``.
3. Nothing downstream checked. A row with no reward read exactly like a row whose candidate had
   simply not moved.

There is a SECOND path to the same silent table, which is why fixing the flag alone is not
enough: ``gate_check.py``'s own two ``return 2`` paths (no ``--current`` and no ``best_id``; no
rollouts for the tag) print valid JSON — ``{"error": "..."}`` — so ``json.loads`` SUCCEEDS and
``_gate`` never even notices it failed. Both paths must be failures, not verdicts.

The one case where a missing verdict is legitimate: the candidate's own EVALUATION failed, so
there are no rollouts to gate. That row must still be written, carrying its ``eval_rc`` and
``eval_error`` — otherwise a real infrastructure failure becomes a crash instead of a report.
That is the line these tests draw: no reward AND a successful eval is a framework bug; no reward
AND a failed eval is a result.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"


def _load(name: str, modname: str):
    spec = importlib.util.spec_from_file_location(modname, SCRIPTS / name)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


def _round():
    return _load("round.py", "_ao_round_failed_gate")


def _gate_check():
    return _load("gate_check.py", "_ao_gate_check_failed_gate")


class _Proc:
    """Just enough of subprocess.CompletedProcess for _gate."""

    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


# ---------------------------------------------------------------- 1. the flag


def test_mode_rejects_a_value_gate_check_cannot_accept():
    """`--mode val` is what actually happened. It must die at the command line."""
    rnd = _round()
    with pytest.raises(SystemExit) as exc:
        rnd.main(["--run-dir", "/nonexistent", "--project", "/nonexistent",
                  "--candidates", "cand_1", "--n-trials", "10", "--mode", "val"])
    assert exc.value.code == 2, (
        "round.py accepted --mode val and passed it to gate_check.py, which rejected it and "
        "exited 2 with empty stdout — emptying the entire round table. A value the downstream "
        "script cannot accept must be refused here, before any rollout is read")


def test_round_mode_choices_are_exactly_gate_check_mode_choices():
    """The two lists must not be able to drift apart again."""
    rnd, gc = _round(), _gate_check()

    def _choices(mod, flag):
        p = mod.build_parser() if hasattr(mod, "build_parser") else None
        assert p is not None, f"{mod.__name__} needs build_parser() so its flags are inspectable"
        for a in p._actions:
            if flag in getattr(a, "option_strings", []):
                return a.choices
        raise AssertionError(f"{flag} not found in {mod.__name__}")

    assert _choices(rnd, "--mode") == _choices(gc, "--mode"), (
        "round.py forwards --mode verbatim to gate_check.py, so any value one accepts and the "
        "other rejects is a silent round-emptying bug. Deriving one list from the other is the "
        "only thing that keeps them in step")


# ---------------------------------------------------------- 2. _gate fails loudly


def test_a_crashed_gate_check_raises_instead_of_returning_a_result_shaped_dict(monkeypatch):
    """The run 33492876620 path: rc=2, empty stdout, json.loads throws."""
    rnd = _round()
    monkeypatch.setattr(rnd.subprocess, "run",
                        lambda *a, **k: _Proc(2, stdout="",
                                              stderr="round: error: argument --mode: invalid"))
    with pytest.raises(rnd.GateCheckFailed) as exc:
        rnd._gate(Path("/nonexistent"), "cand_1", 1.0, "paired", False)
    assert "cand_1" in str(exc.value) and "invalid" in str(exc.value), (
        "_gate returned {'error': ...} — a dict shaped like a verdict, with the verdict keys "
        "missing. The caller .get()s them into None and writes a row that reads as 'no movement'. "
        "It must raise, naming the tag and carrying gate_check.py's own message")


def test_gate_check_error_json_is_a_failure_too_not_a_verdict(monkeypatch):
    """The second path: gate_check.py's own `return 2` prints VALID JSON, so json.loads succeeds.

    Fixing only the ``--mode`` flag would leave this one wide open.
    """
    rnd = _round()
    payload = json.dumps({"error": "no val rollouts for tag 'cand_1' — run the evaluate phase"})
    monkeypatch.setattr(rnd.subprocess, "run",
                        lambda *a, **k: _Proc(2, stdout=payload, stderr=""))
    with pytest.raises(rnd.GateCheckFailed) as exc:
        rnd._gate(Path("/nonexistent"), "cand_1", 1.0, "paired", False)
    assert "no val rollouts" in str(exc.value), (
        "gate_check.py's two `return 2` paths print well-formed JSON, so json.loads succeeded "
        "and _gate handed back {'error': ...} without noticing the non-zero rc. A non-zero rc is "
        "a failure whether or not its stdout happens to parse")


def test_a_successful_gate_check_still_returns_its_payload(monkeypatch):
    """The fix must not turn a working gate into an exception."""
    rnd = _round()
    payload = json.dumps({"candidate": {"reward": 0.6}, "gate": {"delta": 0.05},
                          "verdict": "accept"})
    monkeypatch.setattr(rnd.subprocess, "run",
                        lambda *a, **k: _Proc(0, stdout=payload, stderr=""))
    got = rnd._gate(Path("/nonexistent"), "cand_1", 1.0, "paired", False)
    assert got["verdict"] == "accept" and got["candidate"]["reward"] == 0.6


def test_rc_zero_with_unparseable_stdout_is_also_a_failure(monkeypatch):
    """A gate that exits 0 but prints nothing usable has still not decided anything."""
    rnd = _round()
    monkeypatch.setattr(rnd.subprocess, "run",
                        lambda *a, **k: _Proc(0, stdout="Traceback (most recent call last):",
                                              stderr=""))
    with pytest.raises(rnd.GateCheckFailed):
        rnd._gate(Path("/nonexistent"), "cand_1", 1.0, "paired", False)


# ------------------------------------------------- 3. the table refuses a null row


def test_a_null_reward_row_is_refused_when_its_evaluation_succeeded():
    """The invariant that makes run 33492876620 impossible whatever the cause.

    Independent of the two fixes above: any future path to a reward-less row on a successful
    eval fails here instead of being written to the table.
    """
    rnd = _round()
    rows = [{"tag": "cand_1", "reward": None, "verdict": None, "eval_rc": 0, "eval_error": None}]
    with pytest.raises(rnd.GateCheckFailed) as exc:
        rnd.assert_rows_were_judged(rows)
    assert "cand_1" in str(exc.value), (
        "a row with eval_rc 0 and no reward means the rollouts were scored and the GATE failed. "
        "Writing it as null publishes 'this candidate did not move' for a candidate nothing "
        "judged")


def test_a_null_reward_row_is_allowed_when_the_evaluation_itself_failed():
    """A real infra failure must stay a REPORT, not become a crash."""
    rnd = _round()
    rnd.assert_rows_were_judged([
        {"tag": "cand_1", "reward": None, "verdict": None, "eval_rc": 1,
         "eval_error": "runner OOM"},
    ])


def test_a_judged_row_passes():
    rnd = _round()
    rnd.assert_rows_were_judged([
        {"tag": "cand_1", "reward": 0.6, "verdict": "accept", "eval_rc": 0, "eval_error": None},
    ])


# ------------------------------------- 4. the one case that must NOT start failing


def test_a_candidate_whose_own_evaluation_failed_does_not_crash_the_round(monkeypatch):
    """Raising on a failed gate must not turn a real infra failure into a dead round.

    If the eval failed there are no rollouts, so ``gate_check.py`` exits 2 legitimately. That
    row belongs in the table carrying its ``eval_rc``/``eval_error`` — the round reports the
    failure and the other candidates are still judged.
    """
    rnd = _round()
    monkeypatch.setattr(rnd.subprocess, "run",
                        lambda *a, **k: _Proc(2, stdout=json.dumps(
                            {"error": "no val rollouts for tag 'cand_1'"})))
    got = rnd.gate_unless_eval_failed({"tag": "cand_1", "rc": 1, "error": "runner OOM"},
                                      Path("/nonexistent"), "cand_1", 1.0, "paired", False)
    assert got == {}, (
        "the evaluation itself failed, so there was never anything to gate. This row must still "
        "be written — with its eval_rc and eval_error — rather than killing the whole round")


def test_a_successful_evaluation_with_a_failed_gate_still_raises(monkeypatch):
    """The run 33492876620 case, at the call site: eval fine, gate broken -> stop."""
    rnd = _round()
    monkeypatch.setattr(rnd.subprocess, "run",
                        lambda *a, **k: _Proc(2, stdout="", stderr="invalid --mode"))
    with pytest.raises(rnd.GateCheckFailed):
        rnd.gate_unless_eval_failed({"tag": "cand_1", "rc": 0, "error": None},
                                    Path("/nonexistent"), "cand_1", 1.0, "paired", False)


def test_the_control_row_is_held_to_the_same_bar():
    """On run 33492876620 the CONTROL was null too, which is what emptied the evidence bar."""
    rnd = _round()
    with pytest.raises(rnd.GateCheckFailed) as exc:
        rnd.assert_rows_were_judged([
            {"tag": "ctl_null_i2", "reward": None, "verdict": None, "eval_rc": 0,
             "eval_error": None},
        ])
    assert "ctl_null_i2" in str(exc.value), (
        "a null control is worse than a null candidate: control_replicates goes empty and "
        "evidence_bar goes null, so the round loses the noise floor it exists to establish")
