"""Model tiering: cheap model for auxiliary steps, strong model for proposals (#132).

Two tiers, mapped to the only two kinds of model call cap-evolve makes:

  proposer — the edit proposal that DETERMINES RESULT QUALITY (harness.run_step /
             gepa's minibatch step → ``optimizer(workdir, instructions)``).
  aux      — auxiliary/mechanical model work (summarization, reflection distillation,
             insight synthesis, rejected-summary).

What these tests pin down:
  1. BACKWARD COMPAT — a single-model spec resolves BOTH tiers to ``optimizer_model``
     and builds the byte-identical optimizer argv it built before tiering existed.
  2. ROUTING — with a tiered spec, the argv actually handed to the edit proposer
     carries the PROPOSER model (asserted on the real command that reaches
     ``run-optimizer``, not just on the parsed config), and the cheap ``aux_model``
     never appears on the proposal path.
  3. COST ACCOUNTING — per-tier spend stays separately attributed, so a cheap aux
     call can never be reported at the strong model's rate, and the estimator prices
     the proposal THROUGH the tier seam so a mis-tier changes a visible number.
  4. NO ENV LEAK — CAPEVOLVE_AUX_MODEL is exported only for a genuinely tiered spec
     and cleared otherwise, so it cannot leak stale across in-process runs.
"""

import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

from cap_evolve import cli, pricing  # noqa: E402
from cap_evolve.rundir import RunDir, Spent  # noqa: E402
from cap_evolve.specfile import TIERS, is_tiered, model_for_tier  # noqa: E402

STRONG = "claude-opus-4-8"
CHEAP = "claude-haiku-4-5"
# Sentinel pre-seeded into CAPEVOLVE_AUX_MODEL so "unset after the run" proves the run
# actively CLEARED a leftover value, rather than merely never setting one.
STALE = "stale-model-from-a-previous-run"


# ---- 1. tier resolution ----------------------------------------------------

def test_single_model_spec_resolves_both_tiers_to_optimizer_model():
    """BACKWARD-COMPAT CORE: one model in, one model out — for every tier."""
    spec = {"optimizer_model": STRONG}
    assert model_for_tier(spec, "proposer") == STRONG
    assert model_for_tier(spec, "aux") == STRONG
    assert is_tiered(spec) is False


def test_no_model_at_all_stays_blank_for_both_tiers():
    """A spec with no model set must not invent one (the backend picks its default)."""
    for tier in TIERS:
        assert model_for_tier({}, tier) == ""
        assert model_for_tier({"optimizer_model": ""}, tier) == ""
    assert is_tiered({}) is False


def test_tiered_spec_splits_the_tiers():
    spec = {"optimizer_model": STRONG, "aux_model": CHEAP}
    assert model_for_tier(spec, "proposer") == STRONG
    assert model_for_tier(spec, "aux") == CHEAP
    assert is_tiered(spec) is True


def test_proposer_model_overrides_optimizer_model_for_the_proposal_only():
    spec = {"optimizer_model": CHEAP, "proposer_model": STRONG, "aux_model": CHEAP}
    assert model_for_tier(spec, "proposer") == STRONG
    assert model_for_tier(spec, "aux") == CHEAP


def test_unknown_tier_is_a_loud_error():
    """A typo'd tier must not silently fall back to the cheap model."""
    with pytest.raises(ValueError):
        model_for_tier({"optimizer_model": STRONG}, "auxilliary")


# ---- 2. ROUTING: assert the argv each call site actually gets ---------------

