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

Sparse feedback was only half the problem. Feedback measured against the WRONG REFERENCE is the
other half, and it is worse: on 90 of the 912 tasks (10.1%) the expected output fills under a
quarter of answer_position, so comparing the agent's fill to the SPAN told a perfect answer that
it had "left most of the target range unfilled". Task 56427 was scolded that way while its real
defects went unnamed. This is the same defect class as the TYPE advice that used to point the
wrong way — and fixing that one is what finally moved the val ceiling past 0.580.

GOLD SAFETY. Coverage of the agent's own output and the untouched-sheet note still never open
the gold. Three signals do: a value's TYPE, the expected FILL COUNT (one integer per range), and
the MISMATCH classes (how many cells differ, in which category). All three are metadata ABOUT
the answer — a count, a type, a category — never the answer. No cell value is ever emitted;
test_no_gold_value_leaks_through_the_mismatch_note asserts it.
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


# --- the dataset's own quoting quirks ----------------------------------------------------
#
# MEASURED on all 912 tasks: 23 (2.5%) of answer_position strings do not match the strict
# notation, in seven families. Every localization signal AND the agent-facing TARGET SIZE line
# route through _range_cells, so a part it cannot read makes the task silently invisible: on
# pilot 30906175891, task 450-9 got the one-sentence feedback #289 existed to eliminate, and
# its prompt carried no TARGET SIZE line at all while every well-formed task's did.


def test_a_stray_quote_before_the_range_is_tolerated():
    """Task 450-9's real notation — the apostrophe lands before the range, not after the sheet."""
    mod = _adapter()
    assert list(mod._range_cells("'Data'!'A2:C150")) == [("Data", 1, 2, 3, 150)]
    assert list(mod._range_cells("'Sheet2'!'B7:C22")) == [("Sheet2", 2, 7, 3, 22)]


def test_a_bang_inside_the_sheet_quotes_is_tolerated():
    """The largest family (16 of the 23): the ! is quoted along with the sheet name."""
    mod = _adapter()
    assert list(mod._range_cells("'Vendor!'A1:D101,'NotPaid!'A1:D7")) == [
        ("Vendor", 1, 1, 4, 101), ("NotPaid", 1, 1, 4, 7)]


def test_a_whole_part_wrapped_in_quotes_is_tolerated():
    """Task 172-10: the quotes wrap sheet AND range together."""
    mod = _adapter()
    assert list(mod._range_cells("'T_Data!A1:AB700','NY_Data!A1:AB30'")) == [
        ("T_Data", 1, 1, 28, 700), ("NY_Data", 1, 1, 28, 30)]


def test_a_sheet_named_twice_keeps_the_range():
    """Task 532-3: "'Received'!'Received!A1:G16'" names the sheet on both sides of the bang."""
    mod = _adapter()
    assert list(mod._range_cells("'Received'!'Received!A1:G16'")) == [("Received", 1, 1, 7, 16)]


def test_a_missing_end_column_repeats_the_start_column():
    """Task 73-45: "BD2:308" means BD2:BD308 — a column, not a truncated range."""
    mod = _adapter()
    assert list(mod._range_cells("'Sheet1'!BD2:308")) == [("Sheet1", 56, 2, 56, 308)]


def test_a_full_width_colon_is_tolerated():
    """Task 37456 was authored with U+FF1A rather than ASCII colon."""
    mod = _adapter()
    assert list(mod._range_cells("G12：J15")) == [(None, 7, 12, 10, 15)]


def test_a_column_only_range_is_still_skipped_deliberately():
    """"A:G" names no rows, and _range_cells has no workbook to ask for the extent.

    One task (of 912) is affected. Inventing a bound would corrupt the COVERAGE denominator
    for it, which is the exact class of defect this PR removes elsewhere — so it stays
    skipped, and stays documented.
    """
    mod = _adapter()
    assert list(mod._range_cells("Sheet3'!A:G,'Sheet4'!A:G")) == []


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
    """Task 19-7's shape: a 5,200-row range whose answer really does fill it, 10 cells written."""
    mod = _adapter()
    src = _book(tmp_path / "in.xlsx", {"P": {}})
    out = _book(tmp_path / "out.xlsx", {"P": {(r, 2): r for r in range(2, 12)}})
    gold = _book(tmp_path / "gold.xlsx", {"P": {(r, 2): r for r in range(2, 5201)}})
    notes = mod._localize_failure({"answer_position": "'P'!B2:B5200"}, out, src, gold)
    joined = " ".join(notes)
    assert "spans 5199 cell(s)" in joined and "value in 10 of them" in joined
    assert "Most of the expected answer is missing" in joined


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


