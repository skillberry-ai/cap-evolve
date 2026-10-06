"""The gate decides on the MEAN, so a candidate that TRADES tasks passes silently.

`r3_decide` was accepted in run 36175707483 and became the champion. Its own gate notes say:

    Regressions [33722, 46646]; FIXED vs both controls [49036],
    BROKE vs both controls [33722] -- net zero

So the accept was booked *knowing* it broke a task against BOTH concurrent controls. On the
280-task sealed test split that champion scored 0.764 against the seed's 0.632 -- but the
composition was 54 improved / 17 regressed / 209 unchanged, and every regression sampled went
1.000 -> 0.000 (`60-7`, `384-4`, `82-38`, `183-8`, `192-22`, `387-16`, `524-31`, `560-12`,
`45635`, `48643`). The champion destroys whole tasks it previously solved.

The gate was not wrong: the net was strongly positive. The gate is *indifferent to
composition*, and nothing forced the trade-off to be examined. The per-task signal already
existed at accept time -- `harness._candidate_task_impact` computes broke/fixed for LEDGER.md
and the journal RESULT stamp -- but it reached neither the `step` record the whole framework
reads nor the suite report a reader actually looks at. A mid-run trade was invisible unless
you read the agent's prose.

So: record it on the step, render it in the suite report, and make the veto OPT-IN. NOT
auto-reject -- on a 40-task val split with SE ~ 0.079 a hard no-regression rule would reject
nearly everything, and these runs show tasks flipping 1.0 -> 0.0 between two BYTE-IDENTICAL
control replicates. Measure and surface first; veto on request.
"""

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
LIB = REPO / "ci" / "benchmarks" / "lib"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(CORE))


# --- a 40-task val split where one edit trades tasks ------------------------------

class _Adapter:
    """40 tasks `t00`..`t39`; a task passes iff `cfg.txt` lists its id.

    Forty because that is the real `full_verified` val width, and because the paired
    gate's verdict depends on the vector LENGTH: the same 3-fixed/1-broke trade is a
    different Delta-bar comparison at n=40 than at n=4.
    """

    TASKS = [f"t{i:02d}" for i in range(40)]

    def tasks(self, split):
        from cap_evolve import Task
        return [Task(id=t) for t in self.TASKS]

    def run_target(self, task, ctx, *, seed=0):
        from cap_evolve import Rollout
        cfg = Path(ctx) / "cfg.txt"
        passing = cfg.read_text(encoding="utf-8").split() if cfg.exists() else []
        return Rollout(task_id=task.id, output="pass" if task.id in passing else "fail")

    def score(self, task, rollout):
        from cap_evolve import Score
        r = 1.0 if rollout.output == "pass" else 0.0
        return Score(task_id=task.id, reward=r, trial_rewards=[r])

    def apply(self, candidate_dir, edits=None):
        return None


#: Seed passes t00..t09 (10/40 = 0.250).
_SEED_PASS = [f"t{i:02d}" for i in range(10)]
#: The trade: BREAK t00 (was passing), FIX t10/t11/t12 (were failing). Net +2/40.
_TRADE_PASS = [t for t in _SEED_PASS if t != "t00"] + ["t10", "t11", "t12"]


def _trade_run(tmp_path):
    """A run dir with a scored seed, plus an optimizer that writes the trading candidate."""
    from cap_evolve import RunDir, harness
    from cap_evolve.splits import Splits

    adapter = _Adapter()
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "cfg.txt").write_text(" ".join(_SEED_PASS), encoding="utf-8")

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="trade")
    run_dir.write_splits(Splits(train=[], val=list(_Adapter.TASKS), test=[], seed=0))
    run_dir.snapshot("seed", seed)
    run_dir.set_best("seed")

    base = harness.evaluate_candidate(adapter, run_dir.candidate_dir("seed"),
                                      run_dir=run_dir, split="val", tag="seed")
    assert abs(base.reward - 0.25) < 1e-9, base.reward

    opt = harness.optimizer_from_command(
        ["python3", "-c",
         "import sys,pathlib;(pathlib.Path(sys.argv[1])/'cfg.txt')"
         f".write_text({' '.join(_TRADE_PASS)!r})",
         "{workdir}"])
    return adapter, run_dir, base, opt