def _plan(tmp_path, spec_extra: dict) -> dict:
    """Run ``cap-evolve run --plan-only`` and return its parsed plan.

    --plan-only builds the REAL optimizer command that would be handed to the
    algorithm (and thus to ``run-optimizer``) without spending anything, so
    asserting on ``optimizer_cmd`` asserts on true routing, not on config parsing.

    The returned dict carries an extra ``aux_env`` key: the value of
    ``CAPEVOLVE_AUX_MODEL`` as observed INSIDE the run (``None`` when unset), so tests
    can assert on the env channel even though this helper restores the environment.
    The env is pre-seeded with a STALE sentinel first, so "unset" in a result means the
    run actively cleared a leftover value — not merely that nothing set one.
    """
    proj = tmp_path / ".capevolve" / "project"
    proj.mkdir(parents=True)
    spec = {"capabilities": "[system-prompt]", "capability_path": "seed_capability",
            "optimizer_skill": "mock", "algorithm_skill": "hill-climb", **spec_extra}
    lines = [f"{k}: {v}" for k, v in spec.items()]
    (proj / "capevolve.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    old = dict(os.environ)
    os.environ["CAPEVOLVE_SKILLS_DIR"] = str(REPO / "skills")
    os.environ["CAPEVOLVE_AUX_MODEL"] = STALE
    import io
    import contextlib
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = cli._cmd_run(["--spec", str(proj / "capevolve.yaml"), "--project",
                               str(proj), "--plan-only", "--dashboard", "off"])
        assert rc == 0, buf.getvalue()
        plan = json.loads(buf.getvalue())
        plan["aux_env"] = os.environ.get("CAPEVOLVE_AUX_MODEL")
        return plan
    finally:
        os.environ.clear()
        os.environ.update(old)


def test_single_model_optimizer_argv_is_unchanged_by_tiering(tmp_path):
    """REGRESSION GUARD: the argv a single-model spec produces is exactly the argv
    the pre-tiering code produced — ``--model <optimizer_model>``, once."""
    plan = _plan(tmp_path, {"optimizer_model": STRONG})
    cmd = plan["optimizer_cmd"]
    assert f"--model {STRONG}" in cmd
    assert cmd.count("--model") == 1
    # both tiers resolved to the one model → no split, nothing else injected
    assert plan["model_tiers"] == {"proposer": STRONG, "aux": STRONG}


def test_spec_with_no_model_emits_no_model_flag(tmp_path):
    """The pre-tiering behavior for a model-less spec: no --model token at all."""
    plan = _plan(tmp_path, {})
    assert "--model" not in plan["optimizer_cmd"]
    assert plan["model_tiers"] == {"proposer": "", "aux": ""}


def test_tiered_spec_routes_the_PROPOSAL_to_the_strong_model(tmp_path):
    """The quality-determining call site gets the STRONG model, and the cheap model
    must NOT appear anywhere on the proposal command line."""
    plan = _plan(tmp_path, {"optimizer_model": STRONG, "aux_model": CHEAP})
    cmd = plan["optimizer_cmd"]
    assert f"--model {STRONG}" in cmd
    assert CHEAP not in cmd, "cheap aux model must never reach the edit proposer"
    assert plan["model_tiers"] == {"proposer": STRONG, "aux": CHEAP}


def test_proposer_model_key_routes_the_proposal(tmp_path):
    """``proposer_model`` wins for the proposal even when optimizer_model is cheap."""
    plan = _plan(tmp_path, {"optimizer_model": CHEAP, "proposer_model": STRONG,
                            "aux_model": CHEAP})
    assert f"--model {STRONG}" in plan["optimizer_cmd"]
    assert plan["model_tiers"]["proposer"] == STRONG


def test_aux_model_reaches_subprocesses_via_env(tmp_path):
    """The cheap tier travels by env (no core call site spends it yet). An LLM-backed
    aux step reads CAPEVOLVE_AUX_MODEL rather than re-parsing the spec.

    Asserts the name literally: a REAL child process spawned after the run reads the
    cheap model id out of its inherited environment.
    """
    import subprocess
    proj = tmp_path / ".capevolve" / "project"
    proj.mkdir(parents=True)
    (proj / "capevolve.yaml").write_text(
        "capabilities: [system-prompt]\ncapability_path: seed_capability\n"
        f"optimizer_skill: mock\nalgorithm_skill: hill-climb\n"
        f"optimizer_model: {STRONG}\naux_model: {CHEAP}\n", encoding="utf-8")
    old = dict(os.environ)
    os.environ["CAPEVOLVE_SKILLS_DIR"] = str(REPO / "skills")
    os.environ.pop("CAPEVOLVE_AUX_MODEL", None)
    import io
    import contextlib
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            cli._cmd_run(["--spec", str(proj / "capevolve.yaml"), "--project",
                          str(proj), "--plan-only", "--dashboard", "off"])
        assert os.environ.get("CAPEVOLVE_AUX_MODEL") == CHEAP
        # ...and a child process (where a real aux step would run) inherits it.
        child = subprocess.run(
            [sys.executable, "-c",
             "import os; print(os.environ.get('CAPEVOLVE_AUX_MODEL', ''))"],
            capture_output=True, text=True, check=True)
        assert child.stdout.strip() == CHEAP, child.stdout
    finally:
        os.environ.clear()
        os.environ.update(old)


def test_single_model_spec_sets_no_aux_env(tmp_path):
    """Backward compat: a single-model spec has no cheap tier, so it must NOT export
    CAPEVOLVE_AUX_MODEL — and must clear a value a previous run left behind."""
    plan = _plan(tmp_path, {"optimizer_model": STRONG})
    # the aux tier is the same model, so nothing is "tiered" and nothing is logged
    assert plan["model_tiers"]["aux"] == plan["model_tiers"]["proposer"]
    # THE NAMED BEHAVIOR: no aux env, and the pre-seeded stale value is gone.
    assert plan["aux_env"] is None, plan["aux_env"]


def test_untiered_run_clears_a_stale_aux_env_from_an_earlier_run(tmp_path):
    """The env channel must not leak ACROSS in-process runs. A tiered run exports the
    cheap model; a later untiered run in the same process must clear it, not inherit
    it — otherwise a future aux step spends the previous spec's model."""
    tiered = _plan(tmp_path / "a", {"optimizer_model": STRONG, "aux_model": CHEAP})
    assert tiered["aux_env"] == CHEAP
    # same process, different spec: no aux tier at all
    assert _plan(tmp_path / "b", {"optimizer_model": STRONG})["aux_env"] is None
    assert _plan(tmp_path / "c", {})["aux_env"] is None


# ---- 3. COST ACCOUNTING: per-tier attribution stays honest -----------------

def test_aux_spend_has_its_own_bucket_and_never_inflates_optimizer_usd(tmp_path):
    """HONESTY: aux is the cheap tier. If its spend landed in ``optimizer_usd`` it
    would be calibrated as $/optimizer-call and capped by ``max_optimizer_usd`` at
    the STRONG model's rate — silently wrong in both directions."""
    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    rd.update_spent(iterations=1, optimizer_usd=0.50, optimizer_tokens=12_000)
    rd.update_spent(aux_usd=0.02, aux_tokens=4_500)
    sp = rd.spent
    assert sp.optimizer_usd == 0.50, "aux spend must not leak into the proposer bucket"
    assert sp.aux_usd == 0.02
    assert sp.optimizer_tokens == 12_000
    assert sp.aux_tokens == 4_500
    # but the all-role total (what max_usd guards) must include it, or the run could
    # overspend past its cap through an unbudgeted tier.
    assert sp.total_usd == pytest.approx(0.52)


def test_spent_roundtrips_aux_and_stays_readable_without_it():
    """Old state.json (no aux keys) must still load — and read back as $0 aux."""
    legacy = {"iterations": 2, "usd": 1.0, "optimizer_usd": 0.4, "optimizer_tokens": 99}
    sp = Spent.from_dict(legacy)
    assert sp.aux_usd == 0.0 and sp.aux_tokens == 0
    assert sp.optimizer_usd == 0.4
    assert sp.total_usd == pytest.approx(1.4)  # unchanged from pre-tiering
    # and a fresh Spent roundtrips the new fields
    sp2 = Spent.from_dict(Spent(optimizer_usd=1.0, aux_usd=0.25).to_dict())
    assert (sp2.optimizer_usd, sp2.aux_usd) == (1.0, 0.25)


def test_max_usd_counts_aux_spend(tmp_path):
    """An unbudgeted tier would be a way to spend past max_usd. It isn't."""
    from cap_evolve.rundir import Budget
    rd = RunDir.create(tmp_path / ".capevolve", ts="t", budget=Budget(max_usd=1.0))
    rd.update_spent(usd=0.6)
    assert rd.budget_exhausted()[0] is False
    rd.update_spent(aux_usd=0.5)          # 0.6 + 0.5 = 1.1 > 1.0
    exhausted, why = rd.budget_exhausted()
    assert exhausted is True
    assert "aux $0.50" in why, why


def test_max_optimizer_usd_caps_only_the_proposer_tier(tmp_path):
    """``max_optimizer_usd`` is a cap on the STRONG model's spend. Cheap aux work
    must not consume that cap (that's the whole point of tiering)."""
    from cap_evolve.rundir import Budget
    rd = RunDir.create(tmp_path / ".capevolve", ts="t",
                       budget=Budget(max_optimizer_usd=1.0, max_usd=100.0))
    rd.update_spent(aux_usd=5.0)
    assert rd.budget_exhausted()[0] is False, "aux spend must not trip the optimizer cap"
    rd.update_spent(optimizer_usd=1.0)
    assert rd.budget_exhausted()[0] is True


def test_aux_priced_at_its_own_model_and_token_profile():
    """Per-tier pricing: a cheap-tier call is priced with the CHEAP model AND the
    smaller aux token profile — not the proposer's 10k/2k assumption."""
    strong = pricing.tier_call_cost(STRONG, "proposer")
    cheap = pricing.tier_call_cost(CHEAP, "aux")
    assert strong is not None and cheap is not None
    assert cheap < strong / 5, (cheap, strong)
    # the tier→role mapping is what keeps them from being conflated
    assert pricing.tier_call_cost(STRONG, "proposer") == pricing.call_cost(STRONG, "optimizer")
    assert pricing.tier_call_cost(CHEAP, "aux") == pricing.call_cost(CHEAP, "aux")
    # pricing the SAME model under both tiers must differ (different token profiles),
    # proving a tier label can't be a no-op that hides a mis-priced call.
    assert pricing.tier_call_cost(STRONG, "aux") != pricing.tier_call_cost(STRONG, "proposer")


def test_estimate_prices_proposal_with_the_proposer_tier(tmp_path):
    """A tiered spec must estimate the proposal at the STRONG model's price. Pricing
    it at the cheap model would under-report the run's real cost."""
    single = {"num_trials": 1, "max_iterations": 4, "optimizer_model": STRONG}
    tiered = {**single, "aux_model": CHEAP}
    a = cli._estimate_core(single, tmp_path)
    b = cli._estimate_core(tiered, tmp_path)
    assert a["cost_usd"]["optimizer_usd"] == b["cost_usd"]["optimizer_usd"], \
        "adding a cheap aux tier must not change the PROPOSAL's estimated cost"
    assert b["spec_summary"]["tiered"] is True
    assert a["spec_summary"]["tiered"] is False
    assert b["spec_summary"]["proposer_model"] == STRONG
    assert b["spec_summary"]["aux_model"] == CHEAP


def test_estimator_prices_the_proposal_THROUGH_the_tier_seam(tmp_path, monkeypatch):
    """The mis-pricing guard must be LIVE in production, not just unit-tested.

    ``_estimate_core`` must reach the price table via ``tier_call_cost(m, "proposer")``,
    so the tier a call is priced as is named at the call site. Proven two ways: the
    seam is actually invoked (a sentinel patched over it changes the estimate), and it
    is invoked with the PROPOSER tier (the aux profile would give a different number).
    """
    spec = {"num_trials": 1, "max_iterations": 4, "optimizer_model": STRONG}
    seen: list[tuple[str | None, str]] = []
    real = pricing.tier_call_cost
    monkeypatch.setattr(pricing, "tier_call_cost",
                        lambda m, t: (seen.append((m, t)), real(m, t))[1])
    out = cli._estimate_core(spec, tmp_path)
    assert (STRONG, "proposer") in seen, seen           # seam is on the live path
    assert not any(t == "aux" for _, t in seen), seen   # priced as the proposer tier
    assert out["cost_usd"]["optimizer_usd"] == round(4 * real(STRONG, "proposer"), 4)
    # and a mis-tier would be VISIBLE, not silent: the aux profile prices differently.
    assert real(STRONG, "aux") != real(STRONG, "proposer")


def test_estimate_single_model_is_byte_identical_to_pre_tiering(tmp_path):
    """REGRESSION GUARD on the estimator: for a single-model spec the priced numbers
    are exactly what the pre-tiering code computed off ``optimizer_model``."""
    spec = {"num_trials": 3, "max_iterations": 4, "optimizer_model": STRONG}
    out = cli._estimate_core(spec, tmp_path)
    expected = 4 * pricing.call_cost(STRONG, "optimizer")   # iters × $/optimizer-call
    assert out["cost_usd"]["optimizer_usd"] == round(expected, 4)
    assert out["spec_summary"]["optimizer_model"] == STRONG


def test_calibration_keeps_the_tiers_separate(tmp_path):
    """$/optimizer-call is calibrated from proposer spend ONLY; aux spend calibrates
    its own rate. Blending them would corrupt every future estimate."""
    proj = tmp_path / "project"
    proj.mkdir()
    rd = RunDir.create(proj.parent, ts="prior")
    rd.update_spent(metric_calls=10, usd=1.0, iterations=2,
                    optimizer_usd=0.4, aux_usd=0.04)
    out = cli._estimate_core({"max_iterations": 3, "optimizer_model": STRONG}, proj)
    cal = out["calibration"]
    assert cal["usd_per_optimizer_call"] == 0.2, cal   # 0.4/2, NOT (0.4+0.04)/2
    assert cal["usd_per_aux_call"] == 0.02, cal        # 0.04/2, its own rate


# ---- 4. dashboard surfaces the tiers (CostPanel per-tier breakdown) --------

def test_dashboard_reports_per_tier_cost_and_hides_it_when_untiered(tmp_path):
    from cap_evolve import dashboard
    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    rd.update_spent(iterations=1, usd=0.1, optimizer_usd=0.5, aux_usd=0.02,
                    optimizer_tokens=100, aux_tokens=40, runner_tokens=10)
    rd.log_event("model_tiers", proposer=STRONG, aux=CHEAP)
    s = dashboard.reduce_run(rd)["summary"]
    assert s["cost"]["aux_usd"] == 0.02
    assert s["cost"]["optimizer_usd"] == 0.5
    assert s["cost"]["total_usd"] == pytest.approx(0.62)
    assert s["tokens_by_role"]["aux"] == 40
    assert s["model_tiers"] == {"proposer": STRONG, "aux": CHEAP}

    # untiered run: no model_tiers event → the panel row is hidden (None), and the
    # cost figures are the same shape as before with aux at $0.
    rd2 = RunDir.create(tmp_path / ".capevolve2", ts="t")
    rd2.update_spent(iterations=1, usd=0.1, optimizer_usd=0.5)
    s2 = dashboard.reduce_run(rd2)["summary"]
    assert s2["model_tiers"] is None
    assert s2["cost"]["aux_usd"] == 0.0
    assert s2["cost"]["total_usd"] == pytest.approx(0.6)