# --- COVERAGE must be measured against the expected output, not the span -----------------
#
# MEASURED across all 912 tasks: on 90 of them (10.1%) the expected output fills less than a
# QUARTER of answer_position, and on 203 (22.8%) less than 60%. The old note compared the
# agent's fill to the span, so on those tasks a PERFECT answer was told "Most of the target
# range was left unfilled". Task 56427 in pilot 30906175891 got exactly that: it filled 15
# cells, the expected output fills 20, the span is 324 — scolded for ~300 cells it was never
# supposed to write, while its real defects (14 numbers written as text, 5 cells left empty)
# went unnamed.


def test_coverage_states_the_expected_fill_and_withholds_the_false_scold(tmp_path):
    """Task 56427's measured shape: span 324, expected fill 20, agent fill 15."""
    mod = _adapter()
    src = _book(tmp_path / "in.xlsx", {"S": {}})
    out = _book(tmp_path / "out.xlsx", {"S": {(r, 1): r for r in range(2, 17)}})
    gold = _book(tmp_path / "gold.xlsx", {"S": {(r, 1): r for r in range(2, 22)}})
    notes = mod._localize_failure({"answer_position": "'S'!A1:A324"}, out, src, gold)
    joined = " ".join(notes)
    assert "spans 324 cell(s)" in joined
    assert "expected output has a value in 20" in joined, "the real denominator must be stated"
    assert "Most of the target range was left unfilled" not in joined, \
        "15 of an expected 20 is not an unfilled range"


# The scold's surviving case — a range whose answer really does fill it — is covered by
# test_partial_coverage_of_a_large_range_is_flagged above, now measured against the expected fill.


def test_coverage_makes_no_fill_claim_when_the_gold_cannot_be_read(tmp_path):
    """Without the expected fill there is no honest claim to make, so none is made."""
    mod = _adapter()
    src = _book(tmp_path / "in.xlsx", {"S": {}})
    out = _book(tmp_path / "out.xlsx", {"S": {(2, 1): 1}})
    notes = mod._localize_failure({"answer_position": "'S'!A1:A400"}, out, src,
                                  tmp_path / "does-not-exist.xlsx")
    joined = " ".join(notes)
    assert "spans 400 cell(s)" in joined
    assert "expected output has a value in" not in joined
    assert "Most of the target range was left unfilled" not in joined


# --- MISMATCH: how many cells differ, and in which named class ---------------------------
#
# MEASURED on pilot 30906175891: 11 of the champion's 17 failures received the line "the target
# range spans N cell(s); your output has a value in N of them" and NOTHING else — the range was
# fully covered and the types matched, so every existing signal was silent. Replaying each
# candidate's own final code against the gold shows what that silence hid: task 56637 differed
# in 1 cell of 146, 5192 in 1 of 3, 11842 in 2 of 96. "1 of 146 cells differs" and "wrong" are
# different instructions to an optimizer.


def test_mismatch_states_how_many_cells_differ(tmp_path):
    """Task 56637's measured shape: 146 cells covered, exactly one wrong."""
    mod = _adapter()
    cells = {(r, 2): "2nd Shift" for r in range(12, 158)}
    src = _book(tmp_path / "in.xlsx", {"S": dict(cells)})
    gold = _book(tmp_path / "gold.xlsx", {"S": dict(cells)})
    wrong = dict(cells); wrong[(33, 2)] = "1st Shift"
    out = _book(tmp_path / "out.xlsx", {"S": wrong})
    notes = mod._localize_failure({"answer_position": "'S'!B12:B157"}, out, src, gold)
    joined = " ".join(notes)
    assert "MISMATCH: 1 of 146 cell(s) differ" in joined
    assert "original input" in joined, "the cell was changed although the input was already right"


def test_the_correct_value_stored_as_text_is_named(tmp_path):
    """Tasks 325-44 (15 cells) and 56427 (14): the value is RIGHT, the storage type is not."""
    mod = _adapter()
    src = _book(tmp_path / "in.xlsx", {"S": {}})
    out = _book(tmp_path / "out.xlsx", {"S": {(1, 1): "98", (2, 1): "66"}})
    gold = _book(tmp_path / "gold.xlsx", {"S": {(1, 1): 98, (2, 1): 66}})
    notes = mod._localize_failure({"answer_position": "'S'!A1:A2"}, out, src, gold)
    joined = " ".join(notes)
    assert "2 cell(s) hold the CORRECT value stored as text" in joined


def test_an_excel_error_text_the_agent_wrote_is_named(tmp_path):
    """Task 55931: 8 cells hold the literal string "#N/A" while its own helpers could do the sum.

    The value quoted here is the AGENT's, not the gold's — naming it is what turns "str where
    int was expected" into a rule the optimizer can write.
    """
    mod = _adapter()
    src = _book(tmp_path / "in.xlsx", {"S": {}})
    out = _book(tmp_path / "out.xlsx", {"S": {(1, 1): "#N/A", (2, 1): "#N/A"}})
    gold = _book(tmp_path / "gold.xlsx", {"S": {(1, 1): 4, (2, 1): 6}})
    notes = mod._localize_failure({"answer_position": "'S'!A1:A2"}, out, src, gold)
    joined = " ".join(notes)
    assert "#N/A" in joined and "Excel error text" in joined
    for leaked in ("4", "6"):
        assert f" {leaked} " not in joined.replace("A1:A2", ""), "no gold value"


