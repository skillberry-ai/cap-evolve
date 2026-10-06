"""Unit tests for cap_evolve.model_routing (issue #665 ws5).

Covers the fallback chain (explicit role override -> optimizer_model -> hard error),
and the ModelSelection telemetry record/emission via RunDir.log_event.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

from cap_evolve.model_routing import (  # noqa: E402
    ModelRoutingError,
    ModelSelection,
    record_model_selection,
    resolve_model,
)
from cap_evolve.rundir import RunDir  # noqa: E402


def test_no_model_routing_block_falls_back_to_optimizer_model():
    """Backward compat: a spec with no `model_routing` key resolves every role to
    `optimizer_model`, exactly as before this feature existed."""
    spec = {"optimizer_model": "claude-opus-4"}
    for role in ("plan", "root_cause", "propose", "implement",
                 "evaluation_analysis", "merge", "synthesis"):
        assert resolve_model(role, spec) == "claude-opus-4"


def test_explicit_role_override_wins_over_optimizer_model():
    spec = {"optimizer_model": "claude-opus-4",
            "model_routing": {"root_cause": "claude-sonnet-5"}}
    assert resolve_model("root_cause", spec) == "claude-sonnet-5"
    # unrouted role still falls back to the default
    assert resolve_model("implement", spec) == "claude-opus-4"


def test_missing_both_raises():
    with pytest.raises(ModelRoutingError):
        resolve_model("propose", {})


def test_empty_model_routing_block_is_same_as_absent():
    spec = {"optimizer_model": "claude-opus-4", "model_routing": {}}
    assert resolve_model("plan", spec) == "claude-opus-4"


def test_model_selection_record_shape():
    sel = ModelSelection(role="root_cause", model="claude-opus-4", rationale="judgment step")
    fields = sel.to_event_fields()
    assert fields["role"] == "root_cause"
    assert fields["model"] == "claude-opus-4"
    assert fields["rationale"] == "judgment step"
    assert isinstance(fields["timestamp"], float)


def test_model_selection_without_rationale_omits_the_field():
    sel = ModelSelection(role="plan", model="claude-haiku-4")
    assert "rationale" not in sel.to_event_fields()


def test_record_model_selection_appends_to_events_jsonl(tmp_path):
    rd = RunDir.create(tmp_path)
    record_model_selection(rd, "merge", "claude-opus-4", rationale="merge-conflict reasoning")
    lines = rd.events_path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(l) for l in lines]
    sel_events = [e for e in events if e["kind"] == "model_selection"]
    assert len(sel_events) == 1
    ev = sel_events[0]
    assert ev["role"] == "merge"
    assert ev["model"] == "claude-opus-4"
    assert ev["rationale"] == "merge-conflict reasoning"
    assert "timestamp" in ev and "t" in ev  # t is RunDir.log_event's own clock