def _step(tmp_path, **gate_extra):
    """Run ONE trading step through the real gate.

    ``k_se=0.2`` is the strictness `full_verified` actually runs at, and it is also the only
    honest way to pin "fixes 3 / breaks 1 is ACCEPTED": with binary per-task rewards and a
    zero-padded vector, mean and SE come out ALGEBRAICALLY EQUAL for f=3/b=1 at any n
    (mean = (f-b)/n, SE = sqrt((f+b) - (f-b)^2/n) / sqrt(n(n-1)), and accept needs
    (f-b)^2 > f+b, i.e. 4 > 4). At k_se=1.0 that trade sits exactly ON the bar and the
    verdict is decided by float rounding -- not something to assert behaviour on.

    ``footprint_gate=False`` so the vector is the full 40 and this test is about the gate's
    composition blindness, not about whether a one-file diff localizes.
    """
    from cap_evolve import harness
    adapter, run_dir, base, opt = _trade_run(tmp_path)
    gate_kwargs = {"mode": "paired", "k_se": 0.2, **gate_extra}
    step = harness.run_step(adapter, run_dir=run_dir,
                            parent_dir=run_dir.candidate_dir("seed"),
                            optimizer=opt, instructions="x", current_val=base,
                            gate_kwargs=gate_kwargs, footprint_gate=False)
    return run_dir, step


def _step_events(run_dir):
    out = []
    for line in run_dir.events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("kind") == "step":
            out.append(rec)
    return out


# --- 1. accepted, and it says what it traded ---------------------------------------

def test_a_candidate_that_trades_tasks_is_accepted_and_records_what_it_traded(tmp_path):
    """The r3_decide shape: net positive, so it is ACCEPTED -- but the step now carries
    the ids it broke and fixed, not just a reward. This is the whole point: the accept is
    not the defect, the silence was."""
    run_dir, step = _step(tmp_path)

    assert step["accepted"] is True, step["decision"]["reason"]
    # The trade itself, on the returned step.
    assert step["broke"] == ["t00"], step
    assert sorted(step["fixed"]) == ["t10", "t11", "t12"], step
    # And on the gate decision, so any consumer of `decision` sees the composition.
    d = step["decision"]
    assert d["broke"] == ["t00"] and sorted(d["fixed"]) == ["t10", "t11", "t12"], d
    assert d["n_broke"] == 1 and d["n_fixed"] == 3, d

    # The canonical `step` record -- what LEDGER/RUNMAP/the dashboard/the TUI and
    # ci/benchmarks/lib/metrics.py all read -- must carry it too, or nothing downstream can.
    steps = _step_events(run_dir)
    assert len(steps) == 1, steps
    ev = steps[0]
    assert ev["accept"] is True
    assert ev["broke"] == ["t00"] and sorted(ev["fixed"]) == ["t10", "t11", "t12"], ev
    assert ev["n_broke"] == 1 and ev["n_fixed"] == 3, ev


# --- 2 & 3. the opt-in veto --------------------------------------------------------

def test_gate_max_broke_zero_vetoes_the_trade_and_names_the_task_it_broke(tmp_path):
    """`gate_max_broke=0` turns the same gate-passing trade into a reject, and the reason
    names the id -- a veto whose reason does not say WHAT it broke is not actionable."""
    run_dir, step = _step(tmp_path, gate_max_broke=0)

    assert step["accepted"] is False, step["decision"]["reason"]
    reason = step["decision"]["reason"]
    assert "t00" in reason, reason
    assert "gate_max_broke" in reason, reason
    # The composition is still recorded on a veto -- a reject that hides what it traded is
    # exactly as unreadable as the accept that hid it.
    assert step["broke"] == ["t00"] and sorted(step["fixed"]) == ["t10", "t11", "t12"], step
    # The gate's own statistics are untouched by the veto: it rejected a candidate whose
    # measured mean CLEARED the bar, and the numbers must still say so.
    assert step["decision"]["delta"] > step["decision"]["threshold"], step["decision"]


