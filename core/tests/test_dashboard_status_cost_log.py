"""The reducer keys the redesigned dashboard is built on: run status, algorithm
identity, the accept/reject/INDECISIVE distinction, the reconciling cost ledger, the
full activity log, split honesty, capabilities, and the per-algorithm extras.

Each one is asserted against a run dir built from real event shapes (the same `kind`s
the five algorithms emit), because every number in the UI has to come from evidence in
the run dir — never from a default.
"""

import json
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))


def _mk(tmp: Path, *, events, baseline=None, final=None, spec=None, budget=None):
    from cap_evolve import Budget, RunDir
    base = tmp / ".capevolve"
    base.mkdir(parents=True, exist_ok=True)
    rd = RunDir.create(base, ts="t", budget=budget or Budget())
    rd.events_path.write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    if baseline is not None:
        (rd.root / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
    if final is not None:
        (rd.root / "final.json").write_text(json.dumps(final), encoding="utf-8")
    if spec is not None:
        proj = base / "project"
        proj.mkdir(exist_ok=True)
        (proj / "capevolve.yaml").write_text(spec, encoding="utf-8")
    return rd


NOW = time.time()
_BASELINE = {"val": {"reward": 0.25, "cost_usd": 0.5, "seconds": 3.0, "tokens": 100,
                     "per_task": [{"task_id": "t1", "reward": 0.0, "feedback": "wrong"},
                                  {"task_id": "t2", "reward": 0.5, "feedback": ""}]},
             "best_id": "seed"}


def _events(*, t0=NOW, finalize=True, splits=None):
    ev = [
        {"t": t0, "kind": "splits", **(splits or {"train": [1, 2, 3, 4], "val": [5, 6],
                                                  "test": [7, 8], "seed": 0})},
        {"t": t0 + 1, "kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.25,
         "cost_usd": 0.5, "tokens": 100, "seconds": 3.0},
        {"t": t0 + 2, "kind": "baseline", "val": 0.25},
        {"t": t0 + 3, "kind": "evaluate", "split": "val", "tag": "cand_0001",
         "reward": 0.75, "cost_usd": 0.25, "tokens": 80, "seconds": 2.0},
        {"t": t0 + 4, "kind": "step", "candidate": "cand_0001", "accept": True,
         "reason": "paired Δ̄=+0.5000 > 1.0·SE=0.1000 (SE=0.1000, n=2)",
         "val": 0.75, "parent": "seed", "parent_val": 0.25,
         "optimizer_seconds": 9.0, "runner_seconds": 2.0, "cost_usd": 0.25,
         "tokens": 80, "opt_cost_usd": 1.25, "opt_tokens": 4000},
    ]
    if finalize:
        ev += [
            {"t": t0 + 5, "kind": "evaluate", "split": "test", "tag": "FINAL",
             "reward": 0.8, "cost_usd": 0.1, "tokens": 20, "seconds": 1.0},
            {"t": t0 + 6, "kind": "finalize", "test_reward": 0.8, "best_id": "cand_0001"},
        ]
    return ev


# --------------------------------------------------------------- status ----

def test_status_completed_when_finalize_sealed_the_test():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=_events(), baseline=_BASELINE,
                                     final={"test": {"reward": 0.8},
                                            "best_id": "cand_0001"}))["summary"]
        assert s["status"] == "completed"
        assert "finalize" in s["status_reason"]


def test_status_running_while_the_log_is_still_moving():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=_events(finalize=False),
                                     baseline=_BASELINE))["summary"]
        assert s["status"] == "running"


def test_status_interrupted_when_a_run_died_without_finalizing():
    """The bug the old logic had: anything unfinalized was reported "live" forever."""
    from cap_evolve import dashboard
    old = NOW - 5 * 24 * 3600
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=_events(t0=old, finalize=False),
                                     baseline=_BASELINE))["summary"]
        assert s["status"] == "interrupted"
        assert "died" in s["status_reason"] or "killed" in s["status_reason"]