def test_a_cell_expected_to_stay_unresolved_is_named(tmp_path):
    """Task 57232's inverse case: the expected value IS #N/A and the agent computed a number.

    Today's TYPE advice tells it to "KEEP the original text" — impossible, the input cell is
    empty. Naming the class is the only way that rule can be learned.
    """
    mod = _adapter()
    src = _book(tmp_path / "in.xlsx", {"S": {}})
    out = _book(tmp_path / "out.xlsx", {"S": {(1, 1): 0.25, (2, 1): 1.75}})
    gold = _book(tmp_path / "gold.xlsx", {"S": {(1, 1): "#N/A", (2, 1): "#N/A"}})
    notes = mod._localize_failure({"answer_position": "'S'!A1:A2"}, out, src, gold)
    joined = " ".join(notes)
    assert "2 cell(s) expect an Excel error text" in joined


def test_values_written_past_the_end_of_the_answer_are_named(tmp_path):
    """Task 50051: 29 of 32 cells hold a value the expected output leaves empty — and the old
    COVERAGE line called that "32 of 32", which reads like success."""
    mod = _adapter()
    src = _book(tmp_path / "in.xlsx", {"S": {}})
    out = _book(tmp_path / "out.xlsx", {"S": {(r, 1): r for r in range(2, 34)}})
    gold = _book(tmp_path / "gold.xlsx", {"S": {(r, 1): r for r in range(2, 5)}})
    notes = mod._localize_failure({"answer_position": "'S'!A2:A33"}, out, src, gold)
    joined = " ".join(notes)
    assert "29 cell(s) hold a value where the expected output has none" in joined


def test_a_truncated_string_is_named_as_a_prefix(tmp_path):
    """Task 5192: wrote '1456CH02' where '1456CH02A' was expected — its own slice cut one char."""
    mod = _adapter()
    src = _book(tmp_path / "in.xlsx", {"S": {}})
    out = _book(tmp_path / "out.xlsx", {"S": {(2, 2): "1456CH02"}})
    gold = _book(tmp_path / "gold.xlsx", {"S": {(2, 2): "1456CH02A"}})
    notes = mod._localize_failure({"answer_position": "'S'!B2"}, out, src, gold)
    assert "PREFIX of the expected text" in " ".join(notes)


def test_numeric_direction_is_reported_only_when_every_difference_agrees(tmp_path):
    """Task 11842: 2 of 96 cells wrong, both LOW — a pointer at undercounting."""
    mod = _adapter()
    src = _book(tmp_path / "in.xlsx", {"S": {}})
    out = _book(tmp_path / "out.xlsx", {"S": {(1, 1): 2, (2, 1): 1}})
    gold = _book(tmp_path / "gold.xlsx", {"S": {(1, 1): 4, (2, 1): 2}})
    low = " ".join(mod._localize_failure({"answer_position": "'S'!A1:A2"}, out, src, gold))
    assert "LOWER than expected" in low

    mixed_out = _book(tmp_path / "out2.xlsx", {"S": {(1, 1): 2, (2, 1): 9}})
    mixed = " ".join(mod._localize_failure({"answer_position": "'S'!A1:A2"}, mixed_out, src, gold))
    assert "LOWER than expected" not in mixed, "a direction claim needs every cell to agree"


def test_no_gold_value_leaks_through_the_mismatch_note(tmp_path):
    """The invariant that keeps this diagnostic honest: classes and counts, never answers."""
    mod = _adapter()
    src = _book(tmp_path / "in.xlsx", {"S": {}})
    out = _book(tmp_path / "out.xlsx", {"S": {(1, 1): 1, (2, 1): "x", (3, 1): None}})
    gold = _book(tmp_path / "gold.xlsx", {"S": {(1, 1): 987654,
                                                (2, 1): "SECRETSTRING", (3, 1): 424242}})
    joined = " ".join(mod._localize_failure({"answer_position": "'S'!A1:A3"}, out, src, gold))
    for leaked in ("987654", "SECRETSTRING", "424242"):
        assert leaked not in joined


def test_a_scan_cap_is_disclosed_rather_than_silent(tmp_path):
    """Four tasks of 912 span more than 50,000 cells. A cap is fine; a silent cap is not."""
    mod = _adapter()
    setattr(mod, "_CELL_SCAN_CAP", 4)
    src = _book(tmp_path / "in.xlsx", {"S": {}})
    out = _book(tmp_path / "out.xlsx", {"S": {(r, 1): 1 for r in range(1, 11)}})
    gold = _book(tmp_path / "gold.xlsx", {"S": {(r, 1): 2 for r in range(1, 11)}})
    joined = " ".join(mod._localize_failure({"answer_position": "'S'!A1:A10"}, out, src, gold))
    assert "first 4" in joined and "inspected" in joined


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
