"""#138 — phase pipeline + evidence-header burn (`dashboard.derive_pipeline`).

Two invariants worth a test:

* **Phase detection covers all three deterministic algorithms.** hill-climb logs
  ``step``, GEPA logs ``gepa_val_gate``/``gepa_select``/…, SkillOpt logs
  ``skillopt_step``. Four bugs in this epic (#224) came from a consumer assuming
  ``kind == "step"``; the Optimize stage must light for every one of them.
* **The burn is not re-derived.** ``eventstream.accrue_totals`` counts each dollar
  once and must reproduce ``RunDir.spent.total_usd`` FOR EVERY ALGORITHM — the #234
  review found it understating GEPA 3.9x because GEPA writes neither ``evaluate`` nor
  ``opt_cost_usd``. Summing every cost-ish key overstates it in the other direction.
* **A phase never claims more than the log proves.** The hard gate reads ``unknown``
  unless it attested itself; a dead run's phase reads ``interrupted``, not ``active``;
  a phase whose only evidence is an error reads ``errored``, not ``skipped``/``done``.
* **A rate's denominator is wall clock, and goes away when the log is stale.**
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
        events = ([_ev("intake", usd=0.0), _ev("check_gate", ok=True, problems=0),
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
    # intake: legitimately silent (pre-scaffolded) → skipped. check: silence about the
    # HARD GATE is not evidence it was skipped → unknown, never a green tick.
    assert got["intake"] == "skipped"
    assert got["check"] == "unknown"
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
    # `now` is passed explicitly so the assertions are about the arithmetic, not the
    # test's own wall clock.
    one = dashboard.derive_pipeline(
        [_ev("evaluate", t=100.0, split="val", cost_usd=0.5, tokens=10)], now=100.0)["burn"]
    assert one["usd"] == 0.5 and one["elapsed_seconds"] == 0.0
    assert one["usd_per_min"] is None and one["tokens_per_min"] is None

    live = [_ev("evaluate", t=60.0, split="val", cost_usd=0.5, tokens=600),
            _ev("evaluate", t=180.0, split="val", cost_usd=0.5, tokens=600)]
    burn = dashboard.derive_pipeline(live, now=180.0)["burn"]
    assert burn["elapsed_seconds"] == 120.0
    assert abs(burn["usd_per_min"] - 0.5) < 1e-9
    assert abs(burn["tokens_per_min"] - 600.0) < 1e-9

    # same events, but the run is over → total stands, rate goes away
    done = dashboard.derive_pipeline(live, finalized=True, now=180.0)["burn"]
    assert done["usd"] == burn["usd"]
    assert done["usd_per_min"] is None and done["tokens_per_min"] is None

    # under a minute: extrapolating 3 seconds to a per-minute figure is invention
    short = dashboard.derive_pipeline(
        [_ev("evaluate", t=1.0, split="val", cost_usd=0.5, tokens=10),
         _ev("evaluate", t=4.0, split="val", cost_usd=0.5, tokens=10)], now=4.0)["burn"]
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


# --- the three blocking findings from the #234 review ------------------------

def test_events_burn_equals_spent_for_every_algorithm(tmp_path):
    """The regression the #234 review found: the events-only burn understated GEPA by
    3.9x ($0.28 vs $1.09) because `accrue_totals` read `evaluate`/`opt_cost_usd`, and
    the GEPA path writes NEITHER — its runner spend goes through `minibatch` and its
    optimizer spend rides the per-iteration gate.

    This asserts the events-only burn against each algorithm's own `Spent`, charged
    through the same `update_spent` calls the real code makes. It is the test whose
    absence let a hill-climb-only proof generalise to a false claim about GEPA.
    """
    from cap_evolve.rundir import RunDir

    # (algorithm, events, the update_spent charges the real code makes for them)
    cases = {
        # hill-climb / skillopt: runner spend on `evaluate`, optimizer on the step.
        "hill-climb": ([
            _ev("evaluate", split="val", tag="seed", cost_usd=0.30, tokens=4000),
            _ev("evaluate", split="val", tag="c1", cost_usd=0.51, tokens=7700),
            _ev("step", candidate="c1", val=0.5, accept=True,
                cost_usd=0.51, tokens=7700, opt_cost_usd=0.28, opt_tokens=6000),
        ], dict(usd=0.81, runner_tokens=11700, optimizer_usd=0.28, optimizer_tokens=6000)),
        "skillopt": ([
            _ev("evaluate", split="val", tag="seed", cost_usd=0.30, tokens=4000),
            _ev("evaluate", split="val", tag="s1", cost_usd=0.51, tokens=7700),
            _ev("skillopt_step", candidate="s1", val=0.5, accept=True, epoch=1,
                step_in_epoch=1, opt_cost_usd=0.28, opt_tokens=6000),
        ], dict(usd=0.81, runner_tokens=11700, optimizer_usd=0.28, optimizer_tokens=6000)),
        # GEPA: minibatch rollouts (gepa.py:182) + a full-val eval, optimizer paid per
        # iteration whether or not the local gate passes (gepa.py:589).
        "gepa": ([
            _ev("evaluate", split="val", tag="seed", cost_usd=0.30, tokens=4000),
            _ev("gepa_start"), _ev("gepa_select", parent="seed", strategy="pareto"),
            _ev("minibatch", tag="mb_p_0001", cost_usd=0.09, tokens=1200),
            _ev("gepa_local_gate", candidate="g1", passed=True,
                opt_cost_usd=0.28, opt_tokens=6000),
            _ev("minibatch", tag="mb_c_0001", cost_usd=0.09, tokens=1300),
            _ev("evaluate", split="val", tag="g1", cost_usd=0.33, tokens=5200),
            _ev("gepa_val_gate", candidate="g1", val=0.5, accept=True),
        ], dict(usd=0.81, runner_tokens=11700, optimizer_usd=0.28, optimizer_tokens=6000)),
    }

    for algo, (events, charges) in cases.items():
        rd = RunDir.create(tmp_path / algo, ts="t")
        rd.update_spent(**charges)
        truth = rd.spent
        burn = dashboard.derive_pipeline(events)["burn"]
        assert burn["source"] == "events", algo
        assert abs(burn["usd"] - truth.total_usd) < 1e-9, (algo, burn["usd"], truth.total_usd)
        assert burn["tokens"] == truth.runner_tokens + truth.optimizer_tokens, algo


def test_gepa_emits_the_cost_fields_the_burn_reads():
    """Fixing the burn in the dashboard alone would have left #191's `--follow` meter and
    every future consumer reading the same blind events, so the fix is at the SOURCE.
    Pin the emitter contract: `minibatch` carries runner cost, `gepa_local_gate` carries
    optimizer cost, and `accrue_totals` classifies both."""
    import inspect
    from cap_evolve import gepa
    from cap_evolve.eventstream import _SPEND_SOURCES

    mb = inspect.getsource(gepa._eval_minibatch)
    assert 'log_event("minibatch"' in mb and "cost_usd=" in mb and "tokens=run_tokens" in mb
    loop = inspect.getsource(gepa.gepa_loop)
    assert 'log_event("gepa_local_gate"' in loop and "opt_cost_usd=" in loop

    assert _SPEND_SOURCES["minibatch"] == ("cost_usd", "tokens")
    assert _SPEND_SOURCES["gepa_local_gate"] == ("opt_cost_usd", "opt_tokens")
    # …and no kind is a source for two roles, which is what keeps each dollar once.
    assert len(_SPEND_SOURCES) == len(set(_SPEND_SOURCES))


def test_optimizer_spend_is_counted_on_locally_rejected_gepa_iterations():
    """The optimizer is paid every iteration; `gepa_val_gate` only fires on the ones that
    pass the cheap local gate. Keying optimizer spend off the val gate would silently
    lose the spend of every locally-rejected iteration."""
    events = [_ev("gepa_start"),
              _ev("minibatch", tag="mb_p", cost_usd=0.05, tokens=500),
              # local gate FAILS → no gepa_val_gate is ever logged for this iteration
              _ev("gepa_local_gate", candidate="g1", passed=False,
                  opt_cost_usd=0.40, opt_tokens=9000),
              _ev("minibatch", tag="mb_c", cost_usd=0.05, tokens=500)]
    burn = dashboard.derive_pipeline(events)["burn"]
    assert abs(burn["usd"] - 0.50) < 1e-9, burn   # 0.05 + 0.05 runner + 0.40 optimizer
    assert burn["tokens"] == 500 + 500 + 9000


def test_check_phase_never_claims_done_without_the_gate_attesting_itself():
    """`target_profile` is logged by the ALGORITHM runner, after baseline, whenever a
    target model is configured — so keying the hard gate off it rendered a green
    "✓ Implement & check" on any `--target-model` run with nothing proving the gate ran
    (#234 finding 1). Only `check_gate`, logged by the gate itself, counts."""
    real_order = [_ev("splits", t=1, train=2, val=2, test=2), _ev("baseline", t=2, val=0.1),
                  _ev("target_profile", t=3, model="gpt-oss-120b", tier="mid"),
                  _ev("step", t=4, candidate="c1", val=0.5, accept=True),
                  _ev("finalize", t=5, test_reward=0.9)]
    got = {x["key"]: x["status"]
           for x in dashboard.derive_pipeline(real_order, finalized=True)["phases"]}
    assert got["check"] == "unknown", got
    assert got["check"] not in ("done", "skipped")

    # …and it DOES read done once the gate attests itself.
    attested = [_ev("check_gate", t=1, ok=True, problems=0)] + real_order
    got = {x["key"]: x["status"]
           for x in dashboard.derive_pipeline(attested, finalized=True)["phases"]}
    assert got["check"] == "done", got

    # A gate that attested its own FAILURE is not evidence of a pass.
    failed = [_ev("check_gate", t=1, ok=False, problems=3)] + real_order
    got = {x["key"]: x["status"]
           for x in dashboard.derive_pipeline(failed, finalized=True)["phases"]}
    assert got["check"] == "errored", got


def test_the_live_rate_uses_wall_clock_and_is_suppressed_when_the_log_is_stale():
    """The 30x case (#234 finding 3): two events 120s apart, but the last one is 58
    minutes old because a slow eval is in flight. `last_t - first_t` freezes at 120s, so
    the surviving ratio describes only the dense part of the log."""
    # t>0: `_event_time` rejects t<=0 as clock skew, so anchor on a real epoch value.
    t0 = 1_700_000_000.0
    events = [_ev("evaluate", t=t0, split="val", cost_usd=1.0, tokens=1200),
              _ev("evaluate", t=t0 + 120.0, split="val", cost_usd=1.0, tokens=1200)]
    now = t0 + 120.0 + 58 * 60.0

    burn = dashboard.derive_pipeline(events, now=now)["burn"]
    assert burn["event_span_seconds"] == 120.0          # the OLD denominator
    assert burn["elapsed_seconds"] == now - t0          # wall clock, and still growing
    assert burn["stale_seconds"] == 58 * 60.0
    # Stale log → no recent-burn claim at all, rather than 30x the honest figure.
    assert burn["usd_per_min"] is None and burn["tokens_per_min"] is None

    # A live run whose log is CURRENT still gets a rate — off wall clock, not the span.
    fresh = dashboard.derive_pipeline(events, now=t0 + 180.0)["burn"]
    assert fresh["elapsed_seconds"] == 180.0
    assert abs(fresh["usd_per_min"] - 2.0 / 3.0) < 1e-6   # $2 over 3 minutes (6dp)
    # …and the event span would have claimed $1.00/min, i.e. 1.5x more.
    assert fresh["usd_per_min"] < 2.0 / (120.0 / 60.0)


def test_a_dead_run_shows_interrupted_not_active():
    """Merged with #218, the header rendered "● Optimize" (lit) next to a `crashed`
    StatusBadge and the reader could not tell which was true. `active` claims a phase is
    RUNNING; for a dead run it is only where the run stopped."""
    events = [_ev("splits", train=2, val=2, test=2), _ev("baseline", val=0.1),
              _ev("step", candidate="c1", val=0.5, accept=True)]
    assert _phase(dashboard.derive_pipeline(events), "optimize") == "active"
    for status in ("crashed", "stalled"):
        p = dashboard.derive_pipeline(events, liveness=status)
        assert _phase(p, "optimize") == "interrupted", status
        assert "active" not in {x["status"] for x in p["phases"]}, status
        assert p["current"] == "optimize", status  # still says WHERE, just not "running"
    # #221's plateau is orthogonal — "live and plateaued" is coherent, so `live` and any
    # unknown liveness value leave `active` alone.
    for status in ("live", None, "plateaued"):
        assert _phase(dashboard.derive_pipeline(events, liveness=status), "optimize") == "active"


def test_an_errored_phase_is_not_reported_as_skipped_or_done():
    """`skipped` says "legitimately not run" and `done` says "completed"; a phase whose
    only evidence is failure is neither (#234 finding 4)."""
    events = [_ev("splits", train=2, val=2, test=2), _ev("baseline", val=0.1),
              _ev("optimizer_error", candidate="c1", error="boom"),
              _ev("finalize", test_reward=0.1)]
    got = {x["key"]: x["status"]
           for x in dashboard.derive_pipeline(events, finalized=True)["phases"]}
    assert got["optimize"] == "errored", got
    assert got["optimize"] not in ("done", "skipped")
    # One successful sibling is enough to make it a real phase again.
    ok = events[:2] + [_ev("optimizer_error", candidate="c1", error="boom"),
                       _ev("step", candidate="c2", val=0.4, accept=True),
                       _ev("finalize", test_reward=0.4)]
    got = {x["key"]: x["status"]
           for x in dashboard.derive_pipeline(ok, finalized=True)["phases"]}
    assert got["optimize"] == "done", got


def test_rate_survives_a_backwards_clock():
    """A wall clock behind the log's own timestamps must not produce a negative
    denominator (and so a negative rate)."""
    events = [_ev("evaluate", t=1000.0, split="val", cost_usd=1.0, tokens=100),
              _ev("evaluate", t=1120.0, split="val", cost_usd=1.0, tokens=100)]
    burn = dashboard.derive_pipeline(events, now=0.0)["burn"]
    assert burn["elapsed_seconds"] >= 0.0
    assert burn["stale_seconds"] == 0.0
    assert burn["usd_per_min"] is None or burn["usd_per_min"] > 0


def test_every_log_event_kind_in_core_is_classified_by_at_most_one_phase():
    """#224's failure mode is a per-consumer kind table drifting from the emitters. Pin
    both directions: no kind is claimed by two phases, and every kind `_PHASE_KINDS`
    names is either really emitted in the tree or the sentinel `report` has none."""
    seen: dict[str, str] = {}
    for key, _label, kinds in dashboard._PHASE_KINDS:
        for k in kinds:
            assert k not in seen, f"{k} claimed by both {seen.get(k)} and {key}"
            seen[k] = key

    import pathlib
    root = pathlib.Path(dashboard.__file__).resolve().parent
    src = "\n".join(p.read_text(encoding="utf-8") for p in root.glob("*.py"))
    # `check_gate` is logged from cli.py; the rest from harness/gepa/skillopt/rundir/gate.
    for kind, phase in seen.items():
        assert f'"{kind}"' in src, f"{kind} ({phase}) is not emitted anywhere in core/"
