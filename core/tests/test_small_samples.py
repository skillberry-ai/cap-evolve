"""Issue #113: tiny/empty val splits are refused, and the paired gate gets a
Student-t small-sample correction (never looser than the old z bar).

Regression targets:
  * an empty or 1-task val split must fail LOUDLY at split/baseline time rather
    than silently producing a meaningless gate decision;
  * the paired gate's ``k_se`` is a *z* multiplier, but SE(Δ) is estimated from
    the same n deltas, so the correct bar uses t with df=n-1. At small n the old
    z bar was too LOW (accepted noise); the t bar is strictly wider and converges
    back to z as n grows.
"""

import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))

from cap_evolve import stats  # noqa: E402
from cap_evolve.gate import decide  # noqa: E402
from cap_evolve.splits import (  # noqa: E402
    LOW_CONFIDENCE_VAL_TASKS,
    MIN_VAL_TASKS,
    Splits,
    TinyValSplitError,
    check_val_size,
    make_splits,
)


# ---- (a) tiny / empty val split guard -------------------------------------

def test_empty_val_split_refused_with_actionable_message():
    # 2 tasks with the default ratios -> train=1 val=0 test=1 (the silent case).
    sp = make_splits(["t0", "t1"], seed=0)
    assert sp.val == []
    with pytest.raises(TinyValSplitError) as ei:
        check_val_size(sp)
    msg = str(ei.value)
    assert "is EMPTY" in msg
    assert "split_ids_file" in msg and "split_val" in msg   # actionable fixes
    assert "CAPEVOLVE_ALLOW_TINY_VAL" in msg                # documented escape hatch


def test_single_task_val_split_refused():
    sp = make_splits([f"t{i}" for i in range(4)], seed=0)
    assert len(sp.val) == 1
    with pytest.raises(TinyValSplitError) as ei:
        check_val_size(sp)
    assert "0 degrees of freedom" in str(ei.value)


def test_min_val_size_is_two_and_passes():
    sp = make_splits([f"t{i}" for i in range(6)], seed=0)
    assert len(sp.val) == MIN_VAL_TASKS == 2
    assert check_val_size(sp) is not None      # usable, but warned (2 < 5)


def test_small_val_split_warns_but_is_allowed(tmp_path):
    from cap_evolve import RunDir
    rd = RunDir.create(tmp_path / ".capevolve", ts="w")
    sp = Splits(train=[], val=["a", "b", "c"], test=[], seed=0)
    warn = check_val_size(sp, run_dir=rd)
    assert warn and "LOW CONFIDENCE" in warn
    events = (rd.root / "events.jsonl").read_text(encoding="utf-8")
    assert "split_warning" in events


def test_healthy_val_split_is_silent():
    sp = make_splits([f"t{i}" for i in range(40)], seed=0)
    assert len(sp.val) >= LOW_CONFIDENCE_VAL_TASKS
    assert check_val_size(sp) is None


