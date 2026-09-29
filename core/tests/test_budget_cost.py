"""Tests for role-based spend tracking, optimizer-cost capture, soft spend
warnings, budget enforcement on total spend, and the pre-run cost estimate."""

import importlib.util
import json
from pathlib import Path

import pytest

from cap_evolve import RunDir
from cap_evolve.rundir import Budget, Spent
from cap_evolve.harness import _parse_optimizer_cost, optimizer_from_command
from cap_evolve import cli, pricing, harness

_REPO = Path(__file__).resolve().parents[2]
_RUN_OPTIMIZER_SCRIPTS = _REPO / "skills" / "optimizers" / "run-optimizer" / "scripts"
import sys as _sys  # noqa: E402
if str(_RUN_OPTIMIZER_SCRIPTS) not in _sys.path:
    _sys.path.insert(0, str(_RUN_OPTIMIZER_SCRIPTS))  # so run.py's `import _bootstrap` resolves
_spec = importlib.util.spec_from_file_location("run_optimizer_run", _RUN_OPTIMIZER_SCRIPTS / "run.py")
run_optimizer_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_optimizer_run)


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


# ---- run-optimizer's own parse_cost must scan the WHOLE JSONL stream, not just
# the last line: a session that ends on a trailing system event (e.g. a
# `task_notification` after a background tool was killed) has no cost on its last
# line even though an earlier `result` message reported real spend. Reading only
# the last line silently books $0 for a session that actually cost money.

def test_parse_cost_finds_result_before_trailing_system_events():
    stream = "\n".join(json.dumps(o) for o in [
        {"type": "assistant", "message": {"content": []}},
        {"type": "result", "subtype": "success", "total_cost_usd": 3.65,
         "usage": {"input_tokens": 100, "output_tokens": 50}},
        {"type": "assistant", "message": {"content": []}},
        {"type": "result", "subtype": "success", "total_cost_usd": 3.86,
         "usage": {"input_tokens": 150, "output_tokens": 80}},
        {"type": "system", "subtype": "task_updated", "patch": {"status": "killed"}},
        {"type": "system", "subtype": "task_notification", "status": "stopped"},
    ])
    out = run_optimizer_run.parse_cost(stream)
    assert out["usd"] == 3.86  # the LAST result before the trailing system noise
    assert out["tokens"] == 230


def test_parse_cost_no_result_at_all():
    stream = "\n".join(json.dumps(o) for o in [
        {"type": "system", "subtype": "task_updated"},
        {"type": "system", "subtype": "task_notification"},
    ])
    out = run_optimizer_run.parse_cost(stream)
    assert out["usd"] is None


# ---- issue #562: `tokens` must be the FULL session total the CLI actually
# billed for — input + output + cache_read + cache_creation — not just
# input+output. A realistic Claude Code `--output-format json` result: most of
# a headless session's tokens are cache reads/writes (heavy prompt caching on
# a long agentic loop), so ignoring them under-reports tokens by 1-2 orders of
# magnitude while `total_cost_usd` (which the CLI bills including cache) stays
# correct — this is exactly what made $/token look 90-130x too high.

def test_parse_cost_includes_cache_tokens_in_total():
    result_event = {
        "type": "result", "subtype": "success", "is_error": False,
        "duration_ms": 245000, "num_turns": 14,
        "session_id": "sess_fixture_562",
        "total_cost_usd": 1.2345,
        "usage": {
            "input_tokens": 1200,
            "output_tokens": 3400,
            "cache_creation_input_tokens": 8000,
            "cache_read_input_tokens": 150000,
        },
    }
    out = run_optimizer_run.parse_cost(json.dumps(result_event))
    assert out["usd"] == 1.2345
    # Old formula (input+output only) would have said 4600 — off by >35x.
    assert out["tokens"] == 1200 + 3400 + 8000 + 150000 == 162600
    assert out["cache_read_tokens"] == 150000
    assert out["cache_creation_tokens"] == 8000


