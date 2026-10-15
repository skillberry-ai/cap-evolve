"""The SpreadsheetBench FRAME layout (#871): sealed task_frame.md + editable guidance.md.

#851 showed that a weak optimizer deletes the interaction contract from an editable
task_template.md ("exactly ONE python block per round", "reply without code to finish"),
which costs about 5 test points. In the frame layout that contract and the placeholders live
in a SEALED frame; the editable guidance.md is inserted into it and may contain anything.
"""

import importlib.util
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "templates" / "adapters" / "spreadsheetbench"
FRAME_SEED = ADAPTER_DIR / "seed_capability_frame"

_FIELDS = dict(instruction="do a thing", spreadsheet_path="/mnt/data/x.xlsx",
               spreadsheet_content="A1: 1", instruction_type="Cell-Level Manipulation",
               answer_position="'S'!C2", output_path="/mnt/data/outputs/t/1_x_output.xlsx",
               max_turns=30)


def _adapter():
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_frame", ADAPTER_DIR / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cap(tmp_path, guidance=None, frame=True, template=None):
    cap = tmp_path / "cap"
    cap.mkdir()
    (cap / "prompt.md").write_text("", encoding="utf-8")
    if frame:
        shutil.copy(FRAME_SEED / "task_frame.md", cap / "task_frame.md")
    if guidance is not None:
        (cap / "guidance.md").write_text(guidance, encoding="utf-8")
    if template is not None:
        (cap / "task_template.md").write_text(template, encoding="utf-8")
    return cap


def test_the_frame_seed_ships_all_three_files_and_its_frame_is_valid(tmp_path):
    m = _adapter()
    for f in ("task_frame.md", "guidance.md", "prompt.md"):
        assert (FRAME_SEED / f).is_file()
    assert m._task_template_error(_cap(tmp_path, guidance="")) is None


def test_the_contract_is_always_in_the_message_even_with_empty_guidance(tmp_path):
    m = _adapter()
    msg = m._render_user_message(_cap(tmp_path, guidance=""), **_FIELDS)
    assert "exactly ONE ```python fenced code block" in msg
    assert "reply without a code block to finish" in msg
    assert "up to 30 rounds" in msg
    assert "### Guidance" not in msg              # empty guidance ⇒ no section
    assert "<!--" not in msg and "\x00" not in msg
    for v in ("do a thing", "/mnt/data/x.xlsx", "'S'!C2", "/mnt/data/outputs/t/1_x_output.xlsx"):
        assert v in msg


def test_guidance_is_inserted_verbatim_and_may_contain_braces(tmp_path):
    m = _adapter()
    g = "<!-- note -->\nVerify with {data_only=True} and print {answer_position} cells."
    msg = m._render_user_message(_cap(tmp_path, guidance=g), **_FIELDS)
    assert "### Guidance\nVerify with {data_only=True} and print {answer_position} cells." in msg
    assert msg.index("### Guidance") < msg.index("### How this session works")
    assert "note" not in msg


def test_a_task_template_is_ignored_in_the_frame_layout(tmp_path):
    """An optimizer that recreates task_template.md cannot remove the contract that way."""
    m = _adapter()
    cap = _cap(tmp_path, guidance="g", template="just do it {output_path}")
    msg = m._render_user_message(cap, **_FIELDS)
    assert "just do it" not in msg and "exactly ONE ```python" in msg
    assert m._task_template_error(cap) is None


def test_the_adapter_default_frame_is_used_when_the_capability_has_none(tmp_path):
    m = _adapter()
    msg = m._render_user_message(_cap(tmp_path, guidance="g", frame=False), **_FIELDS)
    assert "exactly ONE ```python" in msg


def test_a_broken_frame_is_reported_not_raised(tmp_path):
    m = _adapter()
    cap = _cap(tmp_path, guidance="g")
    (cap / "task_frame.md").write_text("no placeholders here {guidance}", encoding="utf-8")
    err = m._task_template_error(cap)
    assert err and "task_frame.md" in err and "output_path" in err


def test_the_old_layout_is_unchanged(tmp_path):
    """No guidance.md ⇒ exactly the previous render, from task_template.md or the built-in."""
    m = _adapter()
    cap = _cap(tmp_path, frame=False, template="T {instruction} -> {output_path}")
    assert m._render_user_message(cap, **_FIELDS) == "T do a thing -> /mnt/data/outputs/t/1_x_output.xlsx\n"
    bare = tmp_path / "bare"
    bare.mkdir()
    assert m._render_user_message(bare, **_FIELDS) == m._TASK_TEMPLATE.format(**_FIELDS)