def test_status_budget_exhausted_is_distinct_from_running_and_from_completed():
    from cap_evolve import dashboard
    from cap_evolve import Budget
    old = NOW - 5 * 24 * 3600
    with tempfile.TemporaryDirectory() as d:
        rd = _mk(Path(d), events=_events(t0=old, finalize=False), baseline=_BASELINE,
                 budget=Budget(max_iterations=1))
        rd.update_spent(iterations=1)
        s = dashboard.reduce_run(rd)["summary"]
        assert s["status"] == "budget_exhausted"
        assert "max_iterations" in s["status_reason"]


def test_status_awaiting_agent_for_an_agent_mode_handoff():
    """`cap-evolve run` in agent mode stops after baseline by design. That is neither
    finished nor dead nor running, and must not be reported as any of them."""
    from cap_evolve import dashboard
    old = NOW - 5 * 24 * 3600
    with tempfile.TemporaryDirectory() as d:
        rd = _mk(Path(d), events=_events(t0=old, finalize=False)[:3], baseline=_BASELINE,
                 spec="algorithm_skill: agent-optimize\norchestration_mode: agent\n")
        s = dashboard.reduce_run(rd)["summary"]
        assert s["status"] == "awaiting_agent"


def test_status_failed_when_nothing_ran():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=[]))["summary"]
        assert s["status"] == "failed"


def _startup_events(t0):
    """The first two events a real run writes: the split warning and the split sizes.

    Nothing is scored yet — a long baseline (spreadsheetbench: 10 tasks of agent
    rollouts) can sit here for many minutes before the next event lands.
    """
    return [
        {"t": t0, "kind": "splits_warning", "msg": "test overlaps train/val"},
        {"t": t0 + 0.002, "kind": "splits", "train": [1], "val": [2], "test": [2],
         "seed": 0},
    ]


def test_status_running_while_the_baseline_is_still_being_scored():
    """A live run that has not finished its baseline is RUNNING, not failed.

    Regression: run 33492876620's live snapshot showed a red `failed` badge on a
    spreadsheetbench job that was 9 minutes into its baseline. "Nothing evaluated
    yet" was checked before the freshness evidence, so every live snapshot taken
    before the first `baseline` event libelled a healthy run as dead.
    """
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(
            _mk(Path(d), events=_startup_events(NOW - 9 * 60)))["summary"]
        assert s["status"] == "running", s["status_reason"]
        assert "baseline" in s["status_reason"]


def test_status_failed_when_a_run_died_before_evaluating_anything():
    """The same shape, gone silent: that IS a failure and must still say so."""
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(
            _mk(Path(d), events=_startup_events(NOW - 5 * 24 * 3600)))["summary"]
        assert s["status"] == "failed"
        assert "no baseline and no candidate was ever evaluated" in s["status_reason"]


def test_status_failed_when_the_budget_ran_out_before_anything_was_evaluated():
    from cap_evolve import dashboard
    from cap_evolve import Budget
    with tempfile.TemporaryDirectory() as d:
        rd = _mk(Path(d), events=_startup_events(NOW - 30),
                 budget=Budget(max_iterations=1))
        rd.update_spent(iterations=1)
        s = dashboard.reduce_run(rd)["summary"]
        assert s["status"] == "failed"


def test_elapsed_of_a_live_run_is_measured_to_now_not_to_its_last_event():
    """`0s elapsed` on a run that has been alive nine minutes is the same class of
    intermediate-state lie as the red badge: first-to-last-event is not elapsed while
    the run is still writing events."""
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(
            _mk(Path(d), events=_startup_events(NOW - 9 * 60)))["summary"]
        assert s["elapsed_open"] is True
        assert s["elapsed_seconds"] >= 9 * 60


def test_elapsed_of_a_finished_run_stays_first_to_last_event():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=_events(t0=NOW - 3600),
                                     baseline=_BASELINE,
                                     final={"test": {"reward": 0.8},
                                            "best_id": "cand_0001"}))["summary"]
        assert s["elapsed_open"] is False
        assert s["elapsed_seconds"] == 6.0


