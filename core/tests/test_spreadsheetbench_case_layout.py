"""How many graded test cases a task has, and what its files are called, comes from DISK.

SpreadsheetBench ships in two incompatible on-disk layouts, and the adapter was written
against only the first:

  original 912 (v0.1)   3 graded cases per task, `{idx}_{sid}_input.xlsx` / `_answer.xlsx`
  verified 400          1 graded case  per task, `1_{sid}_init.xlsx`   / `_golden.xlsx`
                        …except 5 tasks (13284, 32023, 32789, 56274, 58109) which ship
                        bare `initial.xlsx` / `golden.xlsx` with no index or id prefix.

Hardcoding `for idx in (1, 2, 3)` and the `_input`/`_answer` suffixes is not a graceful
degradation on the verified set — it is a silent, total failure. Case 1's answer resolves to
a nonexistent `_answer.xlsx` so even a perfect solve mismatches; cases 2 and 3 are missing so
they score 0; and `hard = all(test_results)` is therefore 0.0 for all 400 tasks. That is the
shape of the $77 / 3h zero-score run the mount preflight was written for (30691123806), with
no error message this time — just a plausible-looking 0.000.

The verified 400 is also NOT a subset you can approximate by filtering the 912 archive:
226 of its 400 instructions were rewritten, 4 answer_positions changed, and 61 of its golden
workbooks differ from the corresponding 912 answer. It must be fetched as its own archive.
"""

import importlib.util
import os
import stat
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "templates" / "adapters" / "spreadsheetbench"


def _load_adapter_module():
    """Import the adapter template for its pure helpers (see test_spreadsheetbench_mount_perms)."""
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_adapter_cases", ADAPTER_DIR / "adapter.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_adapter_module()


XLSX = b"PK\x03\x04"


def _v1_task(root: Path, sid: str = "110-2") -> Path:
    """The original 912 layout: three indexed input/answer pairs."""
    d = root / "spreadsheet" / sid
    d.mkdir(parents=True)
    for idx in (1, 2, 3):
        (d / f"{idx}_{sid}_input.xlsx").write_bytes(XLSX)
        (d / f"{idx}_{sid}_answer.xlsx").write_bytes(XLSX)
    return d


def _verified_task(root: Path, sid: str = "13-1") -> Path:
    """The verified 400 layout: ONE case, named init/golden."""
    d = root / "spreadsheet" / sid
    d.mkdir(parents=True)
    (d / f"1_{sid}_init.xlsx").write_bytes(XLSX)
    (d / f"1_{sid}_golden.xlsx").write_bytes(XLSX)
    return d


def _bare_task(root: Path, sid: str = "13284") -> Path:
    """The five verified tasks whose files carry no index or id prefix at all."""
    d = root / "spreadsheet" / sid
    d.mkdir(parents=True)
    (d / "initial.xlsx").write_bytes(XLSX)
    (d / "golden.xlsx").write_bytes(XLSX)
    return d


# --- how many cases is this task graded on? ----------------------------------------------


def test_case_indices_finds_all_three_cases_in_the_original_912_layout(mod):
    with tempfile.TemporaryDirectory() as td:
        d = _v1_task(Path(td))
        assert mod._case_indices(d, "110-2") == [1, 2, 3]


def test_case_indices_finds_the_single_case_in_the_verified_400_layout(mod):
    """The whole bug: 3 hardcoded cases against a 1-case dataset scores 0 on every task."""
    with tempfile.TemporaryDirectory() as td:
        d = _verified_task(Path(td))
        assert mod._case_indices(d, "13-1") == [1]


def test_case_indices_finds_one_case_for_the_bare_filename_tasks(mod):
    with tempfile.TemporaryDirectory() as td:
        d = _bare_task(Path(td))
        assert mod._case_indices(d, "13284") == [1]