def test_gate_max_broke_above_the_count_leaves_the_trade_accepted(tmp_path):
    """The knob is a BUDGET, not a switch: one break under a budget of one still accepts."""
    _, step = _step(tmp_path, gate_max_broke=1)
    assert step["accepted"] is True, step["decision"]["reason"]
    assert step["broke"] == ["t00"], step


def test_gate_max_broke_cannot_turn_a_reject_into_an_accept(tmp_path):
    """A veto only ever subtracts. Set the bar unreachably high and a rejected candidate
    stays rejected -- the knob must not be readable as permission."""
    from cap_evolve import gate as gate_mod
    d = gate_mod.decide(0.5, 0.51, split="val", mode="significant",
                        candidate_stderr=0.08, current_stderr=0.08,
                        broke=[], fixed=["a", "b"], gate_max_broke=99)
    assert d.accept is False
    assert d.fixed == ["a", "b"] and d.broke == []


# --- 4. the default path is unchanged (regression guard, passes in BOTH states) ----

def test_the_default_gate_decision_is_byte_identical_to_the_pre_change_gate():
    """With the knob unset, every field of every decision must match the fixture captured
    from the gate BEFORE this change -- 20 cases covering all four modes, both SE-collapse
    strict fallbacks, the paired SE floor and the low-coverage indecisive guard.

    This is the load-bearing constraint, not a nicety: existing benchmark history is only
    comparable to new runs if the accept/reject decision did not move. `gate_max_broke`
    unset must be a no-op down to the reason STRING, because `dashboard.reduce_run` regexes
    numbers out of exactly that string.

    `accept`/`reason`/`indecisive` are compared EXACTLY -- they are the decision, and the
    reason is rounded to 4 decimal places so it is stable. The three raw floats get a 1e-12
    tolerance, because their last bits are a CPython-version artifact and not a behaviour
    change: `sum()` over floats gained Neumaier compensation in 3.12, so the same
    `paired_deltas` yield an SE of 0.049999999999999996 on 3.14 and 0.04999999999999999 on
    CI's 3.11. Pinning bit-exact values would assert the interpreter's summation order, which
    is not this gate's contract.

    Every grid case is also kept AWAY from the bar on purpose. With binary per-task rewards a
    paired accept needs `(f-b)^2 > f+b`, so the f=3/b=1 trade the issue's test plan names is
    exactly ON the bar at any n -- mean and SE are algebraically equal -- and its verdict is
    then decided by which interpreter's `sum()` ran. Two such cases were in the first version
    of this fixture and one of them disagreed between 3.14 and 3.11. The only zero-margin
    cases left are the deliberate ones where delta is EXACTLY 0.0 (`strict_reject`,
    `significant_se_zero_flat`): no summation, no ulp, and "no change must not accept" is the
    boundary being pinned.
    """
    from cap_evolve import gate as gate_mod

    cases = json.loads((FIXTURES / "gate_decisions_default.json").read_text(encoding="utf-8"))
    assert len(cases) >= 20, "fixture shrank -- it is the coverage, not a formality"

    grid = _fixture_grid()
    assert set(grid) == {c["label"] for c in cases}, "fixture and grid drifted apart"

    exact = {"accept", "reason", "indecisive"}
    for case in cases:
        kw = dict(grid[case["label"]])
        got = gate_mod.decide(kw.pop("current_val"), kw.pop("candidate_val"),
                              split="val", **kw).to_dict()
        for field, want in case["decision"].items():
            if field in exact or want is None or isinstance(want, bool):
                assert got[field] == want, (
                    f"{case['label']}: {field} moved {want!r} -> {got[field]!r}. The default "
                    "accept/reject path must be unchanged or benchmark history stops being "
                    "comparable.")
            else:
                assert abs(got[field] - want) <= 1e-12 * max(1.0, abs(want)), (
                    f"{case['label']}: {field} moved {want!r} -> {got[field]!r} by more than "
                    "float noise -- the gate's statistics changed.")
        # The new fields exist but are EMPTY when nothing was passed -- absent stays absent
        # rather than becoming a fabricated zero-length claim about composition.
        assert got["broke"] == [] and got["fixed"] == []
        assert got["n_broke"] == 0 and got["n_fixed"] == 0


