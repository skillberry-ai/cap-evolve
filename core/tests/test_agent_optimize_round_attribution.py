"""Agent-mode rounds measured their cost and their gate, then reported neither.

Three symptoms, all observed on smoke spreadsheetbench run 32971129203, all of data that the
run had already computed and written down:

1. **The report contradicted itself inside one document.** Its Suite headline said
   ``optimizer $7.95 over 3 iter(s)`` (from ``state.json``'s run-level ``spent``) while its
   Totals line said ``optimizer $0.0000 over 0s`` (summing the per-step figures, which agent
   mode does not fill in — the whole loop is ONE agent process, so there is no per-round
   optimizer cost to attribute). A reader cannot tell which number to believe.

2. **Every iterate row showed no eval cost or time** (``eval $ —``, ``eval time —``) even
   though each candidate's ``evaluate`` event carried both — cand_1 alone was $0.456 over
   629.84s. ``iteration_rows`` only looked at the ``step`` event, which agent mode's
   ``commit.py`` does not populate with eval figures.

3. **The published ``gate_decisions[]`` had ``parent_val``/``delta``/``stderr``/``n``/
   ``k_se``/``threshold`` all null**, with the numbers surviving only inside the prose
   ``reason`` string. ``commit.py``'s comment explained this as "the agent gates via
   gate_check, which prints but does not persist the parent mean" — no longer true:
   ``round.py`` persists the whole table to ``$RUN_DIR/work/round_i<N>.json``, which is where
   the drift-vs-control finding in this run was ultimately read from.

None of this fabricates a number. It reports the ones already measured, and labels the
run-level optimizer spend as whole-loop rather than pretending it was per round.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "ci" / "benchmarks" / "lib"
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"


def _metrics():
    if str(LIB) not in sys.path:
        sys.path.insert(0, str(LIB))
    spec = importlib.util.spec_from_file_location("_bench_metrics_attr", LIB / "metrics.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_bench_metrics_attr"] = mod
    spec.loader.exec_module(mod)
    return mod


# --- the round table -> gate record contract ---------------------------------------------

# The exact shape round.py writes, trimmed to the fields commit.py needs. Values are the real
# ones from run 32971129203's work/round_i0.json.
ROUND_TABLE = {
    "parent": {"tag": "seed", "reward": 0.5, "stderr": 0.14396882759686525, "n_tasks": 10},
    "gate_reference": {"tag": "seed", "mode": "parent", "reward": 0.5,
                       "stderr": 0.14396882759686525},
    "null_delta_between_control_replicates": 0.0444,
    "evidence_bar": {"value": 0.0444, "basis": "the larger of the replicate gap and drift"},
    "gated_against": {"tag": "seed", "mode": "parent"},
    "candidates": [{
        "tag": "cand_1", "reward": 0.5333333333333333,
        "gate_delta": 0.03333333333333333, "gate_threshold": 0.0439790447668071,
        "verdict": "reject", "regressions": [], "eval_rc": 0, "eval_error": None,
        "control_relative": {"reference": "ctl_null_i0", "gate_delta": 0.05555555555555556,
                             "gate_threshold": 0.03414646095293662, "verdict": "accept"},
    }],
}


def test_commit_reads_only_fields_round_actually_writes():
    """Guards the fixture above against drifting from round.py's real output."""
    src = (SCRIPTS / "round.py").read_text(encoding="utf-8")
    for key in ("\"parent\"", "\"gate_reference\"", "\"gated_against\"", "\"candidates\"",
                "gate_delta", "gate_threshold", "control_relative",
                "null_delta_between_control_replicates", "evidence_bar"):
        assert key in src, f"round.py no longer writes {key}; this fixture is stale"
    assert "round_i{int(run_dir.spent.iterations)}" in src, (
        "round.py's table filename no longer keys off spent.iterations; commit.py's lookup must "
        "follow")