def test_an_agent_mode_run_scoring_a_candidate_is_running_not_awaiting():
    """`awaiting_agent` asserts that nothing is happening. An open eval disproves it:
    the agent is scoring its first candidate right now, not waiting to be driven."""
    from cap_evolve import dashboard
    t0 = NOW - 120
    ev = _events(t0=t0, finalize=False)[:3] + [
        {"t": NOW - 60, "kind": "eval_start", "split": "val", "tag": "cand_0001",
         "rollouts": 30},
    ]
    with tempfile.TemporaryDirectory() as d:
        rd = _mk(Path(d), events=ev, baseline=_BASELINE,
                 spec="algorithm_skill: agent-optimize\norchestration_mode: agent\n")
        s = dashboard.reduce_run(rd)["summary"]
        assert s["status"] == "running", s["status_reason"]
        assert "candidate cand_0001" in s["status_reason"]


def test_an_agent_mode_handoff_with_a_closed_eval_still_awaits_the_agent():
    """The override is only for an eval still in flight — a finished baseline eval must
    not turn the genuine handoff state into a claim that work is under way."""
    from cap_evolve import dashboard
    t0 = NOW - 120
    ev = _events(t0=t0, finalize=False)[:3]
    ev.insert(1, {"t": t0 + 0.5, "kind": "eval_start", "split": "val", "tag": "seed"})
    with tempfile.TemporaryDirectory() as d:
        rd = _mk(Path(d), events=ev, baseline=_BASELINE,
                 spec="algorithm_skill: agent-optimize\norchestration_mode: agent\n")
        assert dashboard.reduce_run(rd)["summary"]["status"] == "awaiting_agent"


def test_an_open_eval_is_running_far_past_the_ordinary_stale_window():
    """Nothing is logged INSIDE an evaluation, and a real one runs for hours (639 test
    tasks; swebench builds a container per task). An `eval_start` with no closing
    `evaluate` is positive evidence that the silence is work, so the 45-min window that
    is right for the step loop must not be applied to it."""
    from cap_evolve import dashboard
    t0 = NOW - 3 * 3600
    ev = _startup_events(t0) + [
        {"t": t0 + 1, "kind": "eval_start", "split": "val", "tag": "seed",
         "n_tasks": 10, "n_trials": 1, "workers": 8, "rollouts": 10},
    ]
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=ev))["summary"]
        assert s["status"] == "running", s["status_reason"]
        assert "the seed" in s["status_reason"] and "val" in s["status_reason"]


def test_an_eval_that_never_returned_is_interrupted_not_failed():
    """"failed — nothing ran" is wrong about the one certain fact: something did run."""
    from cap_evolve import dashboard
    t0 = NOW - 20 * 3600
    ev = _startup_events(t0) + [
        {"t": t0 + 1, "kind": "eval_start", "split": "val", "tag": "seed",
         "rollouts": 10},
    ]
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=ev))["summary"]
        assert s["status"] == "interrupted"
        assert "never returned" in s["status_reason"]


def test_a_closed_eval_puts_the_ordinary_stale_window_back():
    """The wide window is only for an OPEN eval. Once `evaluate` closes it, a silent run
    is judged on the normal 45 minutes again."""
    from cap_evolve import dashboard
    t0 = NOW - 3 * 3600
    ev = _events(t0=t0, finalize=False)
    ev.insert(1, {"t": t0 + 0.5, "kind": "eval_start", "split": "val", "tag": "seed"})
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=ev, baseline=_BASELINE))["summary"]
        assert s["status"] == "interrupted"


def test_a_running_run_says_which_split_it_is_scoring():
    from cap_evolve import dashboard
    ev = _events(t0=NOW - 60, finalize=False) + [
        {"t": NOW - 30, "kind": "eval_start", "split": "test", "tag": "FINAL",
         "rollouts": 20},
    ]
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=ev, baseline=_BASELINE))["summary"]
        assert s["status"] == "running"
        assert "the best candidate" in s["status_reason"]
        assert "test split (20 rollouts)" in s["status_reason"]