def test_no_fixture_case_decides_on_a_float_ulp():
    """The fixture is only a regression guard if each case's verdict is determinate.

    A case whose `delta` sits within float noise of its `threshold` is decided by the
    interpreter's summation order, so it would flake across CPython versions AND would not
    detect a real change to the bar. Exact-zero deltas are exempt: those are the deliberate
    "no change must not accept" boundaries, with no summation to be noisy about.
    """
    from cap_evolve import gate as gate_mod

    exempt = {"strict_reject", "significant_se_zero_flat"}
    for label, kw in _fixture_grid().items():
        kw = dict(kw)
        d = gate_mod.decide(kw.pop("current_val"), kw.pop("candidate_val"), split="val", **kw)
        if label in exempt:
            assert d.delta == 0.0 and d.accept is False, (label, d.delta)
            continue
        assert abs(d.delta - d.threshold) > 1e-9, (
            f"{label}: delta {d.delta!r} is within float noise of threshold {d.threshold!r}. "
            "With binary rewards a paired accept needs (f-b)^2 > f+b, so an f=3/b=1 delta "
            "vector lands exactly on the bar — pick a determinate shape.")


def _fixture_grid() -> dict:
    """The inputs behind ``fixtures/gate_decisions_default.json``, by label."""
    return {
        # f=3/b=0: (f-b)^2=9 > f+b=3, so this ACCEPTS with real margin. Deliberately not
        # f=3/b=1 -- see the knife-edge note in the test above.
        "paired_accept": dict(current_val=0.5, candidate_val=0.6, mode="paired",
                              paired_deltas=[1.0, 1.0, 1.0, 0.0, 0.0, 0.0]),
        "paired_reject_noisy": dict(current_val=0.5, candidate_val=0.52, mode="paired",
                                    paired_deltas=[1.0, -1.0, 1.0, -1.0, 0.1]),
        # The r3_decide shape on a 40-task val split, at f=4/b=1 so the accept is determinate
        # (9 > 5, margin 0.0197) rather than exactly on the bar.
        "paired_trade_net_positive": dict(current_val=0.4, candidate_val=0.45, mode="paired",
                                          paired_deltas=[1.0] * 4 + [-1.0] + [0.0] * 35),
        "paired_se_zero_strict_fallback": dict(current_val=0.5, candidate_val=0.6,
                                               mode="paired", paired_deltas=[0.25]),
        "paired_se_zero_negative": dict(current_val=0.5, candidate_val=0.4, mode="paired",
                                        paired_deltas=[-0.25]),
        "paired_identical_deltas": dict(current_val=0.5, candidate_val=0.6, mode="paired",
                                        paired_deltas=[0.1, 0.1, 0.1, 0.1]),
        "paired_with_se_floor": dict(current_val=0.5, candidate_val=0.6, mode="paired",
                                     paired_deltas=[0.0, 0.1, 0.0, 0.1],
                                     paired_se_floor=0.0113),
        "paired_k_se_2": dict(current_val=0.5, candidate_val=0.6, mode="paired", k_se=2.0,
                              paired_deltas=[1.0, 1.0, 0.0, -1.0, 0.0, 0.0]),
        "paired_empty_falls_back": dict(current_val=0.5, candidate_val=0.6, mode="paired",
                                        paired_deltas=[], candidate_stderr=0.02,
                                        current_stderr=0.02),
        "significant_accept": dict(current_val=0.5, candidate_val=0.6, mode="significant",
                                   candidate_stderr=0.02, current_stderr=0.02),
        "significant_reject": dict(current_val=0.5, candidate_val=0.51, mode="significant",
                                   candidate_stderr=0.08, current_stderr=0.08),
        "significant_se_zero": dict(current_val=0.5, candidate_val=0.6, mode="significant"),
        "significant_se_zero_flat": dict(current_val=0.5, candidate_val=0.5,
                                         mode="significant"),
        "threshold_accept": dict(current_val=0.5, candidate_val=0.7, mode="threshold",
                                 threshold=0.1),
        "threshold_reject": dict(current_val=0.5, candidate_val=0.55, mode="threshold",
                                 threshold=0.1),
        "strict_accept": dict(current_val=0.5, candidate_val=0.5001, mode="strict"),
        "strict_reject": dict(current_val=0.5, candidate_val=0.5, mode="strict"),
        "low_coverage_indecisive": dict(current_val=0.5, candidate_val=0.9, mode="paired",
                                        paired_deltas=[1.0, 1.0], coverage=0.25),
        "coverage_ok": dict(current_val=0.5, candidate_val=0.6, mode="paired",
                            paired_deltas=[1.0, 1.0, -1.0, 0.0], coverage=0.95),
        "coverage_guard_disabled": dict(current_val=0.5, candidate_val=0.9, mode="paired",
                                        paired_deltas=[1.0, 1.0], coverage=0.25,
                                        min_coverage=0.0),
    }