def test_parse_cost_camelcase_cache_fields():
    """Some CLIs' per-model usage blocks use camelCase; parse_cost must check both."""
    result_event = {"total_cost_usd": 0.5,
                     "usage": {"input_tokens": 100, "output_tokens": 200,
                               "cacheReadInputTokens": 5000,
                               "cacheCreationInputTokens": 900}}
    out = run_optimizer_run.parse_cost(json.dumps(result_event))
    assert out["tokens"] == 100 + 200 + 5000 + 900
    assert out["cache_read_tokens"] == 5000
    assert out["cache_creation_tokens"] == 900


def test_parse_cost_no_cache_fields_unaffected():
    """A session with no cache activity (or a CLI that never reports it) keeps
    the old input+output behavior — no regression for the common case."""
    result_event = {"total_cost_usd": 0.1,
                     "usage": {"input_tokens": 100, "output_tokens": 50}}
    out = run_optimizer_run.parse_cost(json.dumps(result_event))
    assert out["tokens"] == 150
    assert out["cache_read_tokens"] is None
    assert out["cache_creation_tokens"] is None


def test_parse_cost_total_tokens_fallback_still_works():
    """A CLI reporting only `total_tokens` (no input/output/cache breakdown) still
    works via the fallback path."""
    out = run_optimizer_run.parse_cost(json.dumps(
        {"total_cost_usd": 0.2, "usage": {"total_tokens": 999}}))
    assert out["tokens"] == 999


def test_parse_cost_cumulative_result_survives_compaction_event():
    """A multi-turn session where an earlier turn's context got compacted mid-
    session: Claude Code's cumulative `usage`/`total_cost_usd` on the terminal
    `result` event already reflects the whole session (compaction trims what's
    resent as context, not the running billed-usage counter) — parse_cost must
    trust that cumulative terminal figure rather than only the last visible
    turn's tokens."""
    stream = "\n".join(json.dumps(o) for o in [
        {"type": "assistant", "message": {"content": []}},
        {"type": "system", "subtype": "compact_boundary",
         "compact_metadata": {"trigger": "auto", "pre_tokens": 180000}},
        {"type": "assistant", "message": {"content": []}},
        # Cumulative for the WHOLE session, including the pre-compaction turns —
        # bigger than any single visible turn's usage would be on its own.
        {"type": "result", "subtype": "success", "total_cost_usd": 9.6,
         "usage": {"input_tokens": 4000, "output_tokens": 6000,
                    "cache_creation_input_tokens": 20000,
                    "cache_read_input_tokens": 450000}},
    ])
    out = run_optimizer_run.parse_cost(stream)
    assert out["tokens"] == 4000 + 6000 + 20000 + 450000 == 480000
    assert out["cache_read_tokens"] == 450000
    assert out["cache_creation_tokens"] == 20000


def test_dollar_per_token_now_consistent_across_structurally_similar_calls():
    """Reproduces the issue's exact symptom: with the old input+output-only
    `tokens`, two structurally similar calls (same skill/model, both cache-heavy)
    give wildly different $/token — 100x and 130x a fixed illustrative per-token
    price — purely because their cache-token share differs. With the corrected
    full-session `tokens`, both recompute to the SAME $/token."""
    price_per_token = 0.00002  # illustrative fixed blended rate

    # cand_0003: 200,000 total tokens billed, only 2,000 of them input+output.
    cand_0003 = {"total_cost_usd": price_per_token * 200_000,
                 "usage": {"input_tokens": 800, "output_tokens": 1200,
                           "cache_creation_input_tokens": 8000,
                           "cache_read_input_tokens": 190000}}
    # cand_0004: same input+output (2,000) but a bigger cache share -> 260,000 total.
    cand_0004 = {"total_cost_usd": price_per_token * 260_000,
                 "usage": {"input_tokens": 800, "output_tokens": 1200,
                           "cache_creation_input_tokens": 8000,
                           "cache_read_input_tokens": 250000}}

    out3 = run_optimizer_run.parse_cost(json.dumps(cand_0003))
    out4 = run_optimizer_run.parse_cost(json.dumps(cand_0004))

    old_ratio_3 = cand_0003["total_cost_usd"] / (800 + 1200)   # old (broken) tokens
    old_ratio_4 = cand_0004["total_cost_usd"] / (800 + 1200)
    assert old_ratio_3 == pytest.approx(price_per_token * 100)   # 100x too high
    assert old_ratio_4 == pytest.approx(price_per_token * 130)   # 130x too high — varies call to call

    new_ratio_3 = out3["usd"] / out3["tokens"]
    new_ratio_4 = out4["usd"] / out4["tokens"]
    assert new_ratio_3 == pytest.approx(price_per_token)
    assert new_ratio_4 == pytest.approx(price_per_token)  # bug resolved: fixed and equal