def test_eval_start_is_filed_under_the_phase_its_evaluation_belongs_to():
    from cap_evolve import dashboard
    ev = _startup_events(NOW - 60) + [
        {"t": NOW - 59, "kind": "eval_start", "split": "val", "tag": "seed"},
        {"t": NOW - 58, "kind": "eval_start", "split": "test", "tag": "FINAL"},
    ]
    with tempfile.TemporaryDirectory() as d:
        rows = dashboard.reduce_run(_mk(Path(d), events=ev))["summary"]["log"]
        by_kind = [(r["kind"], r["phase"], r["detail"].get("split")) for r in rows]
        assert ("eval_start", "baseline", "val") in by_kind
        assert ("eval_start", "finalize", "test") in by_kind


# ------------------------------------------------------------ algorithm ----

def test_algorithm_inferred_from_an_algorithm_specific_event():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        ev = _events() + [{"t": NOW + 7, "kind": "gepa_start", "budget": 3}]
        s = dashboard.reduce_run(_mk(Path(d), events=ev, baseline=_BASELINE))["summary"]
        assert s["algorithm"] == "gepa"
        assert s["algorithm_source"] == "events"


def test_algorithm_falls_back_to_the_project_spec_for_a_freeform_run():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk(Path(d), events=_events()[:3], baseline=_BASELINE,
                 spec="algorithm_skill: agent-optimize   # comment\n"
                      "orchestration_mode: agent\n")
        s = dashboard.reduce_run(rd)["summary"]
        assert s["algorithm"] == "agent-optimize"
        assert s["algorithm_source"] == "capevolve.yaml"


def test_algorithm_is_none_rather_than_a_guess_when_there_is_no_evidence():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=_events()[:3],
                                     baseline=_BASELINE))["summary"]
        assert s["algorithm"] is None
        assert s["algorithm_source"] is None


# ------------------------------------------------------------ indecisive ----

def test_indecisive_step_is_not_a_rejection_and_never_sets_the_best():
    from cap_evolve import dashboard
    ev = _events(finalize=False) + [
        {"t": NOW + 7, "kind": "evaluate", "split": "val", "tag": "cand_0002",
         "reward": 0.95, "cost_usd": 0.1, "tokens": 10, "seconds": 1.0},
        {"t": NOW + 8, "kind": "step", "candidate": "cand_0002", "accept": False,
         "reason": "INDECISIVE: only 20% of val tasks produced a valid score",
         "val": 0.95, "parent": "cand_0001", "parent_val": 0.75},
        {"t": NOW + 9, "kind": "step_indecisive", "candidate": "cand_0002",
         "reason": "coverage collapse"},
    ]
    with tempfile.TemporaryDirectory() as d:
        r = dashboard.reduce_run(_mk(Path(d), events=ev, baseline=_BASELINE))
        nodes = {n["id"]: n for n in r["graph"]["nodes"]}
        s = r["summary"]
        assert nodes["cand_0002"]["status"] == "indecisive"
        assert s["counts"]["indecisive"] == 1
        assert s["counts"]["rejected"] == 0
        # 0.95 was measured on 20% of val — it describes the infrastructure, so it must
        # not become the run's best.
        assert s["best_val"] == 0.75
        assert nodes["cand_0002"]["best_so_far"] == 0.75
        verdicts = {g["candidate"]: g["verdict"] for g in s["gate_decisions"]}
        assert verdicts["cand_0002"] == "indecisive"


def test_a_tamper_detected_candidate_is_indecisive_not_failed():
    from cap_evolve import dashboard
    ev = _events(finalize=False) + [
        {"t": NOW + 7, "kind": "tamper_detected", "candidate": "cand_0003",
         "reason": "edited a protected file"},
        {"t": NOW + 8, "kind": "step", "candidate": "cand_0003", "accept": False,
         "reason": "indecisive (integrity): edited a protected file", "val": None,
         "parent": "cand_0001", "parent_val": 0.75},
    ]
    with tempfile.TemporaryDirectory() as d:
        r = dashboard.reduce_run(_mk(Path(d), events=ev, baseline=_BASELINE))
        nodes = {n["id"]: n for n in r["graph"]["nodes"]}
        assert nodes["cand_0003"]["status"] == "indecisive"
        assert nodes["cand_0003"]["val"] is None


