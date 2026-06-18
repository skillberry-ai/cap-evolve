"""Tests for role-based spend tracking, optimizer-cost capture, soft spend
warnings, budget enforcement on total spend, and the pre-run cost estimate."""

import json

from cap_evolve import RunDir
from cap_evolve.rundir import Budget, Spent
from cap_evolve.harness import _parse_optimizer_cost
from cap_evolve import cli, pricing


# ---- Spent / Budget round-trip + total ------------------------------------

def test_spent_roundtrip_new_fields():
    s = Spent(usd=1.0, optimizer_usd=2.0, optimizer_tokens=10, intake_usd=0.5,
              intake_tokens=3, intake_seconds=4.0)
    assert s.total_usd == 3.5
    assert Spent.from_dict(s.to_dict()).total_usd == 3.5


def test_spent_legacy_dict_tolerated():
    # An old state.json without the new keys still loads (defaults to 0).
    s = Spent.from_dict({"usd": 2.0, "metric_calls": 5})
    assert s.optimizer_usd == 0.0 and s.intake_tokens == 0


def test_budget_roundtrip_optimizer_cap():
    b = Budget.from_dict({"max_usd": 10, "max_optimizer_usd": 3})
    assert Budget.from_dict(b.to_dict()).max_optimizer_usd == 3.0


# ---- enforcement counts ALL roles -----------------------------------------

def test_max_usd_counts_optimizer(tmp_path):
    rd = RunDir.create(tmp_path, ts="t", budget=Budget(max_usd=5.0))
    rd.update_spent(usd=2.0, optimizer_usd=3.5)  # total 5.5 >= 5.0
    exhausted, why = rd.budget_exhausted()
    assert exhausted and "max_usd" in why and "opt $3.50" in why


def test_max_optimizer_usd_separate_cap(tmp_path):
    rd = RunDir.create(tmp_path, ts="t", budget=Budget(max_optimizer_usd=1.0))
    rd.update_spent(optimizer_usd=1.5)
    exhausted, why = rd.budget_exhausted()
    assert exhausted and "max_optimizer_usd" in why


# ---- soft spend warnings fire once per crossing ---------------------------

def test_spend_warnings_once_per_threshold(tmp_path):
    rd = RunDir.create(tmp_path, ts="t", budget=Budget(max_usd=10.0))
    rd.update_spent(usd=5.0)  # 50%
    assert [w["pct"] for w in rd.record_spend_warnings()] == [50]
    assert rd.record_spend_warnings() == []  # no re-fire
    rd.update_spent(usd=3.5)  # 85% -> 80% crossing
    assert [w["pct"] for w in rd.record_spend_warnings()] == [80]
    # both warnings are in the event log exactly once each
    events = [json.loads(l) for l in (tmp_path / "run_t" / "events.jsonl").read_text().splitlines()]
    warns = [e for e in events if e["kind"] == "budget_warning"]
    assert sorted(w["pct"] for w in warns) == [50, 80]


# ---- optimizer-cost parsing from run-optimizer stdout ---------------------

def test_parse_optimizer_cost_from_runner_payload():
    stdout = json.dumps({"optimizer": "claude-code", "returncode": 0,
                         "cost": {"total_cost_usd": 0.42, "tokens": 1234}})
    assert _parse_optimizer_cost(stdout) == {"cost_usd": 0.42, "tokens": 1234}


def test_parse_optimizer_cost_absent():
    assert _parse_optimizer_cost("just some prose, no json") is None
    assert _parse_optimizer_cost(json.dumps({"cost": {"total_cost_usd": None, "tokens": None}})) is None


# ---- pricing table is real (not zeros) + estimate math --------------------

def test_pricing_known_models():
    assert pricing.lookup("claude-opus-4-8") == (5.0, 25.0)
    assert pricing.lookup("gpt-5.5") == (5.0, 30.0)
    assert pricing.lookup("totally-unknown") is None


def test_estimate_calls_and_cost(tmp_path):
    # No adapter to load → val unknown, but optimizer cost still prices off the table.
    spec = {"num_trials": 3, "max_iterations": 4, "optimizer_model": "claude-opus-4-8"}
    out = cli._estimate_core(spec, tmp_path)
    assert out["calls"]["optimizer_calls"] == 4
    assert out["cost_usd"]["optimizer_usd"] > 0


def test_estimate_calibrates_from_prior_run(tmp_path):
    # A prior run with real spend → estimate calibrates instead of using the table.
    proj = tmp_path / "project"; proj.mkdir()
    base = proj.parent
    rd = RunDir.create(base, ts="prior")
    rd.update_spent(metric_calls=10, usd=1.0, iterations=2, optimizer_usd=0.4)
    spec = {"num_trials": 1, "max_iterations": 3, "optimizer_model": "claude-opus-4-8"}
    out = cli._estimate_core(spec, proj)
    assert out["cost_usd"]["source"] == "calibrated from prior runs"
    assert out["calibration"]["usd_per_metric_call"] == 0.1
