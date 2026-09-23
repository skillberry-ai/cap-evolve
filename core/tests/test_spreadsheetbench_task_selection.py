"""Which tasks a tier runs, and that it runs ALL of them.

Two coupled concerns:

1. THE SMOKE TIER'S TASKS MUST BE PART OF `full_verified`. Smoke is the cheap signal that
   guards the tiers we actually report. It was drawn from the 200-task sample with no relation
   to the reported roster, and that is how the verified-release scoring bug survived: smoke ran
   three graded cases per task on `sample_200` and passed, while `full_verified` would have
   scored 0.000 on all 400 tasks. Constraining smoke to `full_verified`'s roster means a green
   smoke says something about the tier whose numbers get published.

2. A REQUESTED TASK THAT IS NOT IN THE DATASET MUST FAIL LOUDLY. `_load_dataset` filtered the
   dataset down to `SPREADSHEETBENCH_TASK_IDS` and only complained when NONE matched — so a
   tier listing ten ids of which three were absent silently ran seven, and nothing downstream
   noticed: `assert_run.py` checks the infra-failure FRACTION, not the task count, so a
   shrunken run looks like a clean one. That was survivable while each tier's tasks.json was
   built from its own dataset. It is not survivable now: smoke's roster is derived from
   `full_verified`'s (a different archive), so a task present in one and absent from the other
   is exactly the mistake this must catch.
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "templates" / "adapters" / "spreadsheetbench"
BENCH = REPO / "ci" / "benchmarks" / "spreadsheetbench"
SMOKE = BENCH / "smoke" / "tasks.json"
VERIFIED = BENCH / "full_verified"


def _load_adapter_module():
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_adapter_select", ADAPTER_DIR / "adapter.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_adapter_module()


def _ids(path: Path) -> list[str]:
    return [str(e["id"]) for e in json.loads(path.read_text(encoding="utf-8"))]


# --- 1. the smoke roster ------------------------------------------------------------------


def test_every_smoke_task_is_in_the_full_verified_tier():
    """A green smoke must say something about the tier whose numbers get published."""
    smoke, verified = set(_ids(SMOKE)), set(_ids(VERIFIED / "tasks.json"))
    stray = sorted(smoke - verified)
    assert not stray, (
        f"{len(stray)} smoke tasks are not in full_verified, so smoke can pass while that tier "
        f"is broken: {stray}"
    )


def test_smoke_never_touches_the_full_verified_sealed_test_split():
    """Smoke runs a real (if short) optimization. Drawing it from the split whose score is
    reported would let smoke tune against sealed tasks — the same reason pilot is restricted to
    full's train ids."""
    split = json.loads((VERIFIED / "split_ids.json").read_text(encoding="utf-8"))
    smoke = set(_ids(SMOKE))
    leaked = sorted(smoke & {str(i) for i in split["test"]})
    assert not leaked, f"smoke tasks sit in full_verified's SEALED test split: {leaked}"


def test_smoke_is_drawn_from_the_full_verified_train_split():
    split = json.loads((VERIFIED / "split_ids.json").read_text(encoding="utf-8"))
    smoke = set(_ids(SMOKE))
    assert smoke <= {str(i) for i in split["train"]}, (
        "smoke must come from full_verified's TRAIN ids, so neither reported split is touched"
    )


def test_smoke_keeps_both_instruction_types_represented():
    """Cell-Level and Sheet-Level exercise different adapter paths (a single cell vs a range,
    and different comparison logic). A smoke set of only one type stops guarding the other."""
    entries = json.loads((VERIFIED / "tasks.json").read_text(encoding="utf-8"))
    by_id = {str(e["id"]): e for e in entries}
    assert all(i in by_id for i in _ids(SMOKE))
    # instruction_type lives in the dataset, not in tasks.json, so assert via the committed
    # generator's recorded choice instead: both types must be present in the smoke set.
    types = {e.get("type") for e in json.loads(SMOKE.read_text(encoding="utf-8"))}
    assert types >= {"cell", "sheet"}, (
        f"smoke must cover both instruction types, got {types} — regenerate with make_smoke.py"
    )


def test_smoke_still_has_enough_tasks_to_be_a_signal():
    ids = _ids(SMOKE)
    assert len(ids) == 10, f"smoke is calibrated at 10 tasks, found {len(ids)}"
    assert len(set(ids)) == len(ids), "duplicate smoke task ids"


def test_smoke_pins_one_agent_model():
    tasks = json.loads(SMOKE.read_text(encoding="utf-8"))
    assert len({t["agent"] for t in tasks}) == 1


# --- 2. a requested task that is absent must fail loudly ----------------------------------


def _dataset(tmp: Path, ids: list[str]) -> Path:
    root = tmp / "ds"
    (root / "spreadsheet").mkdir(parents=True)
    (root / "dataset.json").write_text(
        json.dumps([{"id": i, "instruction": "x", "spreadsheet_path": f"spreadsheet/{i}",
                     "instruction_type": "Cell-Level Manipulation", "answer_position": "A1"}
                    for i in ids]), encoding="utf-8")
    return root


def _load_with(mod, dataset_root: Path, task_ids: list[str]):
    saved = (mod.DATA_DIR, mod.TASK_IDS, mod._dataset_cache)
    try:
        mod.DATA_DIR, mod.TASK_IDS, mod._dataset_cache = str(dataset_root), list(task_ids), None
        return mod._load_dataset()
    finally:
        mod.DATA_DIR, mod.TASK_IDS, mod._dataset_cache = saved


def test_a_requested_task_missing_from_the_dataset_is_an_error(mod):
    """The silent-shrink bug: 10 ids requested, 7 present, run proceeds on 7 and looks clean."""
    with tempfile.TemporaryDirectory() as td:
        root = _dataset(Path(td), ["a", "b", "c"])
        with pytest.raises(RuntimeError) as e:
            _load_with(mod, root, ["a", "b", "zzz"])
        msg = str(e.value)
        assert "zzz" in msg, f"the error must name the missing id, got: {msg}"
        assert "SPREADSHEETBENCH_TASK_IDS" in msg or "dataset" in msg


def test_the_error_names_every_missing_id_not_just_the_first(mod):
    with tempfile.TemporaryDirectory() as td:
        root = _dataset(Path(td), ["a"])
        with pytest.raises(RuntimeError) as e:
            _load_with(mod, root, ["a", "p", "q"])
        assert "p" in str(e.value) and "q" in str(e.value)


def test_requesting_exactly_the_available_tasks_still_works(mod):
    with tempfile.TemporaryDirectory() as td:
        root = _dataset(Path(td), ["a", "b", "c"])
        got = _load_with(mod, root, ["a", "c"])
        assert [str(e["id"]) for e in got] == ["a", "c"]


def test_requesting_nothing_loads_the_whole_dataset(mod):
    """Regression: an empty SPREADSHEETBENCH_TASK_IDS means "all tasks", not "none"."""
    with tempfile.TemporaryDirectory() as td:
        root = _dataset(Path(td), ["a", "b"])
        assert len(_load_with(mod, root, [])) == 2
