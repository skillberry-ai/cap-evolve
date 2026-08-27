"""The published cost of a run was a sum of per-step attributions, so unattributed spend vanished.

``record.rollup`` builds a run's headline cost by summing ``steps.jsonl`` — one row per phase
(baseline, each committed round, finalize). Any money the run metered that no phase owns is
therefore not merely unattributed: it is published as if it had never been spent. Two independent
holes fed that, and smoke spreadsheetbench run 33046360451 hit both at once:

* **Agent mode meters the optimizer once for the whole loop.** One agent process drives every
  round, so no round can own a share of its cost. The run's own state held
  ``optimizer_usd: 9.11``; the published record said ``suite.optimizer_usd: 0``.
* **Not every evaluation belongs to a committed step.** Control replicates, re-gates and
  abandoned rounds are real rollouts against the real gateway. ``spent.usd`` was ``12.55``
  while the summed step rows came to ``5.25``.

The record went out as $5.25 for a run that metered $21.66 — a 4x understatement in the single
figure a full tier's budget gets projected from, and one that reads as a completed, green,
cheap run. Both halves are fixed by giving the residual a row of its own rather than by
inventing a per-round split that the run never measured.

The second defect here is upstream of that: the host meters the whole agent process AND the
skill tells the agent to book its own proposal cost per round through ``commit.py
--optimizer-usd``. Those are the same money. An agent that complied made the run report
roughly twice the optimizer spend it used, which is worse than the understatement it sits
next to, because a cost-based ``stop_condition`` would then end a run that still had budget.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ci" / "benchmarks" / "lib"))

import metrics  # noqa: E402
import record  # noqa: E402

HOST = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts" / "host.py"


def _run(tmp_path, *, events: list[dict], spent: dict) -> Path:
    """A minimal run dir: the event stream a report is built from, plus the run's own meters."""
    rd = tmp_path / "run"
    rd.mkdir()
    (rd / "events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    (rd / "state.json").write_text(json.dumps({"best_id": "seed", "spent": spent}),
                                   encoding="utf-8")
    return rd


# One round, committed, whose candidate eval cost $1. The run also paid $4 more in rollouts
# (control replicates and a re-gate) and $9 of optimizer, neither of which any step claims.
AGENT_EVENTS = [
    {"kind": "evaluate", "tag": "seed", "split": "val", "reward": 0.5, "cost_usd": 1.0,
     "seconds": 60.0},
    {"kind": "evaluate", "tag": "cand_1", "split": "val", "reward": 0.55, "cost_usd": 1.0,
     "seconds": 60.0},
    {"kind": "step", "candidate": "cand_1", "accept": False, "val": 0.55},
    {"kind": "evaluate", "tag": "FINAL", "split": "test", "reward": 0.5, "cost_usd": 1.0,
     "seconds": 60.0},
]
AGENT_SPENT = {"iterations": 1, "usd": 7.0, "optimizer_usd": 9.0, "optimizer_seconds": 3600.0,
               "runner_seconds": 400.0, "metric_calls": 100}


def test_metered_optimizer_spend_is_not_published_as_zero(tmp_path):
    rd = _run(tmp_path, events=AGENT_EVENTS, spent=AGENT_SPENT)
    rows = metrics.iteration_rows(str(rd), best_id="seed")
    total = sum(r.get("optimizer_usd") or 0.0 for r in rows)
    assert abs(total - 9.0) < 1e-6, (
        f"the timeline accounts for ${total:.2f} of a metered $9.00 of optimizer spend; agent "
        f"mode attributes none of it per round, so summing the rows publishes $0: {rows}")


def test_evaluations_that_belong_to_no_step_are_still_paid_for(tmp_path):
    rd = _run(tmp_path, events=AGENT_EVENTS, spent=AGENT_SPENT)
    rows = metrics.iteration_rows(str(rd), best_id="seed")
    total = sum(r.get("eval_usd") or 0.0 for r in rows)
    assert abs(total - 7.0) < 1e-6, (
        f"the timeline accounts for ${total:.2f} of a metered $7.00 of rollout spend — the "
        f"control replicates and re-gates that no committed step references were dropped: {rows}")


def test_the_residual_is_its_own_row_not_charged_to_a_round_that_did_not_spend_it(tmp_path):
    rd = _run(tmp_path, events=AGENT_EVENTS, spent=AGENT_SPENT)
    rows = metrics.iteration_rows(str(rd), best_id="seed")
    rounds = [r for r in rows if r["phase"] == "iterate"]
    assert len(rounds) == 1 and (rounds[0]["optimizer_usd"] or 0.0) == 0.0, (
        "the whole-loop optimizer cost was split onto a round, inventing an attribution the run "
        f"never measured: {rounds}")
    resid = [r for r in rows if r["phase"] == "unattributed"]
    assert len(resid) == 1, f"no unattributed row: {rows}"
    assert resid[0]["iter"] is None and resid[0]["accepted"] is None, (
        f"the residual row poses as a round: {resid[0]}")


def test_the_published_record_totals_what_the_run_actually_metered(tmp_path):
    """The regression as a consumer sees it: ``suite.eval_usd``/``optimizer_usd`` in the record
    that lands on the history page and drives every cost projection."""
    rd = _run(tmp_path, events=AGENT_EVENTS, spent=AGENT_SPENT)
    steps = metrics.iteration_rows(str(rd), best_id="seed")
    tasks = [{"task": "t1", "reward_baseline": 0.5, "reward_opt": 0.5, "opt_infra": False}]
    suite = record.rollup(tasks, steps)
    assert suite is not None
    published = (suite["eval_usd"] or 0) + (suite["optimizer_usd"] or 0)
    metered = AGENT_SPENT["usd"] + AGENT_SPENT["optimizer_usd"]
    assert abs(published - metered) < 1e-6, (
        f"the record publishes ${published:.2f} for a run that metered ${metered:.2f}; a tier's "
        f"budget projected from this figure is off by {metered / max(published, 1e-9):.1f}x")