def test_the_step_that_sets_no_knob_decides_exactly_as_it_did_before(tmp_path):
    """End-to-end companion to the fixture: the trading step is ACCEPTED with the knob
    unset, and its reason carries no veto text at all."""
    _, step = _step(tmp_path)
    assert step["accepted"] is True
    assert "gate_max_broke" not in step["decision"]["reason"]
    assert "broke" not in step["decision"]["reason"]


# --- 5. the unscored-task drop rule -----------------------------------------------

def _pt(task_id, reward, *, stderr=0.0, valid_trials=1):
    return {"task_id": task_id, "reward": reward, "stderr": stderr,
            "raw": {"valid_trials": valid_trials, "n_trials": 1,
                    "errored_trials": 0 if valid_trials else 1}}


def test_a_task_unscored_on_one_side_is_dropped_not_counted_as_broke():
    """A task with no valid trial on either side is MISSING DATA, not a break.

    That rule exists because a Docker Hub 429 storm once produced `paired Delta=-0.6400`
    from infrastructure rather than content. Counting an unscored task as broke would hand
    `gate_max_broke` the same failure mode: one image-pull outage would veto a genuinely
    better candidate, and it would do it while naming a task nobody ever ran.
    """
    from cap_evolve import harness

    parent = [_pt("a", 1.0), _pt("b", 1.0), _pt("c", 0.0)]
    # The candidate never validly ran `a` (all trials errored) and really broke `b`.
    cand = [_pt("a", 0.0, valid_trials=0), _pt("b", 0.0), _pt("c", 1.0)]

    mv = harness.movement(parent, cand)
    assert mv["broke"] == ["b"], mv
    assert mv["fixed"] == ["c"], mv
    assert "a" not in mv["broke"] and "a" not in mv["fixed"] and "a" not in mv["unresolved"]

    # ... and the veto cannot fire on it either.
    from cap_evolve import gate as gate_mod
    d = gate_mod.decide(0.5, 0.6, split="val", mode="strict",
                        broke=mv["broke"], fixed=mv["fixed"], gate_max_broke=1)
    assert d.accept is True, d.reason


def test_a_sub_noise_flip_is_unresolved_not_broke():
    """The 2*SE bar is shared, not re-derived: a 1.0 -> 0.9 move at 10 trials is one
    flipped rollout, and stamping it a behavioural break is what poisoned three rounds of
    reasoning on run_finalrun6."""
    from cap_evolve import harness
    parent = [_pt("a", 1.0, stderr=0.1)]
    cand = [_pt("a", 0.9, stderr=0.1)]
    mv = harness.movement(parent, cand)
    assert mv["broke"] == [] and mv["unresolved"] == ["a"], mv


