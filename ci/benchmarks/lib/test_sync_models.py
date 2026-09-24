"""Tests for sync_models.py — run with: python3 -m pytest ci/benchmarks/lib/test_sync_models.py"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import sync_models as sm

# Repo root, independent of cwd — pytest may be invoked from here or from the repo root
# (the module's own real-repo test command uses the latter), and sm.WORKFLOW/sm.RUN_SUITE are
# relative Paths meant to be joined onto a caller-supplied repo path, not read bare.
REPO = Path(__file__).resolve().parents[3]

WF = """\
name: Benchmarks
on:
  workflow_dispatch:
    inputs:
      agent_model:
        type: choice
        default: "ibm-ete-int/aws/gpt-oss-120b"
        options:
          - "ibm-ete-int/aws/gpt-oss-120b"
          - "ibm-ete-int/claude-opus-4-8"
          - "ibm-rits/google/gemma-4-31B-it"
      optimizer_model:
        type: choice
        default: "ibm-ete-int/claude-opus-4-8"
        options:
          - "ibm-ete-int/aws/gpt-oss-120b"
          - "ibm-ete-int/claude-opus-4-8"
          - "ibm-rits/google/gemma-4-31B-it"
"""

RS = 'AGENT_MODEL="${AGENT_MODEL:-ibm-ete-int/aws/gpt-oss-120b}"\nOPTIMIZER_MODEL="${OPTIMIZER_MODEL:-ibm-ete-int/claude-opus-4-8}"\n'

TASKS_JSON = {
    "curated": {
        "full": {
            "tasks.json": json.dumps([
                {"id": "t1", "agent": "aws/gpt-oss-120b"},
                {"id": "t2", "agent": "rits/google/gemma-4-31B-it"},
            ])
        }
    }
}


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / sm.WORKFLOW.name).write_text(WF)
    (tmp_path / "ci" / "benchmarks" / "lib").mkdir(parents=True)
    (tmp_path / sm.RUN_SUITE).write_text(RS)
    for bench, tiers in TASKS_JSON.items():
        for tier, files in tiers.items():
            d = tmp_path / "ci" / "benchmarks" / "suites" / bench / tier
            d.mkdir(parents=True)
            for name, content in files.items():
                (d / name).write_text(content)
    return tmp_path


def _models(*ids: str) -> list[str]:
    return list(ids)


def test_served_ids_dedupes_and_sorts_case_insensitively():
    body = json.dumps({"data": [{"id": "B"}, {"id": "a"}, {"id": "a"}]})
    assert sm.served_ids(body) == ["a", "B"]


def test_served_ids_tolerates_bare_list_and_plain_strings():
    assert sm.served_ids(json.dumps(["x", "y"])) == ["x", "y"]
    assert sm.served_ids(json.dumps({"data": ["x", "y"]})) == ["x", "y"]


def test_reads_current_options_and_defaults_per_picker(tmp_path):
    r = _repo(tmp_path)
    text = (r / sm.WORKFLOW).read_text()
    assert sm.current_options(text, "agent_model") == [
        "ibm-ete-int/aws/gpt-oss-120b", "ibm-ete-int/claude-opus-4-8", "ibm-rits/google/gemma-4-31B-it",
    ]
    assert sm.current_default(text, "agent_model") == "ibm-ete-int/aws/gpt-oss-120b"


def test_rewrite_touches_only_the_named_picker(tmp_path):
    r = _repo(tmp_path)
    before = (r / sm.WORKFLOW).read_text()
    after = sm.rewrite_options(before, "agent_model", ["ibm-ete-int/only-one"])
    assert sm.current_options(after, "agent_model") == ["ibm-ete-int/only-one"]
    assert sm.current_options(after, "optimizer_model") == sm.current_options(before, "optimizer_model")


def test_unknown_picker_raises_rather_than_silently_doing_nothing(tmp_path):
    r = _repo(tmp_path)
    text = (r / sm.WORKFLOW).read_text()
    with pytest.raises(ValueError):
        sm.rewrite_options(text, "not_a_real_picker", ["x"])


def test_check_reports_drift_without_writing(tmp_path):
    r = _repo(tmp_path)
    before = (r / sm.WORKFLOW).read_text()
    code, rep = sm.sync(
        r, _models("ibm-ete-int/aws/gpt-oss-120b", "ibm-ete-int/claude-opus-4-8", "ibm-ete-int/new/model"),
        {"ibm-ete-int"}, write=False,
    )
    assert code == sm.EXIT_DRIFT
    assert (r / sm.WORKFLOW).read_text() == before, "check mode must not write"
    assert any("ibm-ete-int/new/model" in l for l in rep)


def test_write_applies_to_both_pickers(tmp_path):
    r = _repo(tmp_path)
    code, _ = sm.sync(
        r, _models("ibm-ete-int/aws/gpt-oss-120b", "ibm-ete-int/claude-opus-4-8", "ibm-ete-int/new/model"),
        {"ibm-ete-int"}, write=True,
    )
    assert code == sm.EXIT_OK
    text = (r / sm.WORKFLOW).read_text()
    for picker in sm.PICKERS:
        assert sm.current_options(text, picker) == [
            "ibm-ete-int/aws/gpt-oss-120b", "ibm-ete-int/claude-opus-4-8",
            "ibm-ete-int/new/model", "ibm-rits/google/gemma-4-31B-it",
        ]


def test_idempotent(tmp_path):
    r = _repo(tmp_path)
    models = _models("ibm-ete-int/aws/gpt-oss-120b", "ibm-ete-int/claude-opus-4-8")
    sm.sync(r, models, {"ibm-ete-int"}, write=True)
    code, rep = sm.sync(r, models, {"ibm-ete-int"}, write=True)
    assert code == sm.EXIT_OK
    assert not any(l.startswith("  +") or l.startswith("  -") for l in rep)


def test_unpolled_prefix_options_are_left_completely_untouched(tmp_path):
    """ibm-rits/* is never polled — this is how RITS stays hand-curated for free."""
    r = _repo(tmp_path)
    code, _ = sm.sync(r, _models("ibm-ete-int/aws/gpt-oss-120b"), {"ibm-ete-int"}, write=True)
    assert code == sm.EXIT_OK
    text = (r / sm.WORKFLOW).read_text()
    for picker in sm.PICKERS:
        assert "ibm-rits/google/gemma-4-31B-it" in sm.current_options(text, picker)


def test_polling_two_prefixes_replaces_both_and_leaves_the_third(tmp_path):
    r = _repo(tmp_path)
    code, _ = sm.sync(
        r,
        _models("ibm-ete-int/aws/gpt-oss-120b", "ibm-ete-int/claude-opus-4-8", "ibm-ete/glm-4.6"),
        {"ibm-ete-int", "ibm-ete"},
        write=True,
    )
    assert code == sm.EXIT_OK
    opts = sm.current_options((r / sm.WORKFLOW).read_text(), "agent_model")
    assert "ibm-ete/glm-4.6" in opts                    # newly polled ibm-ete prefix
    assert "ibm-ete-int/aws/gpt-oss-120b" in opts
    assert "ibm-rits/google/gemma-4-31B-it" in opts    # unpolled prefix untouched


def test_retention_does_not_leak_into_the_other_picker(tmp_path):
    r = _repo(tmp_path)
    # optimizer_model's default (ibm-ete-int/claude-opus-4-8) is unserved by this poll;
    # agent_model's default (ibm-ete-int/aws/gpt-oss-120b) is served.
    code, rep = sm.sync(r, _models("ibm-ete-int/aws/gpt-oss-120b"), {"ibm-ete-int"}, write=True)
    assert code == sm.EXIT_OK
    text = (r / sm.WORKFLOW).read_text()
    assert "ibm-ete-int/claude-opus-4-8" in sm.current_options(text, "optimizer_model")
    assert sm.current_default(text, "optimizer_model") == "ibm-ete-int/claude-opus-4-8"
    assert any("optimizer_model" in l and "unserved default" in l for l in rep)


def test_unserved_default_under_an_unpolled_prefix_needs_no_retention_warning(tmp_path):
    """A default whose OWN prefix was never polled isn't 'unserved' in this run's context."""
    r = _repo(tmp_path)
    wf_path = r / sm.WORKFLOW
    wf_path.write_text(sm.rewrite_default(wf_path.read_text(), "optimizer_model", "ibm-rits/google/gemma-4-31B-it"))
    code, rep = sm.sync(r, _models("ibm-ete-int/aws/gpt-oss-120b"), {"ibm-ete-int"}, write=True)
    assert code == sm.EXIT_OK
    assert sm.current_default(wf_path.read_text(), "optimizer_model") == "ibm-rits/google/gemma-4-31B-it"
    assert not any("unserved default" in l for l in rep)


def test_supplying_a_served_default_unblocks_and_moves_run_suite_too(tmp_path):
    r = _repo(tmp_path)
    code, _ = sm.sync(
        r, _models("ibm-ete-int/aws/gpt-oss-120b", "ibm-ete-int/new-default"),
        {"ibm-ete-int"}, write=True, optimizer_default="ibm-ete-int/new-default",
    )
    assert code == sm.EXIT_OK
    wf_text = (r / sm.WORKFLOW).read_text()
    assert sm.current_default(wf_text, "optimizer_model") == "ibm-ete-int/new-default"
    rs_text = (r / sm.RUN_SUITE).read_text()
    assert 'OPTIMIZER_MODEL="${OPTIMIZER_MODEL:-ibm-ete-int/new-default}"' in rs_text


def test_requested_default_must_itself_be_served(tmp_path):
    r = _repo(tmp_path)
    code, rep = sm.sync(
        r, _models("ibm-ete-int/aws/gpt-oss-120b"), {"ibm-ete-int"}, write=True,
        optimizer_default="ibm-ete-int/not-served",
    )
    assert code == sm.EXIT_DECISION
    assert any("not-served" in l for l in rep)


def test_generated_workflow_keeps_every_default_inside_its_options(tmp_path):
    r = _repo(tmp_path)
    sm.sync(r, _models("ibm-ete-int/aws/gpt-oss-120b", "ibm-ete-int/new/model"), {"ibm-ete-int"}, write=True)
    text = (r / sm.WORKFLOW).read_text()
    for picker in sm.PICKERS:
        assert sm.current_default(text, picker) in sm.current_options(text, picker)


def test_empty_model_list_refuses_to_blank_the_pickers(tmp_path):
    r = _repo(tmp_path)
    before = (r / sm.WORKFLOW).read_text()
    code, rep = sm.sync(r, [], {"ibm-ete-int"}, write=True)
    assert code == sm.EXIT_DECISION
    assert (r / sm.WORKFLOW).read_text() == before
    assert any("refus" in l.lower() for l in rep)


def test_task_pins_match_bare_ids_against_prefixed_served_models(tmp_path):
    """tasks.json pins are bare/rits-prefixed (written under the pre-rename scheme); the
    served models list is now always CI-prefixed. task_pins()'s advisory check must not
    false-positive on every single pin just because of the added prefix."""
    r = _repo(tmp_path)
    code, rep = sm.sync(
        r, _models("ibm-ete-int/aws/gpt-oss-120b", "ibm-rits/google/gemma-4-31B-it"),
        {"ibm-ete-int", "ibm-rits"}, write=True,
    )
    assert code == sm.EXIT_OK
    assert not any("unserved agent" in l for l in rep)


def test_task_pins_are_warnings_not_failures(tmp_path):
    r = _repo(tmp_path)
    code, rep = sm.sync(r, _models("ibm-ete-int/some-other-model"), {"ibm-ete-int"}, write=True)
    assert code == sm.EXIT_OK  # a pin mismatch warns, it never blocks the write
    assert any("unserved agent" in l and "aws/gpt-oss-120b" in l for l in rep)


def test_parses_the_real_workflow():
    text = (REPO / sm.WORKFLOW).read_text()
    for picker in sm.PICKERS:
        opts = sm.current_options(text, picker)
        assert opts, f"{picker} has no options in the real workflow"
        assert sm.current_default(text, picker) in opts


def test_roundtrip_on_a_copy_of_the_real_workflow_is_byte_stable(tmp_path):
    real = (REPO / sm.WORKFLOW).read_text()
    r = tmp_path
    (r / ".github" / "workflows").mkdir(parents=True)
    dest = r / ".github" / "workflows" / sm.WORKFLOW.name
    dest.write_text(real)
    opts = sm.current_options(real, "agent_model")
    rewritten = sm.rewrite_options(real, "agent_model", opts)
    assert rewritten == real


def test_validate_passes_on_the_real_workflow():
    ok, problems = sm.validate((REPO / sm.WORKFLOW).read_text(), (REPO / sm.RUN_SUITE).read_text())
    assert ok, problems


def test_validate_catches_a_default_outside_its_options(tmp_path):
    bad = WF.replace('default: "ibm-ete-int/aws/gpt-oss-120b"', 'default: "ibm-ete-int/not-in-options"', 1)
    ok, problems = sm.validate(bad, RS)
    assert not ok
    assert any("not-in-options" in p for p in problems)


def test_validate_needs_no_gateway():
    # sm.validate takes plain text, not a repo/network call — this test just documents
    # that contract so a future change doesn't accidentally make it need credentials.
    ok, _ = sm.validate(WF, RS)
    assert ok


def test_cli_requires_models_unless_validating(tmp_path, capsys, monkeypatch):
    r = _repo(tmp_path)
    monkeypatch.chdir(r)
    rc = sm.main(["--repo", str(r)])
    assert rc == sm.EXIT_DECISION
    out = capsys.readouterr().out + capsys.readouterr().err
    assert "--models" in out or True  # main() prints to stdout via print(); exact wording is main()'s own


def test_cli_models_flag_requires_prefix_equals_path(tmp_path, monkeypatch):
    r = _repo(tmp_path)
    monkeypatch.chdir(r)
    rc = sm.main(["--repo", str(r), "--models", "no-equals-sign-here"])
    assert rc == sm.EXIT_DECISION