# ---------------------------------------------------------- gate decisions ----

def test_gate_decisions_carry_delta_se_and_n_parsed_from_the_gate_reason():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=_events(),
                                     baseline=_BASELINE))["summary"]
        g = s["gate_decisions"][0]
        assert g["candidate"] == "cand_0001"
        assert g["verdict"] == "accept"
        assert g["delta"] == 0.5
        assert g["stderr"] == 0.1
        assert g["n"] == 2
        assert g["k_se"] == 1.0
        assert g["threshold"] == 0.1


def test_se_column_is_the_standard_error_not_the_k_se_bar():
    """`0.2·SE=0.0062 (SE=0.0308, n=50)` — an unanchored `SE=` search matched the BAR
    first, so the UI's SE column showed 0.0062 and the gate looked like it had compared
    Δ̄ against five times its own standard error. Real tau2-airline reason string."""
    from cap_evolve import dashboard
    ev = _events(finalize=False)
    ev[-1]["reason"] = "paired Δ̄=+0.0460 > 0.2·SE=0.0062 (SE=0.0308, n=50)"
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=ev, baseline=_BASELINE))["summary"]
        g = s["gate_decisions"][0]
        assert g["stderr"] == 0.0308, g
        assert (g["k_se"], g["threshold"]) == (0.2, 0.0062)
        assert g["n"] == 50 and g["delta"] == 0.046


def test_gate_statistics_absent_from_the_reason_are_none_not_zero():
    from cap_evolve import dashboard
    ev = _events(finalize=False)
    ev[-1]["reason"] = "accepted by hand"
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=ev, baseline=_BASELINE))["summary"]
        g = s["gate_decisions"][0]
        assert g["delta"] is None and g["stderr"] is None and g["n"] is None


# ------------------------------------------------------------ cost ledger ----

def test_cost_ledger_attributes_every_dollar_and_reconciles():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk(Path(d), events=_events(), baseline=_BASELINE,
                 final={"test": {"reward": 0.8}, "best_id": "cand_0001"})
        # Record the same spend the events describe, so the ledger has something to
        # reconcile against (this is what the real loop does via update_spent).
        rd.update_spent(usd=0.85, optimizer_usd=1.25)
        s = dashboard.reduce_run(rd)["summary"]
        led = s["cost_ledger"]
        kinds = [r["kind"] for r in led["rows"]]
        assert kinds == ["intake", "baseline_eval", "candidate_eval", "optimizer_call",
                         "test_eval"]
        # intake row is ALWAYS present, even at $0 — invisible intake cost was the bug.
        assert led["rows"][0]["phase"] == "intake"
        assert led["attributed_usd"] == 2.1        # 0.5 + 0.25 + 1.25 + 0.1
        assert led["total_usd"] == 2.1
        assert led["unattributed_usd"] == 0.0
        assert [r["phase"] for r in led["rows"]] == [
            "intake", "baseline", "optimize", "optimize", "finalize"]


def test_cost_ledger_books_the_remainder_to_the_role_that_spent_it():
    """Spend recorded only in state.json's Spent is ROLE-TAGGED, so it is attributable.

    Publishing it as "unattributed" made the KPI strip show one dollar figure as both the
    run's cost and its unattributed cost (100% unattributed) while the wall-clock KPI put
    every second in the other bucket — two contradictory readings of one run. It is now a
    reconciliation row against the role Spent names, and a residual that NO role can explain
    is what "unattributed" reports.
    """
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk(Path(d), events=_events(finalize=False), baseline=_BASELINE)
        # $1.75 of optimizer spend no event carries; the eval rows already explain the runner's.
        rd.update_spent(usd=0.75, optimizer_usd=3.0)
        led = dashboard.reduce_run(rd)["summary"]["cost_ledger"]
        recon = {r["kind"]: r["usd"] for r in led["rows"] if "reconciliation" in r["kind"]}
        assert recon == {"optimizer_reconciliation": 1.75}
        assert led["total_usd"] == 3.75
        assert led["attributed_usd"] == 3.75
        assert led["unattributed_usd"] == 0.0


