"""The agent's job description is capability text now, not frozen code.

Measured on run 30714307266, the agent read 359 words before starting a task: 144 in
`prompt.md` (optimizable) and 215 frozen in `adapter.py` — so **60% of its instruction
surface could not be optimized**. That frozen text is not boilerplate. It defines what
`instruction_type` means (Cell-Level = exact cells, Sheet-Level = the MAXIMUM range you may
modify), it defines the interaction contract, and it says:

    "once that file exists, you are done."

which tells the agent to stop as soon as it has written *any* output — the exact behaviour
behind the run's dominant failure mode (40 of 91 val tasks produced an output file whose
values were wrong). The one accepted candidate added a "verify before you save" checklist to
prompt.md, i.e. it was arguing with a sentence it was not allowed to delete.

Comparable published work (SkillOpt, arXiv 2605.23904) optimizes a single skill document
which, in a Claude Code / Codex harness, covers this same ground — so freezing it made our
editable surface strictly smaller than the thing we were comparing against.

`task_template.md` is therefore capability text. The risk it introduces is that an edit can
break the per-task placeholders, which would tell every rollout to write its answer to a path
it was never given — so live() validates once per evaluation and rejects the candidate before
any task runs.
"""

import importlib.util
import string
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "templates" / "adapters" / "spreadsheetbench"
SEED = ADAPTER_DIR / "seed_capability"


def _adapter():
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_tmpl", ADAPTER_DIR / "adapter.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_FIELDS = dict(instruction="do a thing", spreadsheet_path="/mnt/data/x.xlsx",
               spreadsheet_content="A1: 1", instruction_type="Cell-Level Manipulation",
               answer_position="'S'!C2", output_path="/mnt/data/outputs/t/1_x_output.xlsx",
               max_turns=30)


# --- the seed ships an editable template -------------------------------------------------


def test_the_seed_capability_ships_the_job_description_as_editable_text():
    assert (SEED / "task_template.md").is_file()
    assert (SEED / "prompt.md").is_file(), "the system prompt stays a separate artifact"


def test_the_shipped_template_carries_every_required_placeholder():
    mod = _adapter()
    text = (SEED / "task_template.md").read_text(encoding="utf-8")
    found = {f for _, f, _, _ in string.Formatter().parse(text) if f}
    assert mod._TEMPLATE_REQUIRED <= found


def test_the_shipped_template_still_renders_a_real_task():
    mod = _adapter()
    out = mod._read_task_template(SEED).format(**_FIELDS)
    for v in ("/mnt/data/outputs/t/1_x_output.xlsx", "'S'!C2", "do a thing"):
        assert v in out


def test_the_optimizer_facing_comment_never_reaches_the_agent():
    """The placeholder contract is documented inside the file; the agent must not see it."""
    mod = _adapter()
    raw = (SEED / "task_template.md").read_text(encoding="utf-8")
    assert "LOAD-BEARING PLACEHOLDERS" in raw, "the contract must be stated where it is edited"
    rendered = mod._read_task_template(SEED)
    assert "LOAD-BEARING" not in rendered and "<!--" not in rendered


def test_a_capability_without_a_template_falls_back_to_the_builtin(tmp_path):
    """Older capabilities, and any other adapter user, must be unaffected."""
    mod = _adapter()
    assert mod._read_task_template(tmp_path) == mod._TASK_TEMPLATE


# --- the guard: what a bad edit would otherwise do ---------------------------------------


def _write(tmp_path, body: str) -> Path:
    (tmp_path / "task_template.md").write_text(body, encoding="utf-8")
    return tmp_path


def test_a_dropped_placeholder_is_rejected_before_any_task_runs(tmp_path):
    """Without this, every rollout is told to write its answer to a path it never got."""
    mod = _adapter()
    ctx = _write(tmp_path, "Do {instruction} on {spreadsheet_path}. {spreadsheet_content} "
                           "{instruction_type} {answer_position}\n")   # no {output_path}
    with pytest.raises(RuntimeError) as e:
        mod._validate_task_template(ctx)
    msg = str(e.value)
    assert "{output_path}" in msg and "missing required placeholder" in msg
    assert "no task was run" in msg


def test_an_unknown_placeholder_is_rejected(tmp_path):
    """An invented field raises KeyError inside str.format on every single task."""
    mod = _adapter()
    body = "{instruction} {spreadsheet_path} {spreadsheet_content} {instruction_type} " \
           "{answer_position} {output_path} {sheet_name}\n"
    with pytest.raises(RuntimeError) as e:
        mod._validate_task_template(_write(tmp_path, body))
    assert "unknown placeholder" in str(e.value) and "{sheet_name}" in str(e.value)


def test_unbalanced_braces_are_rejected_with_the_doubling_rule(tmp_path):
    mod = _adapter()
    body = "{instruction} {spreadsheet_path} {spreadsheet_content} {instruction_type} " \
           "{answer_position} {output_path} then write {\n"
    with pytest.raises(RuntimeError) as e:
        mod._validate_task_template(_write(tmp_path, body))
    assert "not a valid format string" in str(e.value)


def test_dropping_the_cosmetic_turn_budget_is_allowed(tmp_path):
    """{max_turns} only tells the agent its round budget — the optimizer may restructure it
    away without breaking anything, so the guard must not be gratuitously strict."""
    mod = _adapter()
    body = "{instruction} {spreadsheet_path} {spreadsheet_content} {instruction_type} " \
           "{answer_position} {output_path}\n"
    ctx = _write(tmp_path, body)
    mod._validate_task_template(ctx)                      # must not raise
    assert mod._read_task_template(ctx).format(**_FIELDS)  # and still renders


def test_a_rewritten_template_is_accepted_which_is_the_whole_point(tmp_path):
    """The optimizer must be free to delete 'once that file exists, you are done'."""
    mod = _adapter()
    body = ("Task: {instruction}\nFile: {spreadsheet_path}\nPreview: {spreadsheet_content}\n"
            "Kind: {instruction_type}\nCells you may touch: {answer_position}\n"
            "Write to: {output_path}\nVERIFY your values before saving. Do NOT stop merely "
            "because a file exists.\n")
    ctx = _write(tmp_path, body)
    mod._validate_task_template(ctx)
    out = mod._read_task_template(ctx).format(**_FIELDS)
    assert "Do NOT stop merely because a file exists" in out
    assert "once that file exists, you are done" not in out


# --- wiring --------------------------------------------------------------------------------


def test_live_validates_and_run_target_uses_the_capability_template():
    src = (ADAPTER_DIR / "adapter.py").read_text(encoding="utf-8")
    assert "_validate_task_template(candidate_dir)" in src, "live() must validate"
    assert "def live(self, candidate_dir)" in src
    assert "user_msg = _read_task_template(ctx).format(" in src, "run_target must use it"
    assert "_TASK_TEMPLATE.format(" not in src, "the frozen template must no longer be used directly"


def test_live_validates_once_per_evaluation_not_once_per_task():
    """91 (or 639) identical failures is not a useful way to learn the template is broken."""
    src = (ADAPTER_DIR / "adapter.py").read_text(encoding="utf-8")
    run_target = src.split("def run_target(", 1)[1]
    assert "_validate_task_template" not in run_target.split("def score(", 1)[0]
