"""`optimizer.ablation.history: false` / env CAPEVOLVE_HISTORY=0 removes the cross-iteration history from
what the PROPOSER sees and nothing else (Suite D cell E26-nohist). With the switch at its default, the
staging is unchanged."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))

HISTORY_FILES = ("LEDGER.md", "JOURNAL.md", "RUNMAP.md", "INSIGHTS.md", "META_INSIGHTS.md",
                 "FRAMEWORK_IMPROVEMENTS.md")


def _rd(tmp):
    from cap_evolve import RunDir
    rd = RunDir.create(Path(tmp) / ".capevolve", ts="hist")
    rd.candidate_dir("seed").mkdir(parents=True, exist_ok=True)
    rd.log_event("step", candidate="cand_1", parent="seed", accept=False, val=0.5)
    return rd


def _stage(monkeypatch, value):
    from cap_evolve import harness
    if value is None:
        monkeypatch.delenv("CAPEVOLVE_HISTORY", raising=False)
    else:
        monkeypatch.setenv("CAPEVOLVE_HISTORY", value)
    tmp = tempfile.mkdtemp()
    rd = _rd(tmp)
    work = Path(tmp) / "work"
    work.mkdir()
    text = harness._augment_instructions("BASE", work, rd)
    return work, text, rd


def test_default_stages_the_full_history(monkeypatch):
    work, text, _ = _stage(monkeypatch, None)
    for name in HISTORY_FILES + ("PROCESS.md",):
        assert (work / name).is_file(), name
        assert name in text
    assert (work / "prior_iterations").is_dir()


def test_off_stages_no_history_and_no_pointer(monkeypatch):
    work, text, rd = _stage(monkeypatch, "0")
    for name in HISTORY_FILES:
        assert not (work / name).exists(), name
        assert name not in text, name
    assert not (work / "prior_iterations").exists()
    assert "prior_iterations" not in text and "RUNMAP" not in text
    assert (work / "PROCESS.md").is_file() and "PROCESS.md" in text
    assert str(rd.rejected_path) in text   # the gate's reasons are not part of the switch


def test_off_drops_only_the_passing_block(monkeypatch):
    from cap_evolve import harness
    monkeypatch.setenv("CAPEVOLVE_HISTORY", "0")
    assert harness.history_enabled() is False
    monkeypatch.delenv("CAPEVOLVE_HISTORY")
    assert harness.history_enabled() is True
    block = harness._passing_block([{"task_id": "7"}])
    assert "Currently PASSING" in block and "7" in block   # the helper itself is unchanged


def test_spec_key_sets_the_env_bridge_value():
    from cap_evolve import optimizer_config as oc
    assert oc.enabled("history", {"optimizer": {"ablation": {"history": False}}}) is False
    assert oc.DEFAULTS["history"] is True


def _val():
    from cap_evolve.loop import SplitResult
    return SplitResult.from_dict({
        "split": "val", "reward": 0.5, "stderr": 0.0,
        "per_task": [{"task_id": "v1", "reward": 0.0, "feedback": "boom"},
                     {"task_id": "v2", "reward": 1.0, "feedback": ""}]})


def test_rendered_prompt_has_no_history_pointer_or_passing_block_when_off(monkeypatch, tmp_path):
    """The rendered prompt: with a project template free of history text (the E26 derived one) nothing
    in the render names a history file and the {{PASSING}} block is empty; with the switch on, the
    passing block is present. The template itself is project-owned (see scripts/E26/nohist_instructions.py)."""
    from cap_evolve import harness
    tmpl = tmp_path / "INSTRUCTIONS.md"
    tmpl.write_text("# t\n{{FOCUS_SUMMARY}}\n{{FAILURES}}\n{{PASSING}}\n", encoding="utf-8")
    monkeypatch.setenv("CAPEVOLVE_HISTORY", "0")
    off = harness._focus_instructions(_val(), None, "val", instructions_file=str(tmpl))
    assert "Currently PASSING" not in off
    monkeypatch.delenv("CAPEVOLVE_HISTORY")
    on = harness._focus_instructions(_val(), None, "val", instructions_file=str(tmpl))
    assert "Currently PASSING" in on


def test_fallback_prompt_names_no_history_file_when_off(monkeypatch, tmp_path):
    from cap_evolve import harness
    monkeypatch.setenv("CAPEVOLVE_HISTORY", "0")
    off = harness._focus_instructions(_val(), None, "val", instructions_file=str(tmp_path / "missing.md"))
    for name in ("LEDGER", "JOURNAL", "RUNMAP", "prior_iterations"):
        assert name not in off, name
    monkeypatch.delenv("CAPEVOLVE_HISTORY")
    on = harness._focus_instructions(_val(), None, "val", instructions_file=str(tmp_path / "missing.md"))
    assert "LEDGER" in on


def test_bad_unrelated_switch_does_not_break_history_enabled(monkeypatch):
    from cap_evolve import harness
    monkeypatch.setenv("CAPEVOLVE_ACTIVE_EVAL", "maybe")
    monkeypatch.delenv("CAPEVOLVE_HISTORY", raising=False)
    assert harness.history_enabled() is True