def test_a_budget_truncated_optimizer_call_is_labelled_and_still_charged():
    """A real run spent $6.01 against its own $6.00 cap and exited non-zero. The cost
    is real and must appear, flagged — not dropped because the process failed."""
    from cap_evolve import dashboard
    ev = _events(finalize=False) + [
        {"t": NOW + 7, "kind": "optimizer_error", "candidate": "cand_0002",
         "error": "optimizer failed (1): budget exceeded"},
        {"t": NOW + 8, "kind": "step", "candidate": "cand_0002", "accept": False,
         "reason": "paired Δ̄=+0.0000 <= 1.0·SE=0.1741 (SE=0.1741, n=12)",
         "val": 0.75, "parent": "cand_0001", "parent_val": 0.75,
         "opt_cost_usd": 6.01, "opt_tokens": 136535},
    ]
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=ev, baseline=_BASELINE))["summary"]
        row = next(r for r in s["cost_ledger"]["rows"]
                   if r["kind"] == "optimizer_call" and r["candidate"] == "cand_0002")
        assert row["usd"] == 6.01
        assert "exited non-zero" in row["label"]
        assert "still charged" in row["note"]


def test_a_cost_that_was_never_recorded_is_none_not_zero():
    from cap_evolve import dashboard
    ev = _events(finalize=False)
    del ev[-1]["opt_cost_usd"]
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=ev, baseline=_BASELINE))["summary"]
        row = next(r for r in s["cost_ledger"]["rows"] if r["kind"] == "optimizer_call")
        assert row["usd"] is None
        assert s["cost_ledger"]["rows_missing_cost"] >= 1


# ------------------------------------------------------------------- log ----

def test_log_carries_every_event_phase_tagged():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=_events(),
                                     baseline=_BASELINE))["summary"]
        log = s["log"]
        assert len(log) == len(_events())
        assert [r["kind"] for r in log][:3] == ["splits", "evaluate", "baseline"]
        by_kind = {r["kind"]: r for r in log}
        assert by_kind["baseline"]["phase"] == "baseline"
        assert by_kind["finalize"]["phase"] == "finalize"
        assert by_kind["step"]["phase"] == "optimize"
        # The seed-on-val eval IS the baseline; the sealed test eval is finalize.
        evals = [r for r in log if r["kind"] == "evaluate"]
        assert {e["phase"] for e in evals} == {"baseline", "optimize", "finalize"}
        assert all(r["t"] is not None for r in log)


def test_log_strips_control_characters_from_subprocess_authored_text():
    """Optimizer stderr is model/subprocess-authored. ANSI escapes and NULs must not
    survive into an artifact a human opens."""
    from cap_evolve import dashboard
    ev = _events(finalize=False) + [
        {"t": NOW + 7, "kind": "optimizer_error", "candidate": "cand_0002",
         "error": "boom", "error_full": "\x1b[31mred\x1b[0m\x00 and \x07bell"},
    ]
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=ev, baseline=_BASELINE))["summary"]
        row = next(r for r in s["log"] if r["kind"] == "optimizer_error")
        assert "\x1b" not in row["text"] and "\x00" not in row["text"]
        assert "red" in row["text"]


def test_log_text_is_length_capped_so_one_event_cannot_balloon_the_payload():
    from cap_evolve import dashboard
    ev = _events(finalize=False) + [
        {"t": NOW + 7, "kind": "optimizer_error", "candidate": "c",
         "error_full": "x" * 50_000},
    ]
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=ev, baseline=_BASELINE))["summary"]
        row = next(r for r in s["log"] if r["kind"] == "optimizer_error")
        assert len(row["text"]) < 6_200
        assert "truncated" in row["text"]


