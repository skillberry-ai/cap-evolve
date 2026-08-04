"""Feedback that points the wrong way is worse than no feedback.

PR #289 appended one UNCONDITIONAL clause to every TYPE mismatch it reported:

    " — write real numbers/dates, not their text form."

Measured on pilot 30890657732 that clause fired on 6 tasks and was **backwards on two of them**:
`57232` held `float where str was expected` and `50630` held `datetime where str was expected`, and
both were told to write real numbers. Worse, pilot 30799393875's own `PROCESS.md` had already
root-caused `50630` correctly — *"GT keeps the fragment as the original text string"* — so the
optimizer was simultaneously reading its own correct diagnosis and our contradictory advice.

This matters more than a cosmetic wording bug: the optimizer writes capability rules from this
feedback, and a rule pushing the wrong direction can regress a task that currently passes.

Also pins the warm-start seed as a *valid capability*, because a broken template there would
reject every candidate before any task runs.
"""

import importlib.util
import string
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "templates" / "adapters" / "spreadsheetbench"
WARM = ADAPTER_DIR / "seed_capability_warm"


def _adapter():
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_adv", ADAPTER_DIR / "adapter.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- direction awareness -----------------------------------------------------------------


def test_text_where_a_number_was_expected_says_write_the_real_value():
    out = _adapter()._type_advice([("str", "int")]).lower()
    assert "real typed value" in out or "real value" in out
    assert "keep the original text" not in out


def test_a_number_where_text_was_expected_says_KEEP_the_text():
    """The exact case (`57232`) the old static clause got backwards."""
    out = _adapter()._type_advice([("float", "str")]).lower()
    assert "keep the original text" in out
    assert "write the real typed value" not in out


def test_a_datetime_where_text_was_expected_says_do_not_parse():
    """Task `50630`: the agent parsed a split-out date fragment; gold keeps it as text."""
    out = _adapter()._type_advice([("datetime", "str")]).lower()
    assert "do not parse" in out
    assert "keep the original text" in out


def test_a_mixed_pair_gets_both_directions_and_contradicts_neither():
    out = _adapter()._type_advice([("str", "int"), ("float", "str")]).lower()
    assert "real typed value" in out and "keep the original text" in out


def test_two_non_textual_types_get_no_directional_advice():
    """int vs float: neither side is text, so neither tip applies."""
    out = _adapter()._type_advice([("int", "float")]).lower()
    assert "match the expected type exactly" in out
    assert "text form" not in out


def test_the_old_unconditional_wording_is_gone_for_the_to_text_direction():
    """Regression pin: the exact string that miseducated the optimizer must not reappear."""
    for pairs in ([("float", "str")], [("datetime", "str")]):
        assert "not their text form" not in _adapter()._type_advice(pairs)


def test_advice_never_returns_empty_so_the_note_is_always_well_formed():
    for pairs in ([("str", "int")], [("float", "str")], [("int", "float")], []):
        out = _adapter()._type_advice(pairs)
        assert out.startswith(" — ") and out.rstrip().endswith(".")


# --- the warm-start seed must be a usable capability -------------------------------------


def test_the_warm_seed_ships_both_editable_artifacts():
    assert (WARM / "prompt.md").is_file()
    assert (WARM / "task_template.md").is_file()
    assert (WARM / "PROVENANCE.md").is_file(), "a warm seed without provenance is unciteable"


def test_the_warm_seed_template_carries_every_required_placeholder():
    """A missing placeholder here would reject every candidate before any task runs."""
    mod = _adapter()
    found = {
        f for _, f, _, _ in
        string.Formatter().parse((WARM / "task_template.md").read_text(encoding="utf-8")) if f
    }
    assert mod._TEMPLATE_REQUIRED <= found


def test_the_warm_seed_template_renders_a_real_task():
    fields = dict(instruction="do a thing", spreadsheet_path="/mnt/data/x.xlsx",
                  spreadsheet_content="A1: 1", instruction_type="Cell-Level Manipulation",
                  answer_position="'S'!C2", output_path="/mnt/data/outputs/t/1_x_output.xlsx",
                  max_turns=30)
    # Go through _read_task_template, which strips the optimizer-facing HTML comment block —
    # that block documents the contract and itself contains a literal "{braces}", so formatting
    # the raw file would raise KeyError on documentation rather than on a real defect.
    out = _adapter()._read_task_template(WARM).format(**fields)
    for v in ("/mnt/data/outputs/t/1_x_output.xlsx", "'S'!C2", "do a thing"):
        assert v in out


def test_the_warm_seed_prompt_is_not_empty():
    """An empty prompt.md is the no-skill CONTROL; a warm seed must not silently become it."""
    assert (WARM / "prompt.md").read_text(encoding="utf-8").strip()