def test_the_gate_time_movement_is_the_same_rule_the_ledger_publishes():
    """One definition of broke/fixed, not two.

    `_candidate_task_impact` (LEDGER.md + the journal RESULT stamp) and the gate-time
    classification must agree on the same evidence, or a run's ledger and its step record
    disagree about what the accepted candidate did -- which is worse than either being
    wrong alone. Four copies of a bar is how three of them stayed at 1e-9 while one was
    fixed (see `harness.move_is_resolved`).
    """
    import tempfile
    from cap_evolve import RunDir, harness

    tmp = Path(tempfile.mkdtemp())
    rd = RunDir.create(tmp / ".capevolve", ts="sync")
    vdir = rd.rollouts / "val"
    vdir.mkdir(parents=True, exist_ok=True)

    def _rollout(tag, tid, reward):
        rec = {"input": {}, "rollout": {"task_id": tid, "error": None},
               "score": {"task_id": tid, "reward": reward, "feedback": "",
                         "raw": {"errored": False}}}
        (vdir / f"{tid}__{tag}__t0.json").write_text(json.dumps(rec), encoding="utf-8")

    for tid, r in [("1", 1.0), ("2", 1.0), ("3", 0.0), ("4", 0.5)]:
        _rollout("seed", tid, r)
    for tid, r in [("1", 1.0), ("2", 0.0), ("3", 1.0), ("4", 0.25)]:
        _rollout("cand_0001", tid, r)
    rd.log_event("step", candidate="cand_0001", parent="seed", accept=False)

    ledger = harness._candidate_task_impact(rd, "cand_0001", "val",
                                            parent_of={"cand_0001": "seed"})
    seed_sr = harness.split_result_from_rollouts(rd, "seed", "val")
    cand_sr = harness.split_result_from_rollouts(rd, "cand_0001", "val")
    gate_time = harness.movement(seed_sr.per_task, cand_sr.per_task)

    assert gate_time["broke"] == ledger["broke"] == ["2"]
    assert gate_time["fixed"] == ledger["fixed"] == ["3"]
    assert gate_time["unresolved"] == ledger["unresolved"]


# --- 6. the suite report renders the trade ----------------------------------------

def _metrics():
    if str(LIB) not in sys.path:
        sys.path.insert(0, str(LIB))
    spec = importlib.util.spec_from_file_location("_bench_metrics_trade", LIB / "metrics.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_bench_metrics_trade"] = mod
    spec.loader.exec_module(mod)
    return mod