# ---------------------------------------------------------------- splits ----

def test_splits_flags_a_run_with_no_holdout():
    from cap_evolve import dashboard
    same = {"train": ["a", "b"], "val": ["a", "b"], "test": ["a", "b"], "seed": 1}
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=_events(splits=same),
                                     baseline=_BASELINE))["summary"]
        assert s["splits"]["no_holdout"] is True


def test_splits_reports_real_sizes_for_a_run_with_a_holdout():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=_events(),
                                     baseline=_BASELINE))["summary"]
        assert s["splits"] == {"train": 4, "val": 2, "test": 2, "seed": 0,
                               "no_holdout": False, "warning": ""}


# ---------------------------------------------------------- capabilities ----

def test_capabilities_report_only_signals_the_run_actually_emitted():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=_events(),
                                     baseline=_BASELINE))["summary"]
        caps = s["capabilities"]
        assert caps["gate"] is True and caps["cost"] is True and caps["log"] is True
        # No gepa/skillopt/evograph signal in this run ⇒ no panel offered.
        assert caps["minibatch"] is False and caps["gepa"] is False
        assert caps["skillopt"] is False and caps["evograph"] is False
        assert caps["freeform"] is False


def test_freeform_capability_is_set_for_agent_driven_algorithms():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk(Path(d), events=_events()[:3], baseline=_BASELINE,
                 spec="algorithm_skill: agent-optimize\norchestration_mode: agent\n")
        assert dashboard.reduce_run(rd)["summary"]["capabilities"]["freeform"] is True


# ------------------------------------------------------- per-algorithm ----

def test_agent_mode_accept_reject_events_become_candidates():
    """agent-optimize commits log `accept`/`reject`, not `step`. The reducer used to
    ignore them entirely, so every free-form agentic run rendered as a lone seed."""
    from cap_evolve import dashboard
    ev = [
        {"t": NOW, "kind": "splits", "train": [1], "val": [2], "test": [3], "seed": 0},
        {"t": NOW + 1, "kind": "baseline", "val": 0.25},
        {"t": NOW + 2, "kind": "reject", "candidate": "cand_r1", "val": 0.1,
         "note": "CoT nudge alone"},
        {"t": NOW + 3, "kind": "accept", "candidate": "cand_r2", "val": 0.9,
         "note": "pinned the output format"},
        {"t": NOW + 4, "kind": "reject", "candidate": "cand_r3", "val": 0.9,
         "note": "prose alongside the number"},
    ]
    with tempfile.TemporaryDirectory() as d:
        r = dashboard.reduce_run(_mk(Path(d), events=ev, baseline=_BASELINE))
        nodes = {n["id"]: n for n in r["graph"]["nodes"]}
        assert set(nodes) == {"seed", "cand_r1", "cand_r2", "cand_r3"}
        assert nodes["cand_r2"]["status"] == "accepted"
        assert nodes["cand_r1"]["status"] == "rejected"
        # The commit carried no parent edge; the gate compared against the best at the
        # time, so that is the parent recorded — cand_r3's parent is the accepted r2.
        assert nodes["cand_r1"]["parent"] == "seed"
        assert nodes["cand_r3"]["parent"] == "cand_r2"
        assert r["summary"]["counts"]["accepted"] == 1


def test_iterations_count_candidates_not_step_events():
    """skillopt logs BOTH `skillopt_step` and a plain `step` per candidate. Counting
    events made iteration numbers skip (1, 2, 4, 5)."""
    from cap_evolve import dashboard
    ev = [
        {"t": NOW, "kind": "baseline", "val": 0.25},
        {"t": NOW + 1, "kind": "skillopt_step", "candidate": "so_e01s01", "accept": True,
         "val": 0.75, "parent": "seed", "parent_val": 0.25, "epoch": 1},
        {"t": NOW + 2, "kind": "step", "candidate": "so_e01s01", "accept": True,
         "val": 0.75, "parent": "seed", "parent_val": 0.25},
        {"t": NOW + 3, "kind": "skillopt_step", "candidate": "so_e02s01", "accept": False,
         "val": 0.7, "parent": "so_e01s01", "parent_val": 0.75, "epoch": 2},
        {"t": NOW + 4, "kind": "step", "candidate": "so_e02s01", "accept": False,
         "val": 0.7, "parent": "so_e01s01", "parent_val": 0.75},
    ]
    with tempfile.TemporaryDirectory() as d:
        r = dashboard.reduce_run(_mk(Path(d), events=ev, baseline=_BASELINE))
        iters = sorted(n["iteration"] for n in r["graph"]["nodes"] if n["id"] != "seed")
        assert iters == [1, 2]
        assert r["summary"]["algo_extra"]["epochs"] == [1, 2]


