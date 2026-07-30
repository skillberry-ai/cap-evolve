"""#138 — phase pipeline + evidence-header burn (`dashboard.derive_pipeline`).

Two invariants worth a test:

* **Phase detection covers all three deterministic algorithms.** hill-climb logs
  ``step``, GEPA logs ``gepa_val_gate``/``gepa_select``/…, SkillOpt logs
  ``skillopt_step``. Four bugs in this epic (#224) came from a consumer assuming
  ``kind == "step"``; the Optimize stage must light for every one of them.
* **The burn is not re-derived.** ``eventstream.accrue_totals`` counts each dollar
  once (runner from ``evaluate``, optimizer from ``step``-likes) and must reproduce
  ``RunDir.spent.total_usd``. Summing every cost-ish key overstates it.
"""
from __future__ import annotations

import json

from cap_evolve import dashboard


def _ev(kind, t=1000.0, **kw):
    return dict(kind=kind, t=t, **kw)


def _phase(pipeline, key):
    return next(p["status"] for p in pipeline["phases"] if p["key"] == key)


# --- phase detection, per algorithm -----------------------------------------

ALGO_STEP_EVENTS = {
    "hill-climb": [_ev("step", candidate="c1", val=0.5, accept=True)],
    "gepa": [_ev("gepa_start"), _ev("gepa_select", parent="seed", strategy="pareto"),
             _ev("minibatch", tag="g1"), _ev("gepa_local_gate", candidate="g1", passed=True),
             _ev("gepa_val_gate", candidate="g1", val=0.5, accept=True)],
    "skillopt": [_ev("skillopt_start"),
                 _ev("skillopt_step", candidate="s1", val=0.5, accept=True, epoch=1,
                     step_in_epoch=1),
                 _ev("skillopt_slow_update", epoch=1)],
}


def test_optimize_phase_lights_for_every_algorithm():
    """No consumer may assume ``kind == "step"`` (#224)."""
    for algo, steps in ALGO_STEP_EVENTS.items():
        events = [_ev("splits", train=2, val=2, test=2), _ev("baseline", val=0.1)] + steps
        p = dashboard.derive_pipeline(events)
        assert _phase(p, "baseline") == "done", algo
        assert _phase(p, "optimize") == "active", algo
        assert p["current"] == "optimize", algo
        assert _phase(p, "finalize") == "pending", algo


def test_every_phase_reachable_for_every_algorithm():
    """Walk each algorithm through the full pipeline and see all six phases resolve."""
    for algo, steps in ALGO_STEP_EVENTS.items():
        events = ([_ev("intake", usd=0.0), _ev("seed_dir_created", path="/x"),
                   _ev("splits", train=2, val=2, test=2), _ev("baseline", val=0.1)]
                  + steps + [_ev("finalize", test_reward=0.9, best_id="b")])
        p = dashboard.derive_pipeline(events, finalized=True)
        got = {x["key"]: x["status"] for x in p["phases"]}
        assert got == {"intake": "done", "check": "done", "baseline": "done",
                       "optimize": "done", "finalize": "done", "report": "active"}, (algo, got)


def test_unreached_phase_is_pending_but_a_silent_past_phase_is_skipped():
    """`cap-evolve run` on a scaffolded project logs no `intake` — calling that phase
    "pending" on a finalized run would state something false."""
    p = dashboard.derive_pipeline(
        [_ev("baseline", val=0.1), _ev("step", candidate="c", val=0.2, accept=True),
         _ev("finalize", test_reward=0.5)], finalized=True)
    got = {x["key"]: x["status"] for x in p["phases"]}
    assert got["intake"] == "skipped" and got["check"] == "skipped"
    assert "pending" not in got.values()

    early = dashboard.derive_pipeline([_ev("intake", usd=0.0)])
    got = {x["key"]: x["status"] for x in early["phases"]}
    assert got["intake"] == "active" and got["finalize"] == "pending"


def test_empty_log_has_no_current_phase():
    p = dashboard.derive_pipeline([])
    assert p["current"] is None
    assert all(x["status"] == "pending" for x in p["phases"])
    assert p["now"]["line"] is None


def test_malformed_events_do_not_raise():
    """A non-dict record, a string `t`, a dict `t` — all reachable in a real log
    (`log_event` serialises with default=str) and none may kill the header."""
    p = dashboard.derive_pipeline(
        ["not a dict", 42, None, _ev("baseline", t="nope", val=0.1),
         _ev("step", t={"a": 1}, candidate="c", val=0.2, accept=True)])
    assert _phase(p, "optimize") == "active"
    assert p["burn"]["usd"] == 0.0


# --- the burn ---------------------------------------------------------------

