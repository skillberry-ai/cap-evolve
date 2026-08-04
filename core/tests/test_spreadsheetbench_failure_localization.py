"""A failure that says only "values did not match" teaches the optimizer nothing.

MEASURED on run 30762167950: **197 of 639 sealed tasks failed all three test cases**, and the
entire signal the optimizer received for each was:

    "0/3 test cases passed (Sheet-Level Manipulation, checked range:
     MINUS'!B2:E11,'PLUS'!B2:E5200). Test case(s) [1, 2, 3] produced an output file but its
     values did not match the expected result."

One bit: wrong. It never said whether the range was left empty, whether a whole sheet was
untouched, whether only 10 of 5,199 cells were filled, or whether the values were right but
stored as text. So the optimizer could only learn generic discipline ("do not hardcode",
"verify your work") — and indeed our champion learned six of the nine rules comparable
published work reports, while missing exactly the two about LOCATING and COVERING the target
range. It had no evidence those were the failing sub-step.

Task 19-7 is the archetype: two sheets, ~5,200 rows, and the agent spent two turns — write,
then "Done." — from a five-row preview.

GOLD SAFETY. Coverage and untouched-sheet notes never open the gold file: they compare the
agent's output against its own INPUT and against the range it was handed, both already known
to it. The type note reports a value's TYPE, not a value — metadata, judged worth that narrow
disclosure because it is the most actionable diagnostic here. No cell value is ever emitted.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "templates" / "adapters" / "spreadsheetbench"
openpyxl = pytest.importorskip("openpyxl")


def _adapter():
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_loc", ADAPTER_DIR / "adapter.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _book(path, sheets):
    """sheets: {name: {(row, col): value}}"""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, cells in sheets.items():
        ws = wb.create_sheet(name)
        for (r, c), v in cells.items():
            ws.cell(r, c).value = v
    wb.save(path)
    return path


# --- range parsing -----------------------------------------------------------------------


def test_multi_sheet_multi_range_answer_position_is_parsed():
    """The real notation from task 19-7 — two sheets in one answer_position."""
    mod = _adapter()
    got = list(mod._range_cells("MINUS'!B2:E11,'PLUS'!B2:E5200"))
    assert got == [("MINUS", 2, 2, 5, 11), ("PLUS", 2, 2, 5, 5200)]


def test_single_cell_and_sheetless_forms_are_parsed():
    mod = _adapter()
    assert list(mod._range_cells("C20:C29")) == [(None, 3, 20, 3, 29)]
    assert list(mod._range_cells("'Test'!B7")) == [("Test", 2, 7, 2, 7)]


def test_unparseable_parts_are_skipped_not_fatal():
    mod = _adapter()
    assert list(mod._range_cells("garbage,,C1:C2")) == [(None, 3, 1, 3, 2)]


# --- the diagnostics ---------------------------------------------------------------------


def test_an_empty_target_range_is_named_as_such(tmp_path):
    """The most common total failure: a file was written, the answer was not."""
    mod = _adapter()
    src = _book(tmp_path / "in.xlsx", {"S": {(1, 1): "hdr"}})
    out = _book(tmp_path / "out.xlsx", {"S": {(1, 1): "hdr"}})
    gold = _book(tmp_path / "gold.xlsx", {"S": {(1, 1): "hdr", (2, 3): 5, (3, 3): 6}})
    notes = mod._localize_failure({"answer_position": "'S'!C2:C3"}, out, src, gold)
    joined = " ".join(notes)
    assert "COVERAGE" in joined and "spans 2 cell(s)" in joined and "value in 0" in joined
    assert "EMPTY in your output" in joined


def test_partial_coverage_of_a_large_range_is_flagged(tmp_path):
    """Task 19-7's shape: a 5,200-row range with a handful of cells filled."""
    mod = _adapter()
    src = _book(tmp_path / "in.xlsx", {"P": {}})
    out = _book(tmp_path / "out.xlsx", {"P": {(r, 2): r for r in range(2, 12)}})
    gold = _book(tmp_path / "gold.xlsx", {"P": {(r, 2): r for r in range(2, 5201)}})
    notes = mod._localize_failure({"answer_position": "'P'!B2:B5200"}, out, src, gold)
    joined = " ".join(notes)
    assert "spans 5199 cell(s)" in joined and "value in 10 of them" in joined
    assert "Most of the target range was left unfilled" in joined


