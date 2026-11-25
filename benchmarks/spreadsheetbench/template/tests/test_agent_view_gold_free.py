"""#782: the folder the agent's sandbox mounts at /mnt/data must hold no gold workbook, while the scorer still
reads gold from the pristine dataset and scores exactly as before. No model, no docker.

Run: PYTHONPATH=core python -m pytest benchmarks/spreadsheetbench/template/tests -q
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

REPO = Path(__file__).resolve().parents[4]
ADAPTER_DIR = REPO / "benchmarks" / "spreadsheetbench" / "template"
HARNESS = REPO / "benchmarks" / "spreadsheetbench" / "harness"
GOLD_RE = re.compile(r"(golden|answer)", re.I)


def _load():
    for p in (REPO / "core", ADAPTER_DIR, REPO / "benchmarks" / "_shared"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_adapter_viewtest", ADAPTER_DIR / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod(monkeypatch, tmp_path):
    for k in ("SPREADSHEETBENCH_AGENT_VIEW", "SPREADSHEETBENCH_ALLOW_GOLD_IN_MOUNT",
              "SPREADSHEETBENCH_GOLD_DIR", "SPREADSHEETBENCH_AGENT_VIEW_DIR"):
        monkeypatch.delenv(k, raising=False)
    m = _load()
    for name, val in (("HARNESS_DIR", str(HARNESS)), ("_dataset_cache", None), ("_VIEWS", {}),
                      ("_MOUNT_CHECKED", set()), ("TASK_IDS", []), ("AGENT_VIEW", True),
                      ("ALLOW_GOLD_IN_MOUNT", False), ("GOLD_DIR", ""), ("AGENT_VIEW_DIR", ""),
                      ("DATA_DIR", str(tmp_path / "src"))):
        monkeypatch.setattr(m, name, val)
    return m


def _wb(path: Path, value):
    wb = openpyxl.Workbook()
    wb.active["A1"] = value
    wb.save(path)


def _dataset(root: Path, ids=("t1", "t2")):
    entries = []
    for sid in ids:
        d = root / "spreadsheet" / sid
        d.mkdir(parents=True)
        _wb(d / f"1_{sid}_init.xlsx", "input")
        _wb(d / f"1_{sid}_golden.xlsx", "ANSWER-" + sid)
        (d / "prompt.txt").write_text("prompt")
        entries.append({"id": sid, "instruction": "i", "spreadsheet_path": f"spreadsheet/{sid}",
                        "instruction_type": "Cell-Level Manipulation", "answer_position": "A1"})
    (root / "dataset.json").write_text(json.dumps(entries), encoding="utf-8")


def test_the_mounted_folder_holds_no_golden_file_and_gold_stays_with_the_scorer(mod, tmp_path):
    src = tmp_path / "src"
    _dataset(src)
    view = mod._data_dir()                 # what the sandbox bind-mounts at /mnt/data
    assert view.resolve() != src.resolve()
    files = [p for p in view.rglob("*") if p.is_file()]
    assert (view / "spreadsheet" / "t1" / "1_t1_init.xlsx") in files
    assert not [p for p in files if GOLD_RE.search(p.name)], files
    assert (view / "outputs").is_dir()
    # the scorer resolves gold from the pristine dataset, which still has it
    gold = mod._resolve_case_file(mod._gold_dir() / "spreadsheet" / "t1", 1, "t1", "answer")
    assert gold is not None and gold.name == "1_t1_golden.xlsx" and gold.parent.parent.parent == src


@pytest.mark.parametrize("bad", ["..", ".", "", "../t1", "a/b", "a\\b", "/etc", "x\x00y"])
def test_a_task_id_that_is_not_a_plain_name_is_refused(mod, tmp_path, bad):
    src = tmp_path / "src"
    _dataset(src, ids=("t1",))
    entries = json.loads((src / "dataset.json").read_text())
    entries.append(dict(entries[0], id=bad))
    (src / "dataset.json").write_text(json.dumps(entries))
    with pytest.raises(RuntimeError, match="not a plain directory name"):
        mod._load_dataset()


def test_plain_task_ids_still_load(mod, tmp_path):
    _dataset(tmp_path / "src", ids=("t1", "13284", "a-b_c"))
    assert [str(e["id"]) for e in mod._load_dataset()] == ["t1", "13284", "a-b_c"]
