"""The optimizer brief must not claim it is re-scored on the same val tasks in pooled mode."""
from types import SimpleNamespace

from cap_evolve import harness


def test_pooled_brief_says_tasks_are_unseen():
    cur = SimpleNamespace(reward=0.5)
    pooled = harness._algorithm_brief(cur, "hill-climb", "pooled")
    assert "SAME held-out val" not in pooled
    assert "NOT seen" in pooled


def test_legacy_brief_unchanged():
    cur = SimpleNamespace(reward=0.5)
    legacy = harness._algorithm_brief(cur, "hill-climb")
    assert "re-scored on the SAME held-out val tasks" in legacy
    assert legacy == harness._algorithm_brief(cur, "hill-climb", "")