def test_case_indices_falls_back_to_case_one_for_a_task_dir_with_no_inputs(mod):
    """A genuinely broken task dir must still surface as a normal missing-file MISS —
    an empty case list would make `all([])` True and score it a silent PASS."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "spreadsheet" / "9999"
        d.mkdir(parents=True)
        assert mod._case_indices(d, "9999") == [1]


# --- what are this case's files called? ---------------------------------------------------


def test_resolve_case_file_reads_the_verified_400_init_and_golden_names(mod):
    with tempfile.TemporaryDirectory() as td:
        d = _verified_task(Path(td))
        assert mod._resolve_case_file(d, 1, "13-1", "input") == d / "1_13-1_init.xlsx"
        assert mod._resolve_case_file(d, 1, "13-1", "answer") == d / "1_13-1_golden.xlsx"


def test_resolve_case_file_reads_the_bare_initial_and_golden_names(mod):
    with tempfile.TemporaryDirectory() as td:
        d = _bare_task(Path(td))
        assert mod._resolve_case_file(d, 1, "13284", "input") == d / "initial.xlsx"
        assert mod._resolve_case_file(d, 1, "13284", "answer") == d / "golden.xlsx"


def test_bare_filenames_are_only_accepted_for_the_first_case(mod):
    """`initial.xlsx` is case 1's input. Letting cases 2/3 fall back to it would grade a
    replay against the WRONG workbook instead of recording an honest missing-file miss."""
    with tempfile.TemporaryDirectory() as td:
        d = _bare_task(Path(td))
        assert mod._resolve_case_file(d, 2, "13284", "input") == d / "2_13284_input.xlsx"
        assert not mod._resolve_case_file(d, 2, "13284", "input").exists()


def test_resolve_case_file_still_prefers_the_912_canonical_names(mod):
    """Regression: the original layout must resolve exactly as before."""
    with tempfile.TemporaryDirectory() as td:
        d = _v1_task(Path(td))
        assert mod._resolve_case_file(d, 2, "110-2", "input") == d / "2_110-2_input.xlsx"
        assert mod._resolve_case_file(d, 3, "110-2", "answer") == d / "3_110-2_answer.xlsx"


def test_resolve_case_file_still_tolerates_the_912_stray_space_and_xlsm_quirks(mod):
    """Regression: a few 912 ids ship `2_<sid>_input .xlsx` or `.xlsm`."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "2_1000_input .xlsx").write_bytes(XLSX)
        (d / "3_1000_input.xlsm").write_bytes(XLSX)
        assert mod._resolve_case_file(d, 2, "1000", "input") == d / "2_1000_input .xlsx"
        assert mod._resolve_case_file(d, 3, "1000", "input") == d / "3_1000_input.xlsm"


def test_resolve_case_file_tolerates_an_upstream_id_typo_in_a_filename(mod):
    """Verified task 42930 ships its golden as `1_43930_golden.xlsx` — a digit typo, and 43930
    is not a task id in any release. It is the only such file in the 400, and without this it
    is the one task in the tier that can never score."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "1_42930_init.xlsx").write_bytes(XLSX)
        (d / "1_43930_golden.xlsx").write_bytes(XLSX)
        assert mod._resolve_case_file(d, 1, "42930", "answer") == d / "1_43930_golden.xlsx"
        assert mod._resolve_case_file(d, 1, "42930", "input") == d / "1_42930_init.xlsx"


def test_an_ambiguous_filename_is_never_guessed(mod):
    """Tolerating a typo is only safe while the choice is unique. Two candidates means we do
    not know which one grades this task, so take the honest miss instead of guessing."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "1_43930_golden.xlsx").write_bytes(XLSX)
        (d / "1_43931_golden.xlsx").write_bytes(XLSX)
        assert mod._resolve_case_file(d, 1, "42930", "answer") == d / "1_42930_answer.xlsx"