def test_a_sheet_never_modified_is_named(tmp_path):
    """The other half of 19-7: one range handled, the second sheet ignored entirely."""
    mod = _adapter()
    cells = {(r, 2): "x" for r in range(2, 6)}
    src = _book(tmp_path / "in.xlsx", {"MINUS": dict(cells), "PLUS": dict(cells)})
    out = _book(tmp_path / "out.xlsx", {"MINUS": {(r, 2): "done" for r in range(2, 6)},
                                        "PLUS": dict(cells)})
    gold = _book(tmp_path / "gold.xlsx", {"MINUS": {(r, 2): "done" for r in range(2, 6)},
                                          "PLUS": {(r, 2): "done" for r in range(2, 6)}})
    notes = mod._localize_failure({"answer_position": "'MINUS'!B2:B5,'PLUS'!B2:B5"}, out, src, gold)
    joined = " ".join(notes)
    assert "UNCHANGED" in joined and "PLUS" in joined
    assert "MINUS" not in joined.split("UNCHANGED")[1][:60], "the sheet that WAS edited must not be listed"


def test_a_type_mismatch_reports_the_type_and_never_the_value(tmp_path):
    """The date-as-text class. The expected TYPE is disclosed; the value is not."""
    import datetime
    mod = _adapter()
    src = _book(tmp_path / "in.xlsx", {"S": {}})
    out = _book(tmp_path / "out.xlsx", {"S": {(2, 1): "2026-01-02", (3, 1): "2026-01-03"}})
    gold = _book(tmp_path / "gold.xlsx", {"S": {(2, 1): datetime.datetime(2026, 1, 2),
                                                (3, 1): datetime.datetime(2026, 1, 3)}})
    notes = mod._localize_failure({"answer_position": "'S'!A2:A3"}, out, src, gold)
    joined = " ".join(notes)
    assert "TYPE:" in joined and "str where datetime was expected" in joined
    for leaked in ("2026-01-02", "2026-01-03"):
        assert leaked not in joined, "a gold VALUE must never appear in feedback"


def test_coverage_and_untouched_notes_do_not_consult_the_gold_file(tmp_path):
    """Proven by deleting it: the two structural signals must still be produced."""
    mod = _adapter()
    src = _book(tmp_path / "in.xlsx", {"S": {(2, 1): "a"}})
    out = _book(tmp_path / "out.xlsx", {"S": {(2, 1): "a"}})
    notes = mod._localize_failure({"answer_position": "'S'!A2:A3"}, out, src,
                                  tmp_path / "does-not-exist.xlsx")
    joined = " ".join(notes)
    assert "COVERAGE" in joined and "UNCHANGED" in joined
    assert "TYPE:" not in joined


def test_a_broken_produced_file_degrades_quietly(tmp_path):
    """A diagnostic must never cost a score."""
    mod = _adapter()
    bad = tmp_path / "corrupt.xlsx"
    bad.write_bytes(b"not a workbook")
    assert mod._localize_failure({"answer_position": "A1:A2"}, bad, bad, bad) == []


# --- wiring ------------------------------------------------------------------------------


def test_the_notes_reach_the_feedback_the_optimizer_reads():
    mod = _adapter()
    fb = mod._build_feedback({"instruction_type": "Cell-Level Manipulation",
                              "answer_position": "C2:C3"},
                             [0, 0, 0], [], [1, 2, 3], True, None,
                             ["COVERAGE: the target range spans 2 cell(s); your output has a value in 0 of them."])
    assert "COVERAGE" in fb and "did not match" in fb


def test_localization_runs_only_on_a_miss_and_only_once():
    """Scoring opens workbooks; doing this for every passing task would be wasted work."""
    src = (ADAPTER_DIR / "adapter.py").read_text(encoding="utf-8")
    seg = src.split("localized: list[str] = []", 1)[1].split("feedback = _build_feedback", 1)[0]
    assert "if mismatched:" in seg
    assert "idx = mismatched[0]" in seg, "one case is enough; the diagnosis generalizes"
    assert "except Exception" in seg, "must never cost a score"