# ---- optimizer cost must survive a non-zero optimizer exit ----------------

def test_optimizer_from_command_recovers_cost_on_nonzero_exit(tmp_path, monkeypatch):
    """run-optimizer computes real cost from the CLI's JSON *before* returning its
    own exit code, which mirrors the underlying CLI's (e.g. non-zero on hitting
    --max-budget-usd). That already-computed cost must not be thrown away just
    because the optimizer process failed."""
    payload = json.dumps({"optimizer": "claude-code", "returncode": 1,
                          "cost": {"total_cost_usd": 0.0591, "tokens": 500}})

    class FakeProc:
        returncode = 1
        stdout = payload
        stderr = ""

    monkeypatch.setattr(harness.subprocess, "run", lambda *a, **k: FakeProc())

    opt = optimizer_from_command(["fake", "--workdir", "{workdir}", "--prompt", "{prompt}"])
    workdir = tmp_path / "work"
    workdir.mkdir()
    try:
        opt(workdir, "do something")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert getattr(e, "cost", None) == {"cost_usd": 0.0591, "tokens": 500}


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


def _project_with_val(tmp_path, n_val: int):
    """A project whose val split resolves to exactly ``n_val`` tasks, via split_ids_file
    (the cheapest way to give ``_val_size`` a known answer with no real adapter)."""
    proj = tmp_path / "project"
    proj.mkdir()
    ids_file = proj / "splits.json"
    ids_file.write_text(json.dumps({"val": list(range(n_val))}), encoding="utf-8")
    return proj, str(ids_file)


def test_estimate_agent_mode_is_not_priced_as_a_fixed_iteration_loop(tmp_path):
    """orchestration_mode: agent — rounds are not fixed by max_iterations, so the
    estimate must not multiply metric calls by it, and optimizer_calls (a fixed
    per-iteration count) is undefined here."""
    proj, ids_file = _project_with_val(tmp_path, n_val=5)
    spec = {"num_trials": 3, "max_iterations": 10, "orchestration_mode": "agent",
            "split_ids_file": ids_file}
    out = cli._estimate_core(spec, proj)
    assert out["calls"]["optimizer_calls"] is None
    assert out["calls"]["metric_calls_per_round"] == 5 * 3   # val * trials, NOT * iters
    assert "metric_calls" not in out["calls"]
    assert out["note"]


def test_estimate_deterministic_mode_unchanged_by_agent_mode_branch(tmp_path):
    """Regression guard: the same spec (minus orchestration_mode) still prices as
    val * trials * max_iterations, exactly as before the agent-mode branch existed."""
    proj, ids_file = _project_with_val(tmp_path, n_val=5)
    spec = {"num_trials": 3, "max_iterations": 10, "split_ids_file": ids_file}
    out = cli._estimate_core(spec, proj)
    assert out["calls"] == {"metric_calls": 5 * 3 * 10, "optimizer_calls": 10}