def test_a_run_that_attributes_everything_per_round_gets_no_residual_row(tmp_path):
    """Control: the deterministic loops DO book optimizer cost per step. Nothing is missing
    there, and a $0.00 row saying so would be noise."""
    events = [
        {"kind": "evaluate", "tag": "seed", "split": "val", "reward": 0.5, "cost_usd": 2.0,
         "seconds": 10.0},
        {"kind": "step", "candidate": "cand_1", "accept": True, "val": 0.6, "cost_usd": 3.0,
         "runner_seconds": 20.0, "opt_cost_usd": 4.0, "optimizer_seconds": 30.0},
    ]
    rd = _run(tmp_path, events=events,
              spent={"usd": 5.0, "optimizer_usd": 4.0, "optimizer_seconds": 30.0,
                     "runner_seconds": 30.0})
    rows = metrics.iteration_rows(str(rd), best_id="cand_1")
    assert [r["phase"] for r in rows] == ["baseline", "iterate"], (
        f"a fully-attributed run grew a residual row: {rows}")


def test_an_unmetered_run_cannot_produce_a_negative_residual(tmp_path):
    """Not every gateway reports cost. ``spent.usd == 0`` with priced events must not subtract."""
    rd = _run(tmp_path, events=AGENT_EVENTS,
              spent={"usd": 0.0, "optimizer_usd": 0.0, "iterations": 1})
    rows = metrics.iteration_rows(str(rd), best_id="seed")
    assert not [r for r in rows if r["phase"] == "unattributed"], (
        f"an unmetered run invented a residual: {rows}")
    assert all((r.get("eval_usd") or 0.0) >= 0.0 for r in rows)


def test_a_run_dir_without_state_json_still_reports_its_timeline(tmp_path):
    """Older artifacts and partial runs have no meters to reconcile against."""
    rd = tmp_path / "bare"
    rd.mkdir()
    (rd / "events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in AGENT_EVENTS), encoding="utf-8")
    rows = metrics.iteration_rows(str(rd), best_id="seed")
    assert [r["phase"] for r in rows] == ["baseline", "iterate", "finalize"], rows


# --------------------------------------------------------------- the host's own booking


def _host():
    import importlib.util

    spec = importlib.util.spec_from_file_location("_host_cost_booking", HOST)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(HOST.parent))
    spec.loader.exec_module(mod)
    return mod


def test_the_host_does_not_book_optimizer_cost_the_agent_already_booked():
    """The host meters the agent process; the agent books rounds inside it. Same money."""
    host = _host()
    book = host.optimizer_spend_to_book(
        {"usd": 9.0, "tokens": 60_000, "seconds": 3600.0},
        {"usd": 0.0, "tokens": 0, "seconds": 0.0},          # nothing booked before the agent ran
        {"usd": 6.0, "tokens": 40_000, "seconds": 2000.0})  # the agent attributed this per round
    assert abs(book["usd"] - 3.0) < 1e-9, (
        f"booked ${book['usd']:.2f} on top of the $6.00 the agent already attributed, so the run "
        "reports $15.00 for $9.00 of metered spend")
    assert book["tokens"] == 20_000 and abs(book["seconds"] - 1600.0) < 1e-9


def test_a_resumed_run_does_not_lose_the_new_agents_spend():
    """An earlier host invocation's spend sits in the same counter and is not this agent's
    attribution to net out — bracketing the invocation is what keeps the two apart."""
    host = _host()
    book = host.optimizer_spend_to_book(
        {"usd": 9.0, "tokens": 0, "seconds": 0.0},
        {"usd": 20.0, "tokens": 0, "seconds": 0.0},   # a previous host already spent $20
        {"usd": 20.0, "tokens": 0, "seconds": 0.0})   # this agent attributed nothing
    assert abs(book["usd"] - 9.0) < 1e-9, (
        f"booked ${book['usd']:.2f}: a resumed run's earlier spend was mistaken for this agent's "
        "own attribution, so the whole second invocation went unrecorded")


def test_an_agent_that_over_attributes_cannot_drive_a_booking_negative():
    host = _host()
    book = host.optimizer_spend_to_book(
        {"usd": 1.0, "tokens": 10, "seconds": 5.0},
        {"usd": 0.0, "tokens": 0, "seconds": 0.0},
        {"usd": 99.0, "tokens": 0, "seconds": 0.0})   # guessed its own cost wildly high
    assert book == {"usd": 0.0, "tokens": 10, "seconds": 5.0}, (
        f"one over-attributed role leaked into the others or went negative: {book}")


def test_the_host_records_how_long_the_optimizer_ran():
    """`optimizer_seconds: 0.0` for a loop that ran for hours made every per-hour cost figure
    undefined and printed a dash where metrics.py reports the whole-loop total."""
    host = _host()
    book = host.optimizer_spend_to_book(
        {"usd": 9.0, "tokens": 0, "seconds": 3600.0},
        {"usd": 0.0, "tokens": 0, "seconds": 0.0},
        {"usd": 0.0, "tokens": 0, "seconds": 0.0})
    assert book["seconds"] == 3600.0, f"the loop's wall time was not booked at all: {book}"