def test_the_typo_fallback_cannot_steal_case_ones_file_for_a_later_case(mod):
    """912 tasks 43026, 46444 and 4714 ship ONE case. If case 2 could fall back to the only
    `*_answer.xlsx` in the dir, it would be graded against case 1's answer — a fabricated
    result where a missing-file miss belongs."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "1_43026_input.xlsx").write_bytes(XLSX)
        (d / "1_43026_answer.xlsx").write_bytes(XLSX)
        assert mod._resolve_case_file(d, 2, "43026", "answer") == d / "2_43026_answer.xlsx"
        assert not mod._resolve_case_file(d, 2, "43026", "answer").exists()


def test_case_indices_reports_the_short_case_count_of_a_defective_912_task(mod):
    """4 of the 912 tasks ship fewer than 3 cases (43026, 46444, 4714 with one; 52964 with
    two) — all four in the sealed test split. Hardcoding three made them UNWINNABLE at hard
    scoring: the missing cases scored 0 no matter what the agent produced."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "1_52964_input.xlsx").write_bytes(XLSX)
        (d / "2_52964_input.xlsx").write_bytes(XLSX)
        assert mod._case_indices(d, "52964") == [1, 2]


def test_resolve_case_file_falls_back_to_the_canonical_name_when_nothing_matches(mod):
    """Regression: a missing file must stay a normal miss, not an exception."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        assert mod._resolve_case_file(d, 4, "1000", "input") == d / "4_1000_input.xlsx"


# --- the mount preflight probe ------------------------------------------------------------


def test_input_probe_finds_a_workbook_in_the_verified_400_layout(mod):
    """The probe globbed `*/*_input.xls*`. On the verified set that matches NOTHING, so the
    readability check silently no-ops — losing the guard that exists because a non-traversable
    mount once cost $77 and 3h at 0.000."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _verified_task(root)
        probe = mod._input_probe(root)
        assert probe is not None, "no input workbook found — the mount check would be skipped"
        assert probe.name == "1_13-1_init.xlsx"


def test_input_probe_finds_a_workbook_in_the_912_layout(mod):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _v1_task(root)
        probe = mod._input_probe(root)
        assert probe is not None and probe.name.endswith("_input.xlsx")


