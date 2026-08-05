"""The agent is handed facts it was previously expected to go and discover.

Measured on pilot run 30799393875 (50 val tasks, champion `cand_0001`), two failure modes
survived PR #289's richer scoring feedback:

  * **8 tasks passed 1/3 or 2/3** — the solution was right for copy 1 and wrong for the two
    other graded copies. The agent is told 201 times across 150 rollouts that "the grader
    replays your SAME final code on two other copies", and it referenced those copies
    **zero** times — because nothing ever told it WHERE they are. They sit in the same
    mounted directory it reads its input from.
  * **4 tasks filled far too few cells** — e.g. task `110-2` wrote 9 of 39 target cells,
    exactly `3 rows x 3 cols`, because the five-row preview was the only extent signal it had.

Turn usage over the same run went 3.52 -> 3.32 against a cap of 30, so asking the agent to go
look is demonstrably not what changes its behaviour. These helpers therefore STATE the facts:
the target range's size, each sheet's real data extent, and the existence and location of the
other graded copies.

Deliberately FACTUAL, not prescriptive. Nothing here tells the agent to self-test on the other
copies — that strategy is left to the optimizer to discover, so any resulting gain is credited
to the optimizer rather than hand-supplied by us (cf. issue #276).

One hazard this closes: the replay substitutes filenames into the agent's FINAL code block
(`adapter.py`, "replay the SAME code onto cases 2 and 3"). If the agent left a three-copy loop
in that final block, the substitution would corrupt cases 2 and 3 — so the injected text
states that the final block must read exactly one input.
"""