def test_commit_finds_the_table_wherever_round_decided_to_name_it(tmp_path):
    """The naming coupling itself, checked by behaviour rather than by matching source text.

    The two files used to be kept in step by a filename literal duplicated in both. That is a
    guard against editing one copy, not against the schemes diverging — and the scheme now has
    two halves (iteration, and the ``.r<k>`` attempt suffix a re-gate gets). So write a table at
    the name ``round.py`` itself would choose and assert ``commit.py`` reads its numbers back.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("_ao_round_naming", SCRIPTS / "round.py")
    rnd = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(rnd)

    run_dir, work = _run_dir_with_round_table(tmp_path, table=None)
    (run_dir.root / "work").mkdir(parents=True, exist_ok=True)
    stem = rnd.table_stem(run_dir)
    (run_dir.root / "work" / f"{stem}.json").write_text(json.dumps(ROUND_TABLE),
                                                        encoding="utf-8")
    _commit(run_dir, work)
    d = _gate_decision(run_dir)
    # These can only have come from the table, since the prose note carries no numbers.
    assert d.get("threshold") == ROUND_TABLE["candidates"][0]["gate_threshold"], (
        f"commit.py did not read the table round.py would have written ({stem}.json): {d}")
    assert d.get("evidence_bar") == ROUND_TABLE["evidence_bar"]["value"]

    # And on a re-gate, the LATER attempt's table is the operative one. Checked on the lookup
    # itself rather than by booking twice, since booking one candidate id twice is a different
    # rule (and one commit.py deliberately refuses).
    spec_c = importlib.util.spec_from_file_location("_ao_commit_naming", SCRIPTS / "commit.py")
    cmt = importlib.util.module_from_spec(spec_c)
    spec_c.loader.exec_module(cmt)

    stem2 = rnd.table_stem(run_dir)
    assert stem2 != stem, "a second table did not advance the attempt index"
    later = {**ROUND_TABLE, "candidates": [{**ROUND_TABLE["candidates"][0],
                                            "gate_delta": 0.12345}]}
    (run_dir.root / "work" / f"{stem2}.json").write_text(json.dumps(later), encoding="utf-8")
    nums = cmt._round_gate_numbers(run_dir, "cand_1")
    assert nums.get("gate_table") == f"{stem2}.json" and nums.get("gate_delta") == 0.12345, (
        f"the re-gate's table did not supersede the first attempt's: {nums}")


def _run_dir_with_round_table(tmp_path, *, table: dict | None = ROUND_TABLE):
    """A live run dir mid-round: baseline done, cand_1 staged, round table written."""
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=20)
    seed = seed_capability_dir(tmp_path, level=3)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=5))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)

    work = run_dir.root / "work" / "cand_1"
    work.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir.root / "candidates" / "seed", work)
    if table is not None:
        # round.py names it from spent.iterations, which commit.py has not charged yet.
        (run_dir.root / "work" / "round_i0.json").write_text(json.dumps(table), encoding="utf-8")
    return run_dir, work


def _commit(run_dir, work, *extra):
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "commit.py"), "--run-dir", str(run_dir.root),
         "--candidate-id", "cand_1", "--from-dir", str(work),
         "--decision", "reject", "--val", "0.5333333333333333",
         "--note", "delta +0.033 within control noise 0.044", *extra],
        capture_output=True, text=True,
        env={**os.environ, "CAPEVOLVE_CORE": str(REPO / "core")})
    assert p.returncode == 0, f"commit.py failed: {p.stdout}\n{p.stderr}"
    return p


def _gate_decision(run_dir) -> dict:
    """The published gate record for the last booked round.

    ``gate_decisions[]`` is built by ``dashboard.reduce_run`` from the event stream — it is
    what the dashboard, the TUI and the CI live snapshot all read, and it is where run
    32971129203's nulls were observed. state.json does not carry it.
    """
    from cap_evolve import dashboard
    decisions = dashboard.reduce_run(run_dir)["summary"]["gate_decisions"]
    assert decisions, "the round booked no gate decision at all"
    return decisions[-1]


def test_a_booked_round_carries_its_gate_numbers_not_only_prose(tmp_path):
    run_dir, work = _run_dir_with_round_table(tmp_path)
    _commit(run_dir, work)

    d = _gate_decision(run_dir)

    assert d["parent_val"] == 0.5, (
        f"parent_val is still unpopulated though round.py measured it: {d}")
    assert d["delta"] == 0.03333333333333333, f"the gate delta was dropped: {d}"
    assert d["threshold"] == 0.0439790447668071, f"the gate threshold was dropped: {d}"
    assert d["stderr"] == 0.14396882759686525, f"the parent stderr was dropped: {d}"
    assert d["n"] == 10, f"the task count was dropped: {d}"


def test_a_booked_round_records_the_drift_free_comparison_it_measured(tmp_path):
    """The finding that mattered on run 32971129203 lived ONLY in work/round_i0.json: the
    same candidate the parent-mode gate rejected, a control-mode gate accepted. A reader of
    state.json could not see that the verdict was reference-dependent."""
    run_dir, work = _run_dir_with_round_table(tmp_path)
    _commit(run_dir, work)

    d = _gate_decision(run_dir)
    assert d.get("gate_mode") == "parent", f"the gate's REFERENCE is not recorded: {d}"
    assert d.get("control_relative_verdict") == "accept", (
        "the drift-free verdict that disagreed with the booked one is not recorded, so a "
        f"reader cannot tell that this rejection was reference-dependent: {d}")


def test_a_round_with_no_table_still_books_cleanly(tmp_path):
    """round.py's table write is best-effort (it catches OSError), and gate_check-only rounds
    never produce one. A missing table must not break booking or invent numbers."""
    run_dir, work = _run_dir_with_round_table(tmp_path, table=None)
    _commit(run_dir, work)

    d = _gate_decision(run_dir)
    assert d["candidate"] == "cand_1" and d["verdict"] == "reject"
    assert d["parent_val"] is None, f"a number was invented with no table to read: {d}"


# --- the CI timeline ---------------------------------------------------------------------

def _events(tmp_path, lines: list[dict], spent: dict) -> Path:
    rd = tmp_path / "run_suite"
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "events.jsonl").write_text(
        "".join(json.dumps(l) + "\n" for l in lines), encoding="utf-8")
    (rd / "state.json").write_text(json.dumps({"best_id": "seed", "spent": spent}))
    (rd / "baseline.json").write_text(json.dumps(
        {"val": {"reward": 0.5, "per_task": [{"task_id": "t1", "reward": 0.5,
                                              "raw": {"errored": False}}]}}))
    (rd / "final.json").write_text(json.dumps(
        {"test": {"reward": 0.5444, "per_task": [{"task_id": "t1", "reward": 0.5444,
                                                  "raw": {"errored": False}}]},
         "best_id": "seed"}))
    return rd


# The agent-mode event stream: each candidate is evaluated (cost recorded there), then booked
# by commit.py, whose `step` event carries no eval figures.
AGENT_EVENTS = [
    {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5,
     "cost_usd": 0.27643775, "seconds": 608.35},
    {"kind": "evaluate", "split": "val", "tag": "cand_1", "reward": 0.5333,
     "cost_usd": 0.45601625, "seconds": 629.84},
    {"kind": "step", "candidate": "cand_1", "accept": False, "val": 0.5333},
    {"kind": "evaluate", "split": "test", "tag": "FINAL", "reward": 0.5444,
     "cost_usd": 0.31075925, "seconds": 731.28},
]


def test_an_iterate_row_reports_the_eval_cost_the_run_already_measured(tmp_path):
    m = _metrics()
    rd = _events(tmp_path, AGENT_EVENTS, {"iterations": 1, "optimizer_usd": 7.95})
    row = [r for r in m.iteration_rows(str(rd)) if r["phase"] == "iterate"][0]

    assert row["eval_usd"] == 0.45601625, (
        f"the candidate's eval cost was measured and dropped: {row}")
    assert row["eval_seconds"] == 629.84, (
        f"the candidate's eval time was measured and dropped: {row}")


def test_an_explicit_step_cost_still_wins_over_the_evaluate_fallback(tmp_path):
    """The deterministic path DOES put eval figures on the step event; it must keep them."""
    m = _metrics()
    events = [e.copy() for e in AGENT_EVENTS]
    events[2] = {**events[2], "cost_usd": 0.99, "runner_seconds": 12.0}
    rd = _events(tmp_path, events, {"iterations": 1})
    row = [r for r in m.iteration_rows(str(rd)) if r["phase"] == "iterate"][0]

    assert row["eval_usd"] == 0.99 and row["eval_seconds"] == 12.0


def test_the_totals_line_does_not_contradict_the_suite_headline(tmp_path):
    m = _metrics()
    rd = _events(tmp_path, AGENT_EVENTS, {"iterations": 3, "optimizer_usd": 7.95})
    md = m.suite_report(str(rd), "spreadsheetbench", "smoke", "Azure/gpt-5-mini-2025-08-07", 3)

    assert "optimizer $7.95 over 3 iter(s)" in md, "the headline figure changed"
    assert "optimizer $0.0000" not in md, (
        f"Totals still reports $0.0000 while the headline reports $7.95:\n{md}")
    assert "whole-loop" in md, (
        f"the run-level figure is shown without saying it is not per-round:\n{md}")


def test_per_step_optimizer_cost_is_still_summed_when_it_exists(tmp_path):
    """The deterministic path attributes optimizer spend per iteration; Totals must keep
    summing it rather than switching to the run-level number for everyone."""
    m = _metrics()
    events = [e.copy() for e in AGENT_EVENTS]
    events[2] = {**events[2], "opt_cost_usd": 4.25, "optimizer_seconds": 300.0}
    rd = _events(tmp_path, events, {"iterations": 1, "optimizer_usd": 4.25})
    md = m.suite_report(str(rd), "spreadsheetbench", "smoke", "aws/gpt-oss-120b", 1)

    assert "optimizer $4.2500 over 5m00s" in md, f"per-step attribution was lost:\n{md}"
    assert "whole-loop" not in md, f"a per-step run was labelled whole-loop:\n{md}"


def test_the_operative_re_gate_wins_past_nine_re_gates(tmp_path):
    """A same-iteration re-gate is run to SUPERSEDE the first, so the highest suffix is the
    one that counts — and `.r10` must outrank `.r2`, which a lexical sort gets backwards."""
    run_dir, work = _run_dir_with_round_table(tmp_path)
    for n, delta in ((2, 0.222), (10, 0.999)):
        t = json.loads(json.dumps(ROUND_TABLE))
        t["candidates"][0]["gate_delta"] = delta
        (run_dir.root / "work" / f"round_i0.r{n}.json").write_text(json.dumps(t))
    _commit(run_dir, work)

    assert _gate_decision(run_dir)["delta"] == 0.999, "the tenth re-gate lost to the second"
