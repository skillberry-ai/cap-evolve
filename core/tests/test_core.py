"""Tests for the honest-evaluation substrate.

These encode the non-negotiable guarantees: deterministic splits, a sealed test
set, the significance gate, pass^k math, and rejected-memory rendering.
"""

import math

import pytest

from cap_evolve import (
    RejectedMemory,
    RunDir,
    TestSealError,
    TrainGateError,
    decide,
    make_splits,
    pass_k,
)
from cap_evolve import stats
from cap_evolve.gate import decide as gate_decide


# ---- splits ---------------------------------------------------------------

def test_splits_deterministic():
    ids = [f"t{i}" for i in range(20)]
    a = make_splits(ids, seed=42)
    b = make_splits(ids, seed=42)
    assert a.to_dict() == b.to_dict()


def test_splits_partition_is_complete_and_disjoint():
    ids = [f"t{i}" for i in range(20)]
    s = make_splits(ids, seed=1, ratios=(0.5, 0.25, 0.25))
    alls = s.train + s.val + s.test
    assert sorted(alls) == sorted(ids)            # complete
    assert len(set(alls)) == len(ids)             # disjoint


def test_different_seed_different_split():
    ids = [f"t{i}" for i in range(50)]
    assert make_splits(ids, seed=1).to_dict() != make_splits(ids, seed=2).to_dict()


# ---- test seal ------------------------------------------------------------

def test_test_split_sealed_after_one_use(tmp_path):
    rd = RunDir.create(tmp_path)
    rd.write_splits(make_splits([f"t{i}" for i in range(8)], seed=0))
    rd.consume_test()                  # first finalize: OK
    with pytest.raises(TestSealError):
        rd.consume_test()              # second finalize: refused


# ---- gate -----------------------------------------------------------------

def test_gate_rejects_train_split():
    with pytest.raises(TrainGateError):
        decide(0.5, 0.9, split="train")


def test_significance_gate_rejects_noise():
    # tiny improvement, large SE -> not significant
    d = decide(0.50, 0.52, split="val", mode="significant",
               k_se=1.0, candidate_stderr=0.1, current_stderr=0.1)
    assert d.accept is False


def test_significance_gate_accepts_real_gain():
    d = decide(0.50, 0.80, split="val", mode="significant",
               k_se=1.0, candidate_stderr=0.02, current_stderr=0.02)
    assert d.accept is True


def test_strict_gate_accepts_any_improvement():
    assert decide(0.5, 0.5001, split="val", mode="strict").accept is True
    assert decide(0.5, 0.5, split="val", mode="strict").accept is False


def test_simplicity_tiebreak_prefers_smaller_on_tie():
    d = decide(0.5, 0.5, split="val", mode="simplicity_tiebreak",
               candidate_size=10, current_size=20)
    assert d.accept is True


# ---- stats ----------------------------------------------------------------

def test_pass_k_all_pass():
    assert pass_k([1.0, 1.0, 1.0], 2) == 1.0


def test_pass_k_none_pass():
    assert pass_k([0.0, 0.0, 0.0], 1) == 0.0


def test_pass_k_partial():
    # 2 of 4 pass; P(both of 2 drawn pass) = C(2,2)/C(4,2) = 1/6
    assert math.isclose(pass_k([1, 1, 0, 0], 2), 1 / 6, rel_tol=1e-9)


def test_pass_k_k_gt_n_is_zero():
    assert pass_k([1.0], 2) == 0.0


def test_pass_at_k_capability_vs_reliability():
    from cap_evolve import pass_at_k
    # 2 of 4 pass: reliability(pass^2)=1/6, capability(pass@2)=1 - C(2,2)/C(4,2)=5/6
    assert math.isclose(pass_at_k([1, 1, 0, 0], 2), 5 / 6, rel_tol=1e-9)
    assert pass_at_k([0, 0, 0], 2) == 0.0
    assert pass_at_k([1, 0], 2) == 1.0


def test_bootstrap_ci_is_deterministic_and_bracketed():
    from cap_evolve import bootstrap_ci
    lo, hi = bootstrap_ci([1, 1, 1, 0, 0], seed=0)
    assert 0.0 <= lo <= hi <= 1.0
    assert bootstrap_ci([1, 1, 1, 0, 0], seed=0) == bootstrap_ci([1, 1, 1, 0, 0], seed=0)


def test_combined_stderr_zero_for_single_certain_task():
    assert stats.combined_stderr([1.0], [0.0]) == 0.0


# ---- rejected memory ------------------------------------------------------

def test_rejected_memory_roundtrip_and_render(tmp_path):
    rm = RejectedMemory(tmp_path / "rejected.jsonl")
    rm.add("c1", "added verbose preamble", "Δ<=0 on val", val=0.41)
    rm.add("c2", "removed the schema hint", "regressed val", val=0.30)
    assert len(rm.entries()) == 2
    rendered = rm.render()
    assert "added verbose preamble" in rendered
    assert "do NOT re-propose" in rendered.lower() or "do not" in rendered.lower()
