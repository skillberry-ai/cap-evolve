"""The rfe_creator adapter's reward composition, pinned without a real pipeline run.

The judges are rfe-creator's own (its eval.yaml / eval-initiative.yaml); the adapter only
turns their verdicts into one reward: ``gate x check penalty x quality``. Pinned here:
the quality judge is normalized over the range the config DECLARES (the 1-5 holistic judge
through the convex SCORE_MAP, a 0-10 per-criterion judge linearly), rfe-creator's newer
checks (first_review_expectation, evidence_fidelity) are key checks, and the diagnostic
self_score_calibration judge stays out of the reward and the optimizer's feedback.

`core[dev]` ships no PyYAML and a test that skips for a missing dep is worse than none, so
when `yaml` is absent a JSON-backed stand-in is installed before the adapter is imported
(JSON is valid YAML; no fixture here goes through it).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ADAPTER = REPO / "benchmarks" / "rfe_creator" / "template" / "adapter.py"

try:
    import yaml  # noqa: F401
except ImportError:  # pragma: no cover - depends on the environment
    _stub = types.ModuleType("yaml")
    _stub.safe_load = lambda s: json.loads(s.read() if hasattr(s, "read") else s)
    _stub.safe_dump = lambda obj, *a, **k: json.dumps(obj)
    _stub.YAMLError = ValueError
    sys.modules["yaml"] = _stub


def _load_adapter():
    spec = importlib.util.spec_from_file_location("rfe_creator_adapter_under_test", ADAPTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


A = _load_adapter()

NEW_CFG = {"judges": [{"name": "files_exist", "check": "x"},
                      {"name": "rfe_quality", "prompt": "p", "score_range": [0, 10]},
                      {"name": "revision_quality", "prompt": "p", "score_range": [1, 5]},
                      {"name": "self_score_calibration", "prompt": "p", "score_range": [0, 5]}]}


def test_judge_ranges_from_config():
    assert A.judge_ranges(NEW_CFG) == {"rfe_quality": (0.0, 10.0), "revision_quality": (1.0, 5.0),
                                       "self_score_calibration": (0.0, 5.0)}


@pytest.mark.parametrize("value, rng, want", [
    (8, (0.0, 10.0), 0.8),          # per-criterion 0-10 judge: linear
    (4, (1.0, 5.0), 0.6),           # holistic 1-5 judge: convex SCORE_MAP
    (4, None, 0.6),                 # a config that declares no range: the 1-5 default
    (True, None, 1.0), (False, (0.0, 10.0), 0.0),
])
def test_as01(value, rng, want):
    assert A._as01({"value": value}, rng) == pytest.approx(want)


def test_quality_uses_declared_ranges():
    pj = {"rfe_quality": {"value": 8}, "revision_quality": {"value": 5}}
    reward, comp = A.compose_reward(pj, "rfe_quality", {}, A.judge_ranges(NEW_CFG))
    assert comp["quality"] == pytest.approx((3 * 0.8 + 1.0) / 4) and reward == pytest.approx(0.85)
    # the same verdicts read against today's 1-5 config would clamp 8 to a 5
    _, old = A.compose_reward(pj, "rfe_quality", {})
    assert old["quality"] == pytest.approx(1.0)


def test_new_rfe_creator_checks_are_key_penalties():
    pj = {"rfe_quality": {"value": 10}, "revision_quality": {"value": 5},
          "evidence_fidelity": {"value": False}, "first_review_expectation": {"value": False}}
    reward, comp = A.compose_reward(pj, "rfe_quality", {}, A.judge_ranges(NEW_CFG))
    assert sorted(comp["failed_checks"]) == ["evidence_fidelity", "first_review_expectation"]
    assert reward == pytest.approx(0.85 * 0.85)


def test_older_configs_without_the_new_checks_are_unaffected():
    pj = {"rfe_quality": {"value": 5}, "revision_quality": {"value": 5}}
    reward, comp = A.compose_reward(pj, "rfe_quality", {})
    assert reward == pytest.approx(1.0) and comp["failed_checks"] == []


def test_calibration_is_never_in_the_reward_or_the_feedback():
    base = {"rfe_quality": {"value": 9, "rationale": "q"}, "revision_quality": {"value": 5}}
    low = {**base, "self_score_calibration": {"value": 0, "rationale": "SECRET-CALIBRATION"}}
    ranges = A.judge_ranges(NEW_CFG)
    r1, comp = A.compose_reward(base, "rfe_quality", {}, ranges)
    r2, _ = A.compose_reward(low, "rfe_quality", {}, ranges)
    assert r1 == r2
    fb = A.format_feedback(low, "rfe_quality", {}, comp, ranges)
    assert "SECRET-CALIBRATION" not in fb and "self_score_calibration" not in fb


def test_feedback_labels_use_the_declared_range_and_show_sampling():
    pj = {"rfe_quality": {"value": 8, "rationale": "q",
                          "stability": {"samples": 3, "values": [8, 8, 9]}},
          "evidence_fidelity": {"value": True, "rationale": "none", "stability": {"samples": 3}}}
    _, comp = A.compose_reward(pj, "rfe_quality", {}, A.judge_ranges(NEW_CFG))
    fb = A.format_feedback(pj, "rfe_quality", {}, comp, A.judge_ranges(NEW_CFG))
    assert "### rfe_quality — 8/10 (judge sampled 3x)" in fb
    assert "### evidence_fidelity — PASS (judge sampled 3x)" in fb
    assert fb.count("### evidence_fidelity") == 1
