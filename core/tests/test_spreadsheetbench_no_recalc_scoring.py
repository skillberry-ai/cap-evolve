"""SpreadsheetBench scores every output twice: as the agent saved it, and after LibreOffice recalc.

The reward stays the recalculated comparison. The un-recalculated one is how SkillOpt's evaluator
(and the WikiSkill paper, which matches its setup) scores — a formula cell reads back as None — so
recording it lets a run be put next to those papers' numbers without a second run.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "templates" / "adapters" / "spreadsheetbench"

FORMULA = b"PK-formula-uncached"
RECALCED = b"PK-formula-recalculated"


def _load_adapter_module():
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_adapter_norecalc", ADAPTER_DIR / "adapter.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_adapter_module()


def _score(mod, *, written: bytes, keep: bool = False, libre: bool = True):
    """Score one verified-400 task whose comparison passes only on the recalculated bytes."""
    from cap_evolve import Rollout, Task

    td = tempfile.mkdtemp()
    root = Path(td) / "spreadsheetbench_verified_400"
    d = root / "spreadsheet" / "13-1"
    d.mkdir(parents=True)
    (d / "1_13-1_init.xlsx").write_bytes(b"PK")
    (d / "1_13-1_golden.xlsx").write_bytes(b"PK")
    (root / "dataset.json").write_text("[]", encoding="utf-8")
    entry = {"id": "13-1", "instruction": "x", "spreadsheet_path": "spreadsheet/13-1",
             "instruction_type": "Cell-Level Manipulation", "answer_position": "H3:H5"}
    run_tag = "13-1_0_deadbeef"
    out_dir = root / "outputs" / run_tag
    out_dir.mkdir(parents=True)
    (out_dir / "1_13-1_output.xlsx").write_bytes(written)

    def recalc(path, soffice, **_):
        Path(path).write_bytes(RECALCED)
        return True

    saved = (mod.DATA_DIR, mod.SCORING, mod.KEEP_OUTPUTS, mod._dataset_cache,
             dict(mod._Vendor._mod), mod._recalc_workbook)
    try:
        mod.DATA_DIR = str(root)
        mod.SCORING = "hard"
        mod.KEEP_OUTPUTS = keep
        mod._dataset_cache = [entry]
        mod._recalc_workbook = recalc
        mod._Vendor._mod = {
            "compare_workbooks": lambda gt, proc, *a, **k: (Path(proc).read_bytes() == RECALCED, None),
            "find_libreoffice": (lambda: "/usr/bin/soffice") if libre else (lambda: None),
        }
        score = mod.Adapter().score(Task(id="13-1"),
                                    Rollout(task_id="13-1", output="", metadata={"run_tag": run_tag}))
        return score, out_dir
    finally:
        (mod.DATA_DIR, mod.SCORING, mod.KEEP_OUTPUTS, mod._dataset_cache,
         mod._Vendor._mod, mod._recalc_workbook) = saved


def _metric(score, name):
    return next(m["value"] for m in score.metrics if m["name"] == name)


def test_a_formula_answer_passes_recalculated_and_fails_as_saved(mod):
    score, _ = _score(mod, written=FORMULA)
    assert score.reward == 1.0
    assert score.raw["test_case_results"] == [1]
    assert score.raw["test_case_results_no_recalc"] == [0]
    assert _metric(score, "hard_no_recalc") == 0.0
    assert _metric(score, "soft_no_recalc") == 0.0


def test_a_literal_answer_passes_both_ways(mod):
    score, _ = _score(mod, written=RECALCED)
    assert score.reward == 1.0
    assert _metric(score, "hard_no_recalc") == 1.0


def test_no_recalc_metrics_are_never_primary(mod):
    score, _ = _score(mod, written=FORMULA)
    primaries = [m["name"] for m in score.metrics if m["primary"]]
    assert primaries == ["hard_restriction"]


def test_outputs_are_deleted_by_default(mod):
    _, out_dir = _score(mod, written=FORMULA)
    assert not out_dir.exists()


def test_keep_outputs_keeps_both_the_recalculated_and_the_saved_workbook(mod):
    _, out_dir = _score(mod, written=FORMULA, keep=True)
    assert (out_dir / "1_13-1_output.xlsx").read_bytes() == RECALCED
    assert (out_dir / "1_13-1_output.norecalc.xlsx").read_bytes() == FORMULA