import importlib.util
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
    spec = importlib.util.spec_from_file_location("_sb_ctx", ADAPTER_DIR / "adapter.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- target size: pure arithmetic on a string the agent already has ----------------------


def test_a_single_range_reports_its_exact_cell_count():
    # 'Sheet1'!A1:C13 is task 110-2's real answer_position; the scorer graded it as 39 cells.
    out = _adapter()._target_facts("'Sheet1'!A1:C13")
    assert "39" in out
    assert "Sheet1" in out


def test_the_count_matches_what_the_scorer_will_grade_against():
    """_target_facts and the COVERAGE diagnostic must not disagree about the denominator."""
    mod = _adapter()
    pos = "'Sheet1'!A1:C13"
    span = sum((c2 - c1 + 1) * (r2 - r1 + 1) for _, c1, r1, c2, r2 in mod._range_cells(pos))
    assert str(span) in mod._target_facts(pos)


def test_multi_range_multi_sheet_targets_are_summed_and_both_sheets_named():
    # Task 19-7's real answer_position: 40 + 20,796 = 20,836 cells over two sheets.
    out = _adapter()._target_facts("'MINUS'!B2:E11,'PLUS'!B2:E5200")
    assert "20836" in out.replace(",", "")
    assert "MINUS" in out and "PLUS" in out


def test_absolute_and_single_cell_notation_are_understood():
    mod = _adapter()
    assert "40" in mod._target_facts("'S'!$B$2:$E$11")
    assert "1" in mod._target_facts("'S'!B2")


def test_an_unparseable_answer_position_degrades_quietly():
    """_range_cells skips parts it cannot match, so this must not raise."""
    assert _adapter()._target_facts("not a range at all") == ""


def test_target_facts_states_size_without_prescribing_strategy():
    """Integrity: the facts must not smuggle in the rule we want the optimizer to learn."""
    out = _adapter()._target_facts("'Sheet1'!A1:C13").lower()
    for prescription in ("you should", "make sure", "verify", "test your", "always"):
        assert prescription not in out


# --- the other graded copies -------------------------------------------------------------


def _make_book(path: Path, data_rows: int, cols: int = 3, pad_to: int | None = None):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([f"Col{i + 1}" for i in range(cols)])
    for r in range(data_rows):
        ws.append([r * 10 + c for c in range(cols)])
    if pad_to:  # formatted-but-EMPTY trailing cell: inflates max_row, not the real extent
        ws.cell(pad_to, 1).number_format = "0.00"
    wb.save(path)
    return path


def test_existing_sibling_copies_are_named_with_their_container_paths(tmp_path):
    for idx in (1, 2, 3):
        _make_book(tmp_path / f"{idx}_42_input.xlsx", 5)
    out = _adapter()._sibling_inputs(tmp_path, "42", "/mnt/data/spreadsheet/42")
    assert "/mnt/data/spreadsheet/42/2_42_input.xlsx" in out
    assert "/mnt/data/spreadsheet/42/3_42_input.xlsx" in out


def test_missing_sibling_copies_are_not_advertised(tmp_path):
    _make_book(tmp_path / "1_42_input.xlsx", 5)
    _make_book(tmp_path / "2_42_input.xlsx", 5)
    out = _adapter()._sibling_inputs(tmp_path, "42", "/mnt/data/spreadsheet/42")
    assert "2_42_input.xlsx" in out
    assert "3_42_input.xlsx" not in out


def test_no_siblings_yields_no_text(tmp_path):
    _make_book(tmp_path / "1_42_input.xlsx", 5)
    assert _adapter()._sibling_inputs(tmp_path, "42", "/mnt/data/spreadsheet/42") == ""


def test_the_replay_constraint_is_stated_so_a_self_test_cannot_corrupt_cases_2_and_3(tmp_path):
    """The final block is replayed with filenames substituted; it must read ONE input."""
    for idx in (1, 2, 3):
        _make_book(tmp_path / f"{idx}_42_input.xlsx", 5)
    out = _adapter()._sibling_inputs(tmp_path, "42", "/mnt/data/spreadsheet/42").lower()
    assert "final" in out
    assert "one input" in out or "exactly one" in out


# --- per-sheet data extent ---------------------------------------------------------------


def test_the_preview_reports_the_real_data_extent(tmp_path):
    book = _make_book(tmp_path / "1_42_input.xlsx", data_rows=12, cols=9)
    out = _adapter()._spreadsheet_preview(book, 5)
    assert "12" in out and "9" in out, "must state rows x cols"
    assert "extent" in out.lower()


def test_the_extent_uses_the_parsed_shape_not_openpyxls_inflated_max_row(tmp_path):
    """max_row counts formatted-but-empty cells; trusting it would teach overfilling."""
    openpyxl = pytest.importorskip("openpyxl")
    book = _make_book(tmp_path / "1_42_input.xlsx", data_rows=12, cols=3, pad_to=200)
    assert openpyxl.load_workbook(book).active.max_row >= 200, "fixture must inflate max_row"
    out = _adapter()._spreadsheet_preview(book, 5)
    assert "200" not in out, "the inflated max_row must not reach the agent"
    assert "12" in out


def test_the_five_data_rows_are_still_shown(tmp_path):
    book = _make_book(tmp_path / "1_42_input.xlsx", data_rows=12, cols=3)
    out = _adapter()._spreadsheet_preview(book, 5)
    assert "Col1" in out, "column headers survive"
    assert out.count("\n") > 5, "data rows are still rendered"


# --- composition and failure containment -------------------------------------------------


def test_the_context_block_carries_all_three_kinds_of_fact(tmp_path):
    for idx in (1, 2, 3):
        _make_book(tmp_path / f"{idx}_42_input.xlsx", 12)
    mod = _adapter()
    out = mod._workbook_context(tmp_path / "1_42_input.xlsx", tmp_path, "42",
                                "/mnt/data/spreadsheet/42", "'Sheet'!A1:C13", 5)
    assert "39" in out                          # target size
    assert "2_42_input.xlsx" in out             # sibling copies
    assert "extent" in out.lower()              # data extent
    assert "Col1" in out                        # the original preview


def test_a_broken_structure_computation_degrades_to_the_plain_preview(tmp_path, monkeypatch):
    """_spreadsheet_preview at the call site was previously unwrapped, and this file has a
    documented history of a pandas/PyArrow SIGSEGV in that path killing a whole run."""
    book = _make_book(tmp_path / "1_42_input.xlsx", 12)
    mod = _adapter()

    def boom(*a, **k):
        raise RuntimeError("structure computation failed")

    monkeypatch.setattr(mod, "_target_facts", boom)
    out = mod._workbook_context(book, tmp_path, "42", "/mnt/data/spreadsheet/42",
                                "'Sheet'!A1:C13", 5)
    assert "Col1" in out, "the agent still gets its preview"
    assert "39" not in out


# --- the seed template advertises what it now receives -----------------------------------


def test_the_seed_template_describes_the_enriched_content_field():
    text = (SEED / "task_template.md").read_text(encoding="utf-8").lower()
    assert "extent" in text or "target size" in text, (
        "the template's spreadsheet_content bullet should describe the facts now injected"
    )
