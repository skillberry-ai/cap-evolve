import inspect
from cap_evolve import harness


def test_hill_climb_loop_accepts_target_params():
    sig = inspect.signature(harness.hill_climb_loop)
    assert "target_model" in sig.parameters
    assert "target_profile_file" in sig.parameters