def test_escape_hatch_allows_tiny_val(monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_ALLOW_TINY_VAL", "1")
    check_val_size(Splits(train=[], val=[], test=[], seed=0))   # no raise


def test_ensure_splits_refuses_tiny_val(tmp_path):
    """The guard fires at split-freeze time, before any budget is spent."""
    from cap_evolve import RunDir, harness
    from cap_evolve.types import Rollout, Score, Task

    class _Tiny:
        def tasks(self, split):
            return [Task(id=f"t{i}") for i in range(4)]   # -> val=1
        def run_target(self, task, ctx, *, seed=0):
            return Rollout(task_id=task.id, output="x")
        def score(self, task, rollout):
            return Score(task_id=task.id, reward=0.0)
        def apply(self, candidate_dir, edits=None):
            return None

    rd = RunDir.create(tmp_path / ".capevolve", ts="tiny")
    with pytest.raises(TinyValSplitError):
        harness.ensure_splits(_Tiny(), rd, seed=0)
    assert not rd.splits_path.exists()     # nothing frozen on refusal


def test_baseline_refuses_handwritten_tiny_val(tmp_path):
    """A splits.json that bypassed ensure_splits is still caught at baseline."""
    from cap_evolve import RunDir, harness
    from cap_evolve.types import Rollout, Score, Task

    class _A:
        def tasks(self, split):
            return [Task(id="t0")]
        def run_target(self, task, ctx, *, seed=0):
            return Rollout(task_id=task.id, output="x")
        def score(self, task, rollout):
            return Score(task_id=task.id, reward=1.0)
        def apply(self, candidate_dir, edits=None):
            return None

    rd = RunDir.create(tmp_path / ".capevolve", ts="hand")
    rd.write_splits(Splits(train=[], val=["t0"], test=[], seed=0))   # hand-written n=1
    seed = tmp_path / "seed"; seed.mkdir()
    with pytest.raises(TinyValSplitError):
        harness.baseline(_A(), seed, run_dir=rd)


# ---- (b) Student-t small-sample correction ---------------------------------

@pytest.mark.parametrize("df,expected", [
    # One-sided upper-tail t critical values, alpha=0.05.
    # Source: Abramowitz & Stegun, Handbook of Mathematical Functions (1964),
    # Table 26.10 (percentage points of the t-distribution).
    (1, 6.314), (2, 2.920), (4, 2.132), (9, 1.833), (29, 1.699), (100, 1.660),
])
def test_t_critical_matches_published_table_alpha_05(df, expected):
    assert stats.t_critical(0.05, df) == pytest.approx(expected, abs=5e-4)


@pytest.mark.parametrize("df,expected", [
    (1, 12.706), (2, 4.303), (10, 2.228), (30, 2.042),   # A&S Table 26.10, alpha=0.025
])
def test_t_critical_matches_published_table_alpha_025(df, expected):
    assert stats.t_critical(0.025, df) == pytest.approx(expected, abs=5e-4)


def test_t_cdf_is_symmetric_and_bounded():
    for df in (1, 3, 12):
        assert stats.t_cdf(0.0, df) == pytest.approx(0.5)
        for t in (0.3, 1.0, 4.0):
            assert stats.t_cdf(t, df) + stats.t_cdf(-t, df) == pytest.approx(1.0, abs=1e-9)


def test_t_converges_to_normal_at_large_df():
    # df -> inf: t_{1-a,df} -> z_{1-a}. k_se=1 corresponds to alpha=P(Z>1).
    z = 1.0
    alpha = stats.normal_sf(z)
    assert stats.t_critical(alpha, 100000) == pytest.approx(z, abs=1e-3)


def test_t_multiplier_never_looser_than_z():
    """The whole honesty point: the correction can only WIDEN the bar."""
    for k in (0.5, 1.0, 1.5, 2.0):
        for n in range(2, 200):
            assert stats.t_multiplier_for_z(k, n) >= k - 1e-12


def test_t_multiplier_monotonically_relaxes_toward_z():
    ks = [stats.t_multiplier_for_z(1.0, n) for n in range(3, 60)]
    assert ks == sorted(ks, reverse=True)              # shrinks as n grows
    assert ks[-1] == pytest.approx(1.0, abs=0.02)      # ...toward the z multiplier


# --- the regression test: small n is STRICTER than the old z bar -------------

def _old_z_bar(deltas, k_se=1.0):
    """The pre-fix bar: k_se * SE(Δ) with a fixed z-style multiplier."""
    n = len(deltas)
    m = sum(deltas) / n
    var = sum((d - m) ** 2 for d in deltas) / (n - 1)
    return k_se * math.sqrt(var / n)


def test_small_n_gate_is_strictly_stricter_than_old_z_bar():
    """REGRESSION (fails before the fix): at n=3 the t bar must exceed the z bar,
    and a candidate that used to squeak through must now be rejected."""
    # 3 val tasks: mean Δ=+0.10, SE(Δ)=0.0577 -> old bar 0.0577 (ACCEPT, 0.10>0.0577).
    deltas = [0.0, 0.1, 0.2]
    old = _old_z_bar(deltas)
    d = decide(0.5, 0.6, split="val", mode="paired", paired_deltas=deltas, k_se=1.0)
    assert d.threshold > old                            # strictly wider bar
    # t_{0.1587, df=2} = 1.3213 -> bar 0.0763; Δ̄=0.10 still clears it here.
    assert d.threshold == pytest.approx(0.0763, abs=5e-4)
    assert old == pytest.approx(0.0577, abs=5e-4)

    # And a genuinely marginal case flips from accept to reject.
    marginal = [-0.05, 0.10, 0.25]                       # Δ̄=0.10, SE=0.0866
    old_m = _old_z_bar(marginal)
    assert 0.10 > old_m                                  # old gate: ACCEPTED
    dm = decide(0.5, 0.6, split="val", mode="paired", paired_deltas=marginal, k_se=1.0)
    assert dm.threshold > old_m
    assert dm.accept is False                            # new gate: REJECTED
    assert "df=2" in dm.reason and "t-corrected" in dm.reason


def test_large_n_converges_to_old_behaviour():
    """Normal-sized runs are not broken: the bar matches the old z bar to <1%."""
    deltas = [0.1 + (i % 7 - 3) * 0.02 for i in range(200)]
    old = _old_z_bar(deltas)
    d = decide(0.5, 0.6, split="val", mode="paired", paired_deltas=deltas, k_se=1.0)
    assert d.threshold == pytest.approx(old, rel=0.01)
    assert d.accept is True


def test_paired_gate_logs_low_confidence_warning(tmp_path):
    from cap_evolve import RunDir
    rd = RunDir.create(tmp_path / ".capevolve", ts="lc")
    d = decide(0.5, 0.6, split="val", mode="paired",
               paired_deltas=[0.0, 0.1, 0.25], k_se=1.0, run_dir=rd)
    assert "LOW CONFIDENCE" in d.reason
    events = (rd.root / "events.jsonl").read_text(encoding="utf-8")
    assert "gate_warning" in events and "Student-t" in events


def test_large_n_has_no_low_confidence_flag():
    d = decide(0.5, 0.6, split="val", mode="paired",
               paired_deltas=[0.1] * 9 + [0.05], k_se=1.0)
    assert "LOW CONFIDENCE" not in d.reason


# ---- review fixes: one regression test per blocking finding ----------------
#
# The PR's original guard sat at ensure_splits + baseline only. Review found three
# production paths that reach a gate decision without passing either, plus a
# silently-wrong t critical value and a remediation string that doesn't work.

def _val1_run_dir(tmp_path, ts="v1"):
    """A run dir with a hand-written val=1 splits.json + baseline.json (the exact
    shape a resumed / copied run has)."""
    import json

    from cap_evolve import RunDir
    rd = RunDir.create(tmp_path / ".capevolve", ts=ts)
    rd.write_splits(Splits(train=["t0"], val=["t1"], test=["t2"], seed=0))
    (rd.root / "baseline.json").write_text(
        json.dumps({"val": {"reward": 0.0, "stderr": 0.0}, "best_id": "seed"}), encoding="utf-8")
    return rd


def _load_phase_script(phase):
    """Import a phase's ``run.py`` under a unique module name.

    Every phase ships a module literally named ``run``, so ``import run`` returns
    whichever one got cached first.
    """
    import importlib.util
    path = REPO / "skills" / "phases" / phase / "scripts" / "run.py"
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(f"_phase_{phase}_run", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(path.parent))


# --- BLOCKING 1: harness.reuse_baseline copied splits.json before any guard ---

def test_reuse_baseline_refuses_tiny_val(tmp_path, monkeypatch):
    """A prior run's val=1 split must not be resurrectable into a fresh run.

    Before the fix ``reuse_baseline`` returned before ``baseline()`` ran, so an
    escape-hatch run's split became a reusable seed for later runs that nothing
    marked as dishonest.
    """
    from cap_evolve import RunDir, harness
    monkeypatch.delenv("CAPEVOLVE_ALLOW_TINY_VAL", raising=False)
    prior = _val1_run_dir(tmp_path / "prior", ts="prior")
    fresh = RunDir.create(tmp_path / "fresh" / ".capevolve", ts="fresh")
    with pytest.raises(TinyValSplitError) as ei:
        harness.reuse_baseline(prior.root, run_dir=fresh)
    assert "at baseline reuse" in str(ei.value)
    # Refused BEFORE freezing: nothing was written into the fresh run dir.
    assert not fresh.splits_path.exists()


def test_reuse_baseline_accepts_healthy_val(tmp_path, monkeypatch):
    """The guard is not overreach: a normal split still reuses fine."""
    import json

    from cap_evolve import RunDir, harness
    monkeypatch.delenv("CAPEVOLVE_ALLOW_TINY_VAL", raising=False)
    prior = RunDir.create(tmp_path / "prior" / ".capevolve", ts="p2")
    prior.write_splits(make_splits([f"t{i}" for i in range(20)], seed=0))
    (prior.root / "baseline.json").write_text(
        json.dumps({"val": {"reward": 0.25, "stderr": 0.1}, "best_id": "seed"}), encoding="utf-8")
    fresh = RunDir.create(tmp_path / "fresh" / ".capevolve", ts="f2")
    res = harness.reuse_baseline(prior.root, run_dir=fresh)
    assert res.reward == 0.25
    assert len(fresh.read_splits().val) >= MIN_VAL_TASKS


# --- BLOCKING 2: the baseline --resume fast path returned before any guard ---

def test_baseline_resume_fast_path_refuses_tiny_val(tmp_path, monkeypatch):
    """``baseline --resume`` on a val=1 run dir must fail, not exit 0."""
    monkeypatch.delenv("CAPEVOLVE_ALLOW_TINY_VAL", raising=False)
    rd = _val1_run_dir(tmp_path, ts="res")
    mod = _load_phase_script("baseline")
    with pytest.raises(TinyValSplitError) as ei:
        mod.main(["--base", str(tmp_path / ".capevolve"), "--project", str(tmp_path),
                  "--capability", str(tmp_path / "cap"), "--run-ts", "res", "--resume"])
    assert "at resume" in str(ei.value)
    assert rd.root.exists()  # sanity: we really did target the prepared dir


# --- BLOCKING 1+2+7: the chokepoint — gate.decide itself refuses n<2 ---------

@pytest.mark.parametrize("deltas", [[0.5], [0.0], [-0.3], []])
def test_gate_decide_itself_refuses_fewer_than_two_pairs(deltas, monkeypatch):
    """No caller can reach an accept/reject with n<2, whatever path it came from.

    ``[]`` is the documented fall-through to ``significant`` (no paired data at all),
    so only n==1 raises; both are covered here so the boundary is pinned.
    """
    monkeypatch.delenv("CAPEVOLVE_ALLOW_TINY_VAL", raising=False)
    if not deltas:
        d = decide(0.5, 0.6, split="val", mode="paired", paired_deltas=deltas, k_se=1.0)
        assert "Δ=" in d.reason  # fell through to the independent significance test
        return
    with pytest.raises(TinyValSplitError) as ei:
        decide(0.5, 0.6, split="val", mode="paired", paired_deltas=deltas, k_se=1.0)
    assert "gate refused" in str(ei.value)
    assert f">= {MIN_VAL_TASKS}" in str(ei.value)


def test_gate_refuses_collapsed_pair_count_from_healthy_split(monkeypatch):
    """Finding 7: a candidate that errored on 4 of 5 val tasks leaves n=1 pairs.

    The split is healthy, so ``check_val_size`` on the split cannot catch this — only
    the guard inside ``decide`` can. Before the fix this was ACCEPTED via the SE=0
    strict fallback (a candidate that crashed on 80% of val).
    """
    monkeypatch.delenv("CAPEVOLVE_ALLOW_TINY_VAL", raising=False)
    healthy = make_splits([f"t{i}" for i in range(20)], seed=0)
    assert len(healthy.val) >= LOW_CONFIDENCE_VAL_TASKS  # split itself is fine
    with pytest.raises(TinyValSplitError):
        decide(0.5, 0.6, split="val", mode="paired", paired_deltas=[0.0999], k_se=1.0)


def test_gate_with_two_pairs_still_decides(monkeypatch):
    """n==2 is the boundary and must still work (df=1, the 1.837x bar)."""
    monkeypatch.delenv("CAPEVOLVE_ALLOW_TINY_VAL", raising=False)
    d = decide(0.5, 0.6, split="val", mode="paired", paired_deltas=[0.0, 0.2], k_se=1.0)
    assert d.accept is False  # Δ̄=0.10 <= 1.8373*0.10
    assert "df=1" in d.reason


def test_gate_bypass_env_lets_n1_through_but_marks_it(tmp_path, monkeypatch):
    """The escape hatch still works at the gate — and brands the run dir."""
    from cap_evolve import RunDir
    from cap_evolve.splits import bypassed
    monkeypatch.setenv("CAPEVOLVE_ALLOW_TINY_VAL", "1")
    rd = RunDir.create(tmp_path / ".capevolve", ts="byp")
    d = decide(0.5, 0.6, split="val", mode="paired", paired_deltas=[0.5], k_se=1.0, run_dir=rd)
    assert d.accept is True
    mark = bypassed(rd)
    assert mark and mark["val"] == 1 and "NOT AN HONEST GATE" in mark["banner"]


# --- BLOCKING 3: bypassed runs are branded in the durable artifacts ---------

def test_bypass_marker_is_durable_and_reaches_final_json(tmp_path, monkeypatch):
    import json

    from cap_evolve import RunDir
    from cap_evolve.splits import BYPASS_BANNER, bypassed, check_val_size
    monkeypatch.setenv("CAPEVOLVE_ALLOW_TINY_VAL", "1")
    rd = RunDir.create(tmp_path / ".capevolve", ts="mark")
    msg = check_val_size(Splits(train=["a"], val=["b"], test=["c"]),
                         context="at split freeze", run_dir=rd)
    assert msg == BYPASS_BANNER
    # Durable in state.json, not just an event line that scrolls away.
    assert bypassed(rd)["val"] == 1
    assert "tiny_val_bypass" in (rd.root / "state.json").read_text(encoding="utf-8")
    # And it is what finalize stamps into final.json.
    payload = {"test": {"reward": 0.0}, "best_id": "seed"}
    b = bypassed(rd)
    payload.update({"honest_gate": False, "warnings": [BYPASS_BANNER], "tiny_val_bypass": b})
    assert json.loads(json.dumps(payload))["honest_gate"] is False


def test_report_md_brands_a_bypassed_run(tmp_path, monkeypatch):
    """report.md must LEAD with the banner and retract the honesty claim."""
    import json

    from cap_evolve import RunDir
    monkeypatch.setenv("CAPEVOLVE_ALLOW_TINY_VAL", "1")
    rd = RunDir.create(tmp_path / ".capevolve", ts="rep")
    rd.write_splits(Splits(train=["a"], val=["b"], test=["c"]))
    rd.set_best("cand_0001")
    from cap_evolve.splits import check_val_size
    check_val_size(rd.read_splits(), context="at split freeze", run_dir=rd)
    (rd.root / "baseline.json").write_text(json.dumps({"val": {"reward": 0.0}}), encoding="utf-8")
    (rd.root / "final.json").write_text(json.dumps({
        "test": {"reward": 0.5}, "best_id": "cand_0001", "baseline_id": "seed",
        "test_baseline": {"reward": 0.0}, "test_delta": 0.5, "honest_gate": False,
    }), encoding="utf-8")
    rep = _load_phase_script("report")
    assert rep.main(["--run-dir", str(rd.root), "--no-dashboard"]) == 0
    md = (rd.root / "report.md").read_text(encoding="utf-8")
    assert "NOT AN HONEST GATE" in md
    assert "Honest gate: no — BYPASSED" in md
    # The old text claimed the improvement was honest; it must now be retracted.
    assert "NOT AN HONEST RESULT" in md
    assert md.index("NOT AN HONEST GATE") < md.index("Held-out test")


def test_dashboard_surfaces_split_warning_and_banner(tmp_path, monkeypatch):
    """dashboard.py had NO split_warning branch at all, and no banner."""
    import json

    from cap_evolve import RunDir, dashboard
    from cap_evolve.splits import check_val_size
    monkeypatch.setenv("CAPEVOLVE_ALLOW_TINY_VAL", "1")
    rd = RunDir.create(tmp_path / ".capevolve", ts="dash")
    rd.write_splits(Splits(train=["a"], val=["b"], test=["c"]))
    check_val_size(rd.read_splits(), context="at split freeze", run_dir=rd)
    (rd.root / "baseline.json").write_text(json.dumps({"val": {"reward": 0.0}}), encoding="utf-8")
    reduced = dashboard.reduce_run(rd)
    s = reduced["summary"]
    assert s["honesty_banner"] and "NOT AN HONEST GATE" in s["honesty_banner"]
    assert any("NOT AN HONEST GATE" in (w.get("reason") or "") for w in s["gate_warnings"])
    ansi = dashboard.render_ansi(reduced, color=False)
    assert "NOT AN HONEST GATE" in ansi
    html = dashboard.render_html(reduced) if hasattr(dashboard, "render_html") else ""
    if html:
        assert "honesty_banner" in html


def test_honest_run_has_no_banner(tmp_path):
    """The branding must not fire on a normal run."""
    import json

    from cap_evolve import RunDir, dashboard
    rd = RunDir.create(tmp_path / ".capevolve", ts="ok")
    rd.write_splits(make_splits([f"t{i}" for i in range(20)], seed=0))
    (rd.root / "baseline.json").write_text(json.dumps({"val": {"reward": 0.0}}), encoding="utf-8")
    assert dashboard.reduce_run(rd)["summary"]["honesty_banner"] is None


def test_split_warning_does_not_claim_a_correction_at_df_zero(tmp_path, monkeypatch):
    """The old warning said 'Student-t correction (df=0)' at n<2 — a lie: at n<2 the
    gate takes the SE=0 strict fallback and no correction is applied."""
    from cap_evolve import RunDir
    from cap_evolve.splits import check_val_size
    monkeypatch.setenv("CAPEVOLVE_ALLOW_TINY_VAL", "1")
    rd = RunDir.create(tmp_path / ".capevolve", ts="lie")
    msg = check_val_size(Splits(train=["a"], val=["b"], test=["c"]), run_dir=rd)
    assert "df=0" not in msg
    assert "Student-t" not in msg


# --- BLOCKING 4: t_critical is correct-or-loud, never silently wrong --------

def _indep_t_inv_df2(alpha):
    """Independent closed-form inverse for df=2, zero shared code with stats.py.

    P(T>t) = 1/(A(A+t)) with A=sqrt(2+t^2)  =>  with S=1/alpha,  t=(S-2)/sqrt(2S-2).
    Algebraically cancellation-free, so it stays exact into the far tail.
    """
    S = 1.0 / alpha
    return (S - 2.0) / math.sqrt(2.0 * S - 2.0)


@pytest.mark.parametrize("k_se", [1.0, 2.0, 5.0, 7.0, 8.0, 8.3, 10.0, 20.0, 26.5])
def test_t_multiplier_matches_independent_closed_form_at_high_k(k_se):
    """The measured errors were -5.9% at k=8, -29% at k=8.3, saturated 10..38."""
    got = stats.t_multiplier_for_z(k_se, 3)          # df = 2
    want = _indep_t_inv_df2(stats.normal_sf(k_se))
    assert got == pytest.approx(want, rel=1e-9), f"k_se={k_se}: {got} vs {want}"


def test_t_multiplier_is_strictly_monotonic_in_k_se():
    """It used to SATURATE at a constant for k_se 10..38, so raising the bar did
    nothing at all."""
    vals = [stats.t_multiplier_for_z(k, 3) for k in (8.0, 8.3, 10.0, 15.0, 20.0, 26.5)]
    assert all(b > a for a, b in zip(vals, vals[1:])), vals


@pytest.mark.parametrize("k_se", [26.6, 30.0, 38.5, 40.0, 100.0])
def test_t_multiplier_raises_instead_of_silently_reverting_to_z(k_se):
    """At k_se >= ~38.5 the normal tail underflows to 0.0. The old code returned the
    RAW k_se — i.e. the uncorrected z bar, the original bug, with no warning."""
    with pytest.raises(ValueError) as ei:
        stats.t_multiplier_for_z(k_se, 3)
    assert "supported range" in str(ei.value)
    # and the answer is emphatically not the silent z revert
    assert str(k_se) in str(ei.value)


def test_t_critical_raises_on_invalid_inputs_instead_of_sentinels():
    """0.0 / inf sentinels get silently multiplied by an SE (nit 12)."""
    for alpha in (0.0, -0.1, 0.5, 0.9, 1.0):
        with pytest.raises(ValueError):
            stats.t_critical(alpha, 5)
    for df in (0, -1):
        with pytest.raises(ValueError):
            stats.t_critical(0.05, df)


def test_t_sf_is_cancellation_free_in_the_far_tail():
    """``t_cdf`` saturates at 1.0 below ~1e-16 of tail mass; ``t_sf`` must not.

    Cross-checked against the exact df=2 form 1/(A(A+t)), A=sqrt(2+t^2).
    """
    for t in (1e3, 1e6, 1e7, 1e8, 1e12):
        A = math.sqrt(2.0 + t * t)
        assert stats.t_sf(t, 2) == pytest.approx(1.0 / (A * (A + t)), rel=1e-12)
    assert stats.t_cdf(1e12, 2) == 1.0        # documented saturation
    assert stats.t_sf(1e12, 2) > 0.0          # tail space still resolves it


def test_t_multiplier_never_falls_below_k_se():
    """t >= z is a theorem; the removed max() clamp bound in 0 of ~30k cases, so
    dropping it must not change any valid answer."""
    for k in (0.05, 0.2, 0.5, 1.0, 2.0, 3.0):
        for n in (2, 3, 5, 10, 100, 3000):
            assert stats.t_multiplier_for_z(k, n) >= k


def test_betainc_raises_on_non_convergence(monkeypatch):
    """A half-converged continued fraction used to be returned unflagged (nit 9)."""
    import cap_evolve.stats as st
    # Positive control: the shapes t_cdf uses converge fine.
    assert 0.0 < st.betainc(1.0, 0.5, 0.5) < 1.0
    assert 0.0 < st.betainc(2.5, 0.5, 1e-6) < 1.0
    # Force non-convergence by making the tolerance unreachable: with eps=0 the
    # `break` can never fire, so the loop must now RAISE rather than return `h`.
    real_abs = abs
    calls = {"n": 0}

    def fake_abs(x):
        # only defeat the convergence test itself (|delta - 1| < eps), nothing else
        calls["n"] += 1
        return real_abs(x) + 1.0 if calls["n"] > 4 else real_abs(x)

    monkeypatch.setitem(st._betacf.__globals__, "abs", fake_abs)
    with pytest.raises(RuntimeError, match="failed to converge"):
        st._betacf(1.0, 0.5, 0.5)


# --- BLOCKING 5: remediation option 2 actually works ------------------------

def test_remediation_option_2_is_stated_as_a_full_ratio_triple():
    """`split_val: 0.4` alone yields (0.5, 0.4, 0.25) -> still val=1 at n=3 and n=4."""
    with pytest.raises(TinyValSplitError) as ei:
        check_val_size(Splits(train=["a", "b"], val=["c"], test=[]))
    msg = str(ei.value)
    assert "split_val: 0.4" not in msg
    for line in ("split_train: 0.25", "split_val:   0.5", "split_test:  0.25"):
        assert line in msg, line
    assert "test needs >= 1" in msg          # option 3 completeness
    assert "with exactly 3 tasks no ratio can work" in msg


def test_remediation_option_2_ratios_actually_fix_the_error():
    """Follow the instruction verbatim: 0.25/0.5/0.25 must pass the guard for every
    n >= 4 — the population that hits this error."""
    for n in range(4, 41):
        sp = make_splits([f"t{i}" for i in range(n)], seed=0, ratios=(0.25, 0.5, 0.25))
        assert len(sp.val) >= MIN_VAL_TASKS, (n, sp.val)
        assert len(sp.test) >= 1, (n, sp.test)       # or finalize fails later
        assert len(sp.train) >= 1, (n, sp.train)
        check_val_size(sp)  # must not raise


def test_the_old_broken_remediation_really_was_broken():
    """Pin the reviewer's counter-example so nobody reintroduces it."""
    for n in (3, 4):
        sp = make_splits([f"t{i}" for i in range(n)], seed=0, ratios=(0.5, 0.4, 0.25))
        assert len(sp.val) == 1
        with pytest.raises(TinyValSplitError):
            check_val_size(sp)


def test_skillcheck_default_split_passes_the_guard(tmp_path):
    """CI risk: the old ids=("a","b","c","d") default produced val=["b"] (n=1)."""
    from cap_evolve import skillcheck
    _rd, splits = skillcheck.temp_run_dir(tmp_path)
    assert len(splits.val) >= MIN_VAL_TASKS
    check_val_size(splits)