def _suite_run(tmp: Path) -> Path:
    """A finished held-out run whose accepted candidate traded tasks."""
    rd = tmp / "run_trade"
    rd.mkdir(parents=True)

    def _ptj(t, r):
        return {"task_id": t, "reward": r, "raw": {"errored": False}}

    (rd / "baseline.json").write_text(json.dumps({
        "val": {"reward": 0.25, "stderr": 0.07,
                "per_task": [_ptj(f"v{i}", 1.0 if i < 1 else 0.0) for i in range(4)]}}))
    (rd / "final.json").write_text(json.dumps({
        "baseline_id": "seed", "test_delta": 0.25,
        "test_baseline": {"reward": 0.5,
                          "per_task": [_ptj(f"s{i}", 1.0 if i < 2 else 0.0) for i in range(4)]},
        "test": {"reward": 0.75,
                 "per_task": [_ptj(f"s{i}", 0.0 if i == 0 else 1.0) for i in range(4)]}}))
    (rd / "state.json").write_text(json.dumps({
        "best_id": "cand_0001",
        "spent": {"iterations": 2, "usd": 1.0, "optimizer_usd": 2.0,
                  "runner_seconds": 10.0, "optimizer_seconds": 20.0}}))
    events = [
        {"kind": "evaluate", "tag": "seed", "split": "val", "reward": 0.25,
         "cost_usd": 0.5, "seconds": 5.0},
        # The accepted trade, and a rejected candidate that broke nothing.
        {"kind": "step", "candidate": "cand_0001", "accept": True, "val": 0.325,
         "parent": "seed", "parent_val": 0.25, "cost_usd": 0.25, "runner_seconds": 5.0,
         "broke": ["t00"], "fixed": ["t10", "t11", "t12"], "n_broke": 1, "n_fixed": 3},
        {"kind": "step", "candidate": "cand_0002", "accept": False, "val": 0.25,
         "parent": "cand_0001", "parent_val": 0.325, "cost_usd": 0.25,
         "runner_seconds": 5.0, "broke": [], "fixed": [], "n_broke": 0, "n_fixed": 0},
        {"kind": "evaluate", "tag": "FINAL", "split": "test", "reward": 0.75,
         "cost_usd": 0.0, "seconds": 1.0},
        {"kind": "evaluate", "tag": "FINAL_seed", "split": "test", "reward": 0.5,
         "cost_usd": 0.0, "seconds": 1.0},
    ]
    (rd / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    return rd


def test_the_suite_report_shows_what_an_accepted_candidate_traded(tmp_path):
    """`report.md`/the suite report showed only the FINAL champion's per-task base->opt, so
    a mid-run trade was invisible unless you read the agent's prose. The per-iteration table
    already has a row per candidate; the composition belongs on it."""
    m = _metrics()
    rd = _suite_run(tmp_path)
    out = m.suite_report(str(rd), "spreadsheetbench", "full", "agent", 2)

    row = [ln for ln in out.splitlines() if "cand_0001" in ln and ln.startswith("|")]
    assert row, out
    assert "+3 fixed / -1 broke" in row[0], row[0]
    # A candidate that traded nothing must not be decorated with a fabricated "0 fixed /
    # 0 broke" claim -- absent stays absent.
    row2 = [ln for ln in out.splitlines() if "cand_0002" in ln and ln.startswith("|")][0]
    assert "fixed" not in row2, row2


def test_the_suite_report_is_unchanged_for_a_run_that_recorded_no_movement(tmp_path):
    """Every run in published history predates this field. Their reports must render exactly
    as they did, or the benchmarks page starts showing a column of dashes for the past."""
    m = _metrics()
    rd = _suite_run(tmp_path)
    events = [json.loads(ln) for ln in
              (rd / "events.jsonl").read_text().splitlines() if ln.strip()]
    for ev in events:
        for k in ("broke", "fixed", "n_broke", "n_fixed"):
            ev.pop(k, None)
    (rd / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))

    out = m.suite_report(str(rd), "spreadsheetbench", "full", "agent", 2)
    assert "fixed /" not in out, out
    assert "broke" not in out, out
    # ... and the report is still a report.
    assert "**Suite (held-out):**" in out and "### Iterations" in out


# --- 7. agent mode, which is where this actually happened --------------------------

SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"


