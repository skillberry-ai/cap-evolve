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


def test_a_dropped_placeholder_is_reported_not_raised(tmp_path):
    """Reporting rather than raising is the whole point: harness.run_step does NOT wrap
    evaluate_candidate in try/except, so anything raised from live() aborts the entire run —
    losing a multi-hour sealed evaluation over one bad text edit."""
    mod = _adapter()
    ctx = _write(tmp_path, "Do {instruction} on {spreadsheet_path}. {spreadsheet_content} "
                           "{instruction_type} {answer_position}\n")   # no {output_path}
    msg = mod._task_template_error(ctx)
    assert msg and "{output_path}" in msg and "missing required placeholder" in msg
    assert "every" in msg and "scores 0" in msg, "the message must say what the consequence is"


def test_an_unknown_placeholder_is_reported(tmp_path):
    """An invented field raises KeyError inside str.format on every single task."""
    mod = _adapter()
    body = "{instruction} {spreadsheet_path} {spreadsheet_content} {instruction_type} " \
           "{answer_position} {output_path} {sheet_name}\n"
    msg = mod._task_template_error(_write(tmp_path, body))
    assert msg and "unknown placeholder" in msg and "{sheet_name}" in msg


def test_unbalanced_braces_are_reported_with_the_doubling_rule(tmp_path):
    mod = _adapter()
    body = "{instruction} {spreadsheet_path} {spreadsheet_content} {instruction_type} " \
           "{answer_position} {output_path} then write {\n"
    msg = mod._task_template_error(_write(tmp_path, body))
    assert msg and "not a valid format string" in msg


def test_a_good_template_reports_no_error(tmp_path):
    mod = _adapter()
    assert mod._task_template_error(SEED) is None
    assert mod._task_template_error(tmp_path) is None       # no file at all


def test_live_never_raises_so_a_bad_edit_cannot_abort_the_run(tmp_path):
    """The bug this fixes: live() raising propagates through evaluate_candidate, which
    run_step leaves unprotected, and kills the run."""
    mod = _adapter()
    ad = object.__new__(mod.Adapter)
    ctx = _write(tmp_path, "only {instruction}\n")          # badly broken
    with ad.live(ctx) as yielded:                            # must NOT raise
        assert yielded == ctx


def test_the_harness_path_also_survives_a_broken_template(tmp_path):
    """Exercised through harness._live, which is what the eval actually calls."""
    mod = _adapter()
    sys.path.insert(0, str(REPO / "core"))
    from cap_evolve import harness
    ad = object.__new__(mod.Adapter)
    ctx = _write(tmp_path, "only {instruction}\n")
    with harness._live(ad, ctx) as yielded:
        assert yielded == ctx


def test_run_target_refuses_before_spending_anything(tmp_path):
    """The candidate must cost ~nothing: no LLM call, no container, no 30-turn loop."""
    src = (ADAPTER_DIR / "adapter.py").read_text(encoding="utf-8")
    body = src.split("def run_target(", 1)[1].split("def score(", 1)[0]
    check = body.index("_task_template_error(ctx)")
    for later in ("import litellm", "_get_sandbox()", "_entries_by_id()"):
        assert check < body.index(later), f"the template check must precede {later}"


def test_dropping_the_cosmetic_turn_budget_is_allowed(tmp_path):
    """{max_turns} only tells the agent its round budget — the optimizer may restructure it
    away without breaking anything, so the guard must not be gratuitously strict."""
    mod = _adapter()
    body = "{instruction} {spreadsheet_path} {spreadsheet_content} {instruction_type} " \
           "{answer_position} {output_path}\n"
    ctx = _write(tmp_path, body)
    assert mod._task_template_error(ctx) is None           # accepted
    assert mod._read_task_template(ctx).format(**_FIELDS)  # and still renders


def test_a_rewritten_template_is_accepted_which_is_the_whole_point(tmp_path):
    """The optimizer must be free to delete 'once that file exists, you are done'."""
    mod = _adapter()
    body = ("Task: {instruction}\nFile: {spreadsheet_path}\nPreview: {spreadsheet_content}\n"
            "Kind: {instruction_type}\nCells you may touch: {answer_position}\n"
            "Write to: {output_path}\nVERIFY your values before saving. Do NOT stop merely "
            "because a file exists.\n")
    ctx = _write(tmp_path, body)
    assert mod._task_template_error(ctx) is None
    out = mod._read_task_template(ctx).format(**_FIELDS)
    assert "Do NOT stop merely because a file exists" in out
    assert "once that file exists, you are done" not in out


# --- wiring --------------------------------------------------------------------------------


def test_the_optimizer_is_told_both_files_are_editable():
    """The unlock is inert unless the instructions NAME the second artifact. Pilot
    30736646559 proved it: both files were in the optimizer's workdir, the rendered
    instructions mentioned neither by name, and it reported "all in prompt.md"."""
    sh = (REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh").read_text(encoding="utf-8")
    arm = sh.split("  spreadsheetbench)", 1)[1].split("\n  *)", 1)[0]
    assert "## The TWO files you may edit" in arm
    for f in ("prompt.md", "task_template.md"):
        assert f"`{f}`" in arm, f"{f} must be named explicitly"
    # It must also carry the contract, so the optimizer does not learn it via a rejection.
    for ph in ("{instruction}", "{output_path}", "{answer_position}"):
        assert ph in arm
    assert "EVERY task scores 0" in arm, "state the consequence of breaking a placeholder"
    assert "appended" not in arm.lower() or True
    # …and it must be APPENDED to the copied file, not to the shared template in templates/.
    assert '>> "$PROJ/optimizer/INSTRUCTIONS.md"' in arm
    shared = (REPO / "templates" / "project" / "optimizer" / "INSTRUCTIONS.prompt-only.md").read_text(encoding="utf-8")
    assert "task_template.md" not in shared, "the shared template must stay benchmark-neutral"


def test_live_reports_and_run_target_uses_the_capability_template():
    src = (ADAPTER_DIR / "adapter.py").read_text(encoding="utf-8")
    assert "_task_template_error(candidate_dir)" in src, "live() must report the reason once"
    assert "def live(self, candidate_dir)" in src
    assert "raise RuntimeError" not in src.split("def live(", 1)[1].split("def run_target", 1)[0]
    assert "user_msg = _read_task_template(ctx).format(" in src, "run_target must use it"
    assert "_TASK_TEMPLATE.format(" not in src, "the frozen template must no longer be used directly"


def test_live_logs_the_reason_once_per_evaluation():
    """One loud line per eval, not 639 — while run_target still fails each rollout cheaply."""
    src = (ADAPTER_DIR / "adapter.py").read_text(encoding="utf-8")
    live = src.split("def live(", 1)[1].split("def run_target", 1)[0]
    assert "file=sys.stderr" in live