def test_preflight_widens_an_unreadable_verified_400_workbook(mod):
    """Proves the probe is actually consulted on the verified layout: an o-unreadable input
    workbook must be healed, which can only happen if the probe found it."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "spreadsheetbench_verified_400"
        d = _verified_task(root)
        (root / "dataset.json").write_text("[]", encoding="utf-8")
        wb = d / "1_13-1_init.xlsx"
        os.chmod(wb, 0o600)
        mod._preflight_mount(root)
        assert os.stat(wb).st_mode & stat.S_IROTH, "input workbook was never widened"


# --- scoring -----------------------------------------------------------------------------


def _score_one_case(mod, *, scoring: str, case_ok: bool):
    """Score a rollout on a verified-400-shaped task with a stubbed comparison.

    Everything here is real adapter code except `compare_workbooks` (the vendored
    cell-by-cell comparison, which needs openpyxl and real workbooks) and LibreOffice.
    """
    from cap_evolve import Rollout, Task

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "spreadsheetbench_verified_400"
        _verified_task(root, "13-1")
        entry = {
            "id": "13-1",
            "instruction": "irrelevant",
            "spreadsheet_path": "spreadsheet/13-1",
            "instruction_type": "Cell-Level Manipulation",
            "answer_position": "H3:H5",
        }
        (root / "dataset.json").write_text("[]", encoding="utf-8")

        run_tag = "13-1_0_deadbeef"
        out_dir = root / "outputs" / run_tag
        out_dir.mkdir(parents=True)
        (out_dir / "1_13-1_output.xlsx").write_bytes(XLSX)

        saved = (mod.DATA_DIR, mod.SCORING, mod._dataset_cache, dict(mod._Vendor._mod))
        try:
            mod.DATA_DIR = str(root)
            mod.SCORING = scoring
            mod._dataset_cache = [entry]
            mod._Vendor._mod = {
                "compare_workbooks": lambda *a, **k: (case_ok, None),
                "find_libreoffice": lambda: None,   # skip recalc; irrelevant to enumeration
            }
            adapter = mod.Adapter()
            task = Task(id="13-1")
            rollout = Rollout(task_id="13-1", output="", metadata={"run_tag": run_tag})
            return adapter.score(task, rollout)
        finally:
            mod.DATA_DIR, mod.SCORING, mod._dataset_cache, mod._Vendor._mod = saved


def test_a_solved_task_gets_the_full_hard_score_on_a_single_case_dataset(mod):
    """The bug, end to end: the same rollout scored 0.0 because cases 2 and 3 do not exist."""
    score = _score_one_case(mod, scoring="hard", case_ok=True)
    assert score.reward == 1.0, f"solved task scored {score.reward} — missing cases counted as misses"
    assert score.raw["test_case_results"] == [1], "graded more cases than the dataset ships"


def test_a_failed_task_still_scores_zero_on_a_single_case_dataset(mod):
    score = _score_one_case(mod, scoring="hard", case_ok=False)
    assert score.reward == 0.0
    assert score.raw["test_case_results"] == [0]


def test_soft_and_hard_agree_when_the_dataset_ships_one_case(mod):
    """With a single graded case, matches/n and all-of-n are the same number by construction —
    so a verified-400 result is directly comparable to published `hard` scores."""
    soft = _score_one_case(mod, scoring="soft", case_ok=True)
    hard = _score_one_case(mod, scoring="hard", case_ok=True)
    assert soft.reward == hard.reward == 1.0
    by_name = {m["name"]: m["value"] for m in soft.metrics}
    assert by_name["soft_restriction"] == by_name["hard_restriction"] == 1.0


def test_feedback_counts_only_the_cases_the_dataset_ships(mod):
    score = _score_one_case(mod, scoring="hard", case_ok=True)
    assert "1/1 test cases passed" in score.feedback
    assert "1/3" not in score.feedback


# --- the replay of the solution onto the remaining cases ----------------------------------


def test_replay_rewrites_both_the_input_and_the_output_filename(mod):
    """Refactor guard for the 912 path: cases 2/3 are produced by re-running the agent's
    final block with the input and output names substituted, and no new LLM call."""
    code = "wb = load('1_110-2_input.xlsx')\nwb.save('1_110-2_output.xlsx')"
    out = mod._replay_code(code, "1_110-2_input.xlsx", "2_110-2_input.xlsx", "110-2", 2)
    assert out == "wb = load('2_110-2_input.xlsx')\nwb.save('2_110-2_output.xlsx')"


def test_replay_handles_the_verified_400_input_names(mod):
    """The substitution is driven by the resolved filenames, not by an assumed suffix."""
    code = "wb = load('1_13-1_init.xlsx')\nwb.save('1_13-1_output.xlsx')"
    out = mod._replay_code(code, "1_13-1_init.xlsx", "2_13-1_init.xlsx", "13-1", 2)
    assert "2_13-1_init.xlsx" in out and "2_13-1_output.xlsx" in out


# --- the prompt's "other graded copies" block ---------------------------------------------


def test_sibling_inputs_names_the_other_two_copies_in_the_912_layout(mod):
    """Refactor guard: the agent is told where the other graded copies are."""
    with tempfile.TemporaryDirectory() as td:
        d = _v1_task(Path(td))
        txt = mod._sibling_inputs(d, "110-2", "/mnt/data/spreadsheet/110-2")
        assert "2_110-2_input.xlsx" in txt and "3_110-2_input.xlsx" in txt


def test_sibling_inputs_says_nothing_when_there_is_only_one_graded_copy(mod):
    """On the verified set the whole paragraph must vanish — telling the agent its code will
    be 'replayed on two other copies' that do not exist is a prompt defect, and the
    one-input constraint it imposes is not needed."""
    with tempfile.TemporaryDirectory() as td:
        d = _verified_task(Path(td))
        assert mod._sibling_inputs(d, "13-1", "/mnt/data/spreadsheet/13-1") == ""
