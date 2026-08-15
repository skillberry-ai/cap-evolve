"""Plateau detection: escalates on a real plateau, stays quiet under noise."""

import pytest

from cap_evolve.convergence import ConvergenceConfig, Observation, assess


def _obs(rewards, *, stderr=0.0, accepted=False):
    return [Observation(f"c{i}", r, accepted, stderr) for i, r in enumerate(rewards)]


def test_below_min_observations_is_ok(tmp_path=None):
    sig = assess(_obs([0.5, 0.5]), baseline=0.5)
    assert sig.level == "ok" and sig.consecutive_non_improving == 0
    assert "statistically available" in sig.advice
    assert sig.to_dict()["n_observations"] == 2


def test_monotonic_improvement_is_ok():
    sig = assess(_obs([0.55, 0.60, 0.65, 0.70, 0.75], accepted=True), baseline=0.50)
    assert sig.level == "ok" and sig.consecutive_non_improving == 0
    assert sig.velocity > 0


@pytest.mark.parametrize("n,level", [(4, "warn"), (5, "paradigm_shift"),
                                     (7, "paradigm_shift"), (8, "stop"), (12, "stop")])
def test_flat_run_escalates_at_the_right_counts(n, level):
    sig = assess(_obs([0.50] * n), baseline=0.50)
    assert sig.level == level
    assert sig.consecutive_non_improving == n
    assert sig.advice  # actionable text, injectable verbatim


def test_minimize_direction_inverts():
    falling = _obs([0.9, 0.8, 0.7, 0.6])
    assert assess(falling, baseline=1.0, direction="minimize").level == "ok"
    assert assess(falling, baseline=1.0, direction="maximize").level == "warn"
    with pytest.raises(ValueError):
        assess(falling, baseline=1.0, direction="sideways")


def test_noisy_but_real_improvement_is_not_a_plateau():
    """The reason this port beats the original: Arbor compares raw numbers and would
    call a genuinely climbing-but-noisy run a plateau."""
    sig = assess(_obs([0.55, 0.60, 0.65, 0.70, 0.75], stderr=0.02), baseline=0.50)
    assert sig.level == "ok", sig.advice
    assert sig.consecutive_non_improving == 0


def test_tiny_gain_under_high_noise_is_a_plateau():
    """The other half of variance-awareness: delta > threshold is NOT enough."""
    rewards = [0.501, 0.502, 0.503, 0.504]
    assert assess(_obs(rewards, stderr=0.0), baseline=0.500).level == "ok"
    assert assess(_obs(rewards, stderr=0.05), baseline=0.500).level == "warn"


def test_pure_function_same_input_same_output():
    obs = _obs([0.5, 0.5, 0.6, 0.5, 0.5])
    a = assess(obs, baseline=0.5).to_dict()
    b = assess(list(obs), baseline=0.5).to_dict()
    assert a == b
    # No hidden accumulation: repeated calls do not drift.
    assert assess(obs, baseline=0.5).to_dict() == a


def test_improvement_resets_the_streak():
    cfg = ConvergenceConfig()
    flat_then_jump = _obs([0.5, 0.5, 0.5, 0.5, 0.5, 0.9])
    assert assess(flat_then_jump[:5], baseline=0.5, config=cfg).level == "paradigm_shift"
    sig = assess(flat_then_jump, baseline=0.5, config=cfg)
    assert sig.level == "ok" and sig.consecutive_non_improving == 0


def test_config_is_frozen():
    with pytest.raises(Exception):
        ConvergenceConfig().warn_after = 99