def _load_script(name: str):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(f"_ao_trade_{name}", SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"_ao_trade_{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_the_agent_mode_step_record_carries_the_round_tables_movement(tmp_path):
    """`r3_decide` was booked ACCEPT in run 36175707483 with "BROKE vs both controls [33722]"
    living only in the agent's prose. `round.py` persists the round table and `commit.py`
    reads the gate's numbers back off it onto the step record — the movement has to ride the
    same channel, or the one run type this issue is about still records nothing."""
    from cap_evolve import RunDir
    commit = _load_script("commit")

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ao")
    work = run_dir.root / "work"
    work.mkdir(parents=True, exist_ok=True)
    stem = f"round_i{int(run_dir.spent.iterations)}"
    (work / f"{stem}.json").write_text(json.dumps({
        "parent": {"tag": "seed", "reward": 0.5, "n_tasks": 40},
        "gated_against": {"tag": "seed", "mode": "parent"},
        "candidates": [{
            "tag": "r3_decide", "reward": 0.55, "gate_delta": 0.05,
            "gate_threshold": 0.01, "verdict": "accept", "regressions": ["33722"],
            "movement": {"broke": ["33722"], "fixed": ["49036"], "unresolved": ["46646"]},
            "n_broke": 1, "n_fixed": 1,
        }],
    }), encoding="utf-8")

    gate = commit._round_gate_numbers(run_dir, "r3_decide")
    assert gate["broke"] == ["33722"], gate
    assert gate["fixed"] == ["49036"], gate
    assert gate["n_broke"] == 1 and gate["n_fixed"] == 1, gate


def test_an_older_round_table_without_movement_stays_silent(tmp_path):
    """A `gate_check`-only round, and every table written before this field existed, has no
    movement. A missing measurement must stay missing rather than be published as
    "broke nothing" -- which is a claim, and a false one."""
    from cap_evolve import RunDir
    commit = _load_script("commit")

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ao_old")
    work = run_dir.root / "work"
    work.mkdir(parents=True, exist_ok=True)
    (work / f"round_i{int(run_dir.spent.iterations)}.json").write_text(json.dumps({
        "parent": {"tag": "seed", "reward": 0.5, "n_tasks": 40},
        "candidates": [{"tag": "cand_1", "reward": 0.55, "gate_delta": 0.05,
                        "gate_threshold": 0.01, "verdict": "accept", "regressions": []}],
    }), encoding="utf-8")

    gate = commit._round_gate_numbers(run_dir, "cand_1")
    assert "broke" not in gate and "fixed" not in gate, gate
    assert "n_broke" not in gate and "n_fixed" not in gate, gate
    # ... and the numbers it DOES have are untouched.
    assert gate["gate_delta"] == 0.05 and gate["gate_threshold"] == 0.01


def test_agent_modes_regression_list_and_the_shared_broke_rule_cannot_diverge():
    """`gate_check.regressions` (which feeds `--veto-regressions`) and
    `harness.movement`'s `broke` must name the SAME tasks.

    They are two functions over the same evidence, and agent-optimize now publishes both --
    the veto list and the recorded movement. If they ever disagree, a round says it broke
    task X while vetoing on task Y. Checked over every combination of fifths, the reward
    granularity at num_trials=5, which is where an earlier divergence between agent-optimize
    and the harness actually bit (see test_regression_gate).
    """
    from cap_evolve import harness
    gc = _load_script("gate_check")

    class _Side:
        def __init__(self, per_task):
            self.per_task = [{"task_id": t, "reward": r, "trials": [{"reward": r}]}
                             for t, r in per_task.items()]

    fifths = [i / 5 for i in range(6)]
    for pr in fifths:
        for cd in fifths:
            a, b = _Side({"t1": pr}), _Side({"t1": cd})
            assert gc.regressions(a, b) == harness.movement(a.per_task, b.per_task)["broke"], \
                (pr, cd)


def test_every_gate_call_site_passes_the_composition_so_the_veto_is_never_inert():
    """A `gate_max_broke` that reaches `decide` with an empty `broke` list rejects nothing
    and says nothing -- strictly worse than the knob not existing, because the operator
    believes it is on. There are two `decide` call sites inside the engine (`run_step` and
    gepa's `_full_val_gate`, which deliberately does NOT route through `run_step`); both must
    hand it the movement. Pinned on the SOURCE, walked as a syntax tree, because the failure
    mode is SILENCE: a run through the un-wired path produces no wrong number and no error, so
    no test of behaviour can catch it."""
    import ast

    seen = 0
    for mod in ("harness.py", "gepa.py"):
        path = CORE / "cap_evolve" / mod
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "decide"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "gate_mod"):
                continue
            seen += 1
            kw = {k.arg for k in node.keywords}
            assert {"broke", "fixed"} <= kw, (
                f"{mod}:{node.lineno} calls gate_mod.decide without broke=/fixed= — "
                "gate_max_broke would be silently inert through this path, which is worse "
                f"than the knob not existing. Keywords: {sorted(k for k in kw if k)}")
    assert seen == 2, (
        f"expected the 2 known engine gate call sites (run_step, gepa._full_val_gate), "
        f"found {seen} — a new one must pass the movement too")