def test_burn_uses_accrue_totals_and_does_not_double_count_the_runner():
    """The harness reports the SAME runner spend twice: on ``evaluate`` and restated on
    the following ``step``. Counting both showed ~2x the real spend (#191 review)."""
    events = [
        _ev("evaluate", split="val", tag="seed", cost_usd=0.07, tokens=1500),
        _ev("evaluate", split="val", tag="c1", cost_usd=0.07, tokens=1500),
        # the step restates the runner spend AND adds the optimizer's own
        _ev("step", candidate="c1", val=0.5, accept=True, cost_usd=0.07, tokens=1500,
            opt_cost_usd=0.13, opt_tokens=900),
    ]
    burn = dashboard.derive_pipeline(events)["burn"]
    # runner 2 x 0.07 (from `evaluate` only) + optimizer 0.13 = Spent.total_usd
    assert abs(burn["usd"] - 0.27) < 1e-9, burn
    assert burn["tokens"] == 1500 * 2 + 900
    naive = sum(float(e.get("cost_usd") or 0) + float(e.get("opt_cost_usd") or 0)
                for e in events)
    assert naive > burn["usd"]  # what re-deriving the arithmetic would have shown


def test_burn_rate_is_only_reported_when_it_means_something():
    """A burn *rate* answers "what is this costing me right now". There is no honest
    answer for a finished run (a 2.6s toy run that spent $0.81 is not burning
    $18.69/min) or under a minute of elapsed time — report the total, and `None`."""
    one = dashboard.derive_pipeline(
        [_ev("evaluate", t=100.0, split="val", cost_usd=0.5, tokens=10)])["burn"]
    assert one["usd"] == 0.5 and one["elapsed_seconds"] == 0.0
    assert one["usd_per_min"] is None and one["tokens_per_min"] is None

    live = [_ev("evaluate", t=60.0, split="val", cost_usd=0.5, tokens=600),
            _ev("evaluate", t=180.0, split="val", cost_usd=0.5, tokens=600)]
    burn = dashboard.derive_pipeline(live)["burn"]
    assert burn["elapsed_seconds"] == 120.0
    assert abs(burn["usd_per_min"] - 0.5) < 1e-9
    assert abs(burn["tokens_per_min"] - 600.0) < 1e-9

    # same events, but the run is over → total stands, rate goes away
    done = dashboard.derive_pipeline(live, finalized=True)["burn"]
    assert done["usd"] == burn["usd"]
    assert done["usd_per_min"] is None and done["tokens_per_min"] is None

    # under a minute: extrapolating 3 seconds to a per-minute figure is invention
    short = dashboard.derive_pipeline(
        [_ev("evaluate", t=1.0, split="val", cost_usd=0.5, tokens=10),
         _ev("evaluate", t=4.0, split="val", cost_usd=0.5, tokens=10)])["burn"]
    assert short["elapsed_seconds"] == 3.0 and short["usd_per_min"] is None


def test_reduce_run_burn_equals_the_run_dirs_own_spent(tmp_path):
    """The header's dollars must be the run's own dollars — not a second opinion."""
    from cap_evolve.rundir import RunDir

    rd = RunDir.create(tmp_path, ts="t")
    rd.log_event("splits", train=1, val=1, test=1)
    rd.log_event("baseline", val=0.1)
    rd.log_event("evaluate", split="val", tag="seed", cost_usd=0.07, tokens=1500)
    rd.log_event("evaluate", split="val", tag="c1", cost_usd=0.07, tokens=1500)
    rd.log_event("step", candidate="c1", val=0.5, accept=True, cost_usd=0.07, tokens=1500,
                 opt_cost_usd=0.13, opt_tokens=900)
    rd.update_spent(usd=0.14, runner_tokens=3000, optimizer_usd=0.13, optimizer_tokens=900)

    reduced = dashboard.reduce_run(rd)
    burn = reduced["summary"]["pipeline"]["burn"]
    truth = rd.spent
    assert burn["source"] == "spent"
    assert abs(burn["usd"] - truth.total_usd) < 1e-9
    assert burn["tokens"] == truth.runner_tokens + truth.optimizer_tokens + truth.intake_tokens
    # …and the same total the KPI strip and the cost bars show.
    assert abs(burn["usd"] - reduced["summary"]["cost"]["total_usd"]) < 1e-4
    assert burn["tokens"] == reduced["summary"]["tokens"]


def test_now_line_is_sanitised_by_format_event():
    """Event text is model-controlled. The `now` line goes through
    `eventstream.format_event`, so an ESC sequence or a forged newline cannot reach a
    terminal or an HTML renderer."""
    p = dashboard.derive_pipeline(
        [_ev("optimizer_error", candidate="c", error="boom\033[2Jwiped\nFINALIZE test=1.0")])
    line = p["now"]["line"]
    assert "\033" not in line and "\n" not in line
    assert "⏎" in line  # the forged newline is visible, not obeyed


def test_json_for_html_neutralises_script_data(tmp_path):
    """#209: a model-written reason containing `<!--<script>` blanked the page."""
    hostile = {"reason": "<!--<script>alert(1)</script>", "amp": "a&b"}
    out = dashboard.json_for_html(hostile)
    assert "<" not in out and ">" not in out and "&" not in out
    assert json.loads(out) == hostile  # the data the JS reads is unchanged