def test_minibatch_events_become_a_gepa_extra():
    from cap_evolve import dashboard
    ev = _events(finalize=False) + [
        {"t": NOW + 7, "kind": "gepa_start", "budget": 3},
        {"t": NOW + 8, "kind": "minibatch", "tag": "gepa_0002", "reward": 0.4,
         "n_tasks": 3, "tasks": ["a", "b", "c"]},
    ]
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=ev, baseline=_BASELINE))["summary"]
        assert s["capabilities"]["minibatch"] is True
        mb = s["algo_extra"]["minibatch"][0]
        assert mb["candidate"] == "gepa_0002" and mb["reward"] == 0.4
        assert [e["kind"] for e in s["algo_extra"]["gepa"]] == ["gepa_start"]


def test_evograph_wiki_is_read_from_the_run_dir_no_second_server():
    """The weakness graph used to require its own server behind an iframe. It is a set
    of files in the run dir, so the reducer reads them directly."""
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk(Path(d), events=_events()[:3], baseline=_BASELINE)
        wiki = Path(rd.root) / "wiki"
        (wiki / "results").mkdir(parents=True)
        (wiki / "weaknesses").mkdir(parents=True)
        (wiki / "solutions" / "arith" / "sol-01").mkdir(parents=True)
        (wiki / "results" / "round-1.json").write_text(json.dumps({
            "round": 1, "split": "train", "num_tasks": 2,
            "started_at": "2026-08-15T09:00:00+03:00",
            "completed_at": "2026-08-15T09:01:00+03:00",
            "metrics": {"reward": {"value": 0.5, "primary": True, "direction": "higher"},
                        "steps": {"value": 9, "primary": False, "direction": "lower"}},
        }), encoding="utf-8")
        (wiki / "weaknesses" / "arith.md").write_text(
            "---\nslug: arith\nstatus: solved\ntags: [output-format, arithmetic]\n"
            "discovered_in_round: 1\naffected_tasks: [t1, t2]\nrelated: [verbosity]\n"
            "---\nprose body\n", encoding="utf-8")
        s = dashboard.reduce_run(rd)["summary"]
        assert s["algorithm"] == "evograph"
        assert s["algorithm_source"] == "run-dir wiki/"
        assert s["capabilities"]["evograph"] is True
        eg = s["algo_extra"]["evograph"]
        assert eg["rounds"][0]["primary_metric"] == "reward"
        assert eg["rounds"][0]["metrics"] == {"reward": 0.5, "steps": 9}
        w = eg["weaknesses"][0]
        assert w["slug"] == "arith" and w["status"] == "solved"
        assert w["tags"] == ["output-format", "arithmetic"]
        assert w["affected_tasks"] == ["t1", "t2"]
        assert w["num_solutions"] == 1


# --------------------------------------------------------------- timing ----

def test_elapsed_is_distinct_from_summed_measured_time():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        s = dashboard.reduce_run(_mk(Path(d), events=_events(),
                                     baseline=_BASELINE))["summary"]
        # 6s between the first and last event, but 14s of MEASURED time (3s baseline
        # eval + 9s optimizer + 2s candidate eval): the two numbers answer different
        # questions and the UI must not present one as the other.
        assert s["elapsed_seconds"] == 6.0
        assert s["wall_clock_seconds"] == 14.0
        assert s["event_count"] == len(_events())
