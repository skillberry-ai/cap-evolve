"""The never-delete-a-needed-rule invariant is reported, not merely documented.

`docs/ARCHITECTURE.md` states prompt edits must "change / consolidate / add, don't
delete". Before #327 that was prose only: `validate()` asserted non-emptiness, so an
`op: "set"` replacing a whole policy with one line validated `ok`. These tests pin the
constraint-line accounting that now surfaces such an edit as a warning (never a hard
failure — a legitimate consolidation trips it too).
"""

import importlib.util
from pathlib import Path

import pytest

ABSTRACT = (Path(__file__).resolve().parents[2] / "skills" / "capabilities"
            / "system-prompt" / "scripts" / "abstract.py")

POLICY = (
    "# Refund policy\n"
    "\n"
    "Require a manager code before any refund.\n"
    "Confirm before any destructive action.\n"
    "State the record ID in every reply.\n"
    "---\n"
)


@pytest.fixture(scope="module")
def sp():
    spec = importlib.util.spec_from_file_location("sp_abstract_rules", ABSTRACT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_rule_lines_ignores_structure_and_counts_rules(sp):
    """Headings, fences and rules structure a prompt; only the rest can carry a rule."""
    assert sp.rule_lines(POLICY) == 3
    assert sp.rule_lines("# Title\n\n```\ncode\n```\n===\n") == 1  # only the fenced body line
    assert sp.rule_lines("") == 0


def test_set_that_wipes_the_policy_is_flagged(sp, tmp_path):
    """The edit the invariant exists to catch: a whole-file replacement losing rules."""
    (tmp_path / "prompt.txt").write_text(POLICY, encoding="utf-8")
    rep = sp.apply(tmp_path, [{"file": "prompt.txt", "op": "set", "text": "Be helpful.\n"}])
    assert rep["changed"] == ["prompt.txt"]
    assert len(rep["warnings"]) == 1
    assert "3 -> 1" in rep["warnings"][0]
    # Still a warning, not a failure — the candidate remains valid and evaluable.
    assert sp.validate(tmp_path)["ok"] is True


def test_additive_and_consolidating_edits_do_not_warn(sp, tmp_path):
    """An add keeps every rule; a merge of two lines into one keeps every constraint."""
    (tmp_path / "prompt.txt").write_text(POLICY, encoding="utf-8")
    add = sp.apply(tmp_path, [{"file": "prompt.txt", "op": "append", "text": "Cite sources.\n"}])
    assert add["warnings"] == []
    merged = POLICY.replace(
        "Require a manager code before any refund.\nConfirm before any destructive action.\n",
        "Require a manager code before any refund, and confirm before any destructive action.\n",
    )
    # A real consolidation does drop a line, so it warns too — the warning asks for a
    # justification, it cannot distinguish a merge from a loss.
    con = sp.apply(tmp_path, [{"file": "prompt.txt", "op": "set", "text": merged}])
    assert con["warnings"], "a consolidation is flagged for justification, not silently accepted"


def test_validate_reports_stats_and_always_carries_warnings(sp, tmp_path):
    """`stats` turns 'the preamble is too long' into a number; `warnings` never KeyErrors."""
    (tmp_path / "prompt.txt").write_text(POLICY, encoding="utf-8")
    v = sp.validate(tmp_path)
    assert v["warnings"] == []
    assert v["stats"]["prompt.txt"]["rule_lines"] == 3
    assert v["stats"]["prompt.txt"]["lines"] == 6
    assert sp.validate(tmp_path / "missing")["warnings"] == []  # empty-seed branch


def test_validate_against_a_baseline_sees_the_drop(sp, tmp_path):
    """The agent-edit path: compare the candidate to the parent it was derived from."""
    (tmp_path / "prompt.txt").write_text("Be helpful.\n", encoding="utf-8")
    assert sp.validate(tmp_path, baseline={"prompt.txt": POLICY})["warnings"]
    assert sp.validate(tmp_path, baseline={"prompt.txt": "Be helpful.\n"})["warnings"] == []
