"""The agent's sandbox must not be able to see the gold answers (issue #782), and separating the gold
from the agent's mount must not change a single score.

* unit: the gold-free "agent view" built by SPREADSHEETBENCH_AGENT_VIEW=1 holds inputs and a writable
  outputs/ and no answer/golden workbook, in both dataset layouts (912: `_answer`, verified-400: `_golden`).
* equivalence: the REAL vendored comparator scores the same fixed outputs identically with gold inside the
  mounted dir (historical), via AGENT_VIEW, and via an explicit SPREADSHEETBENCH_GOLD_DIR.
* provenance: LibreOffice version / REWARD_RECALC / evaluation.py hash are recorded on every score.
* sandbox: when a docker-compatible runtime and the executor image are present, code running in the container
  lists the task directory and finds no gold file. Skips cleanly otherwise.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")
pytest.importorskip("numpy")
pytest.importorskip("tqdm")

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "templates" / "adapters" / "spreadsheetbench"
HARNESS = REPO / "third_party" / "spreadsheetbench"
GOLD_RE = re.compile(r"(_answer|_golden|^golden|^answer)", re.I)


def _load():
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_adapter_goldiso", ADAPTER_DIR / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "HARNESS_DIR", str(HARNESS))
    monkeypatch.setattr(m, "_dataset_cache", None)
    monkeypatch.setattr(m, "_VIEWS", {})
    monkeypatch.setattr(m, "TASK_IDS", [])
    monkeypatch.setattr(m, "SCORING", "hard")
    monkeypatch.setattr(m, "KEEP_OUTPUTS", False)
    monkeypatch.setattr(m, "REWARD_RECALC", False)
    monkeypatch.setattr(m, "_libreoffice_bin", lambda: None)   # no recalculation: deterministic, no soffice needed
    monkeypatch.setattr(m, "_PROVENANCE", None)
    return m


def _wb(path: Path, value):
    wb = openpyxl.Workbook()
    wb.active["A1"] = value
    wb.save(path)


def _dataset(root: Path, layout: str):
    """Two tiny tasks. layout 'v400' (init/golden, 1 case) or 'x912' (input/answer, 1 case here)."""
    inp, gold = ("init", "golden") if layout == "v400" else ("input", "answer")
    entries = []
    for sid in ("t1", "t2"):
        d = root / "spreadsheet" / sid
        d.mkdir(parents=True)
        _wb(d / f"1_{sid}_{inp}.xlsx", "input")
        _wb(d / f"1_{sid}_{gold}.xlsx", "ANSWER-" + sid)
        (d / "prompt.txt").write_text("prompt")
        entries.append({"id": sid, "instruction": "i", "spreadsheet_path": f"spreadsheet/{sid}",
                        "instruction_type": "Cell-Level Manipulation", "answer_position": "A1"})
    (root / "dataset.json").write_text(json.dumps(entries), encoding="utf-8")
    return entries


def _tree_files(root: Path):
    return [p for p in root.rglob("*") if p.is_file()]


@pytest.mark.parametrize("layout", ["v400", "x912"])
def test_agent_view_has_no_gold_and_a_writable_outputs_dir(mod, monkeypatch, tmp_path, layout):
    src = tmp_path / "src"
    _dataset(src, layout)
    monkeypatch.setattr(mod, "DATA_DIR", str(src))
    monkeypatch.setattr(mod, "AGENT_VIEW", True)
    monkeypatch.setattr(mod, "GOLD_DIR", "")
    view = mod._data_dir()
    assert view != src
    assert (view / "dataset.json").is_file()
    files = _tree_files(view)
    assert files and not [p for p in files if GOLD_RE.search(p.name)], files
    assert {p.name for p in (view / "spreadsheet" / "t1").iterdir()} >= {"prompt.txt"}
    assert (view / "outputs").is_dir() and (view / "outputs").stat().st_mode & 0o777 == 0o777
    # the scorer still finds the gold, in the pristine dir
    assert mod._gold_dir() == src
    assert [p for p in _tree_files(src) if GOLD_RE.search(p.name)]   # source untouched


def test_agent_view_honours_task_ids_and_is_built_once(mod, monkeypatch, tmp_path):
    src = tmp_path / "src"
    _dataset(src, "v400")
    monkeypatch.setattr(mod, "DATA_DIR", str(src))
    monkeypatch.setattr(mod, "AGENT_VIEW", True)
    monkeypatch.setattr(mod, "TASK_IDS", ["t2"])
    v1 = mod._data_dir()
    assert v1 is not None and v1 == mod._data_dir()
    assert {p.name for p in (v1 / "spreadsheet").iterdir()} == {"t2"}


def test_default_behaviour_is_unchanged_without_the_flags(mod, monkeypatch, tmp_path):
    src = tmp_path / "src"
    _dataset(src, "v400")
    monkeypatch.setattr(mod, "DATA_DIR", str(src))
    monkeypatch.setattr(mod, "AGENT_VIEW", False)
    monkeypatch.setattr(mod, "GOLD_DIR", "")
    assert mod._data_dir() == src and mod._gold_dir() == src


def _score_all(mod, monkeypatch, src: Path, *, view: bool, explicit_gold: bool):
    """Write fixed outputs into whatever dir the sandbox would write to, then score them."""
    from cap_evolve import Rollout, Task

    monkeypatch.setattr(mod, "DATA_DIR", str(src))
    monkeypatch.setattr(mod, "_dataset_cache", None)
    monkeypatch.setattr(mod, "_VIEWS", {})
    monkeypatch.setattr(mod, "AGENT_VIEW", view)
    monkeypatch.setattr(mod, "GOLD_DIR", "")
    if explicit_gold:
        mod._VIEWS.clear()
        v = mod._build_agent_view(src, src.parent / "explicit_view")
        monkeypatch.setattr(mod, "DATA_DIR", str(v))
        monkeypatch.setattr(mod, "GOLD_DIR", str(src))
    data = mod._data_dir()
    out = {}
    for sid, written in (("t1", "ANSWER-t1"), ("t2", "WRONG"), ("t3", None)):
        tag = f"{sid}_0_{uuid.uuid4().hex[:6]}"
        if sid == "t3":                      # unknown task id -> "Unknown task id." path is not what we test
            continue
        d = data / "outputs" / tag
        d.mkdir(parents=True)
        _wb(d / f"1_{sid}_output.xlsx", written)
        s = mod.Adapter().score(Task(id=sid), Rollout(task_id=sid, output="", metadata={"run_tag": tag, "id": sid}))
        out[sid] = (s.reward, {m["name"]: m["value"] for m in s.metrics}, s.raw["test_case_results"])
    # a task whose output file is missing
    tag = "t1_0_missing"
    (data / "outputs" / tag).mkdir(parents=True)
    s = mod.Adapter().score(Task(id="t1"), Rollout(task_id="t1", output="", metadata={"run_tag": tag, "id": "t1"}))
    out["t1_missing"] = (s.reward, {m["name"]: m["value"] for m in s.metrics}, s.raw["test_case_results"])
    return out


@pytest.mark.parametrize("layout", ["v400", "x912"])
def test_scores_are_identical_with_gold_separated(mod, monkeypatch, tmp_path, layout):
    historical_src = tmp_path / "a" / "src"
    view_src = tmp_path / "b" / "src"
    explicit_src = tmp_path / "c" / "src"
    for p in (historical_src, view_src, explicit_src):
        _dataset(p, layout)
    base = _score_all(mod, monkeypatch, historical_src, view=False, explicit_gold=False)
    viewed = _score_all(mod, monkeypatch, view_src, view=True, explicit_gold=False)
    explicit = _score_all(mod, monkeypatch, explicit_src, view=False, explicit_gold=True)
    assert base["t1"][0] == 1.0 and base["t2"][0] == 0.0 and base["t1_missing"][0] == 0.0   # fixed expectations
    assert viewed == base
    assert explicit == base


def test_the_score_records_how_it_was_produced(mod, monkeypatch, tmp_path):
    src = tmp_path / "src"
    _dataset(src, "v400")
    monkeypatch.setattr(mod, "REWARD_RECALC", True)
    monkeypatch.setattr(mod, "_libreoffice_bin", lambda: "/nonexistent/soffice-for-test")
    from cap_evolve import Rollout, Task
    monkeypatch.setattr(mod, "DATA_DIR", str(src))
    monkeypatch.setattr(mod, "AGENT_VIEW", True)
    monkeypatch.setattr(mod, "_recalc_workbook", lambda *a, **k: True)
    data = mod._data_dir()
    d = data / "outputs" / "t1_0_x"
    d.mkdir(parents=True)
    _wb(d / "1_t1_output.xlsx", "ANSWER-t1")
    s = mod.Adapter().score(Task(id="t1"), Rollout(task_id="t1", output="", metadata={"run_tag": "t1_0_x", "id": "t1"}))
    info = s.raw["scorer"]
    assert info["reward_recalc"] is True
    assert info["gold_separate_from_agent_mount"] is True
    assert info["evaluation_py_sha256"] == __import__("hashlib").sha256(
        (HARNESS / "evaluation" / "evaluation.py").read_bytes()).hexdigest()
    assert "libreoffice_version" in info and "libreoffice_bin" in info   # None when the binary cannot run


# ---------------------------------------------------------------------------------------------
# real sandbox (needs a docker-compatible API and the executor image already pulled; never pulls it)
# ---------------------------------------------------------------------------------------------

def _runtime_or_skip():
    docker = pytest.importorskip("docker")
    pytest.importorskip("tornado")
    try:
        c = docker.from_env()
        c.ping()
        c.images.get("docker.io/xingyaoww/codeact-executor")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no docker-compatible runtime with the executor image: {type(e).__name__}")


@pytest.mark.parametrize("agent_view,expect_gold", [(False, True), (True, False)])
def test_sandbox_listing_shows_gold_only_without_the_agent_view(mod, monkeypatch, tmp_path, agent_view, expect_gold):
    _runtime_or_skip()
    src = tmp_path / "src"
    _dataset(src, "v400")
    for p in [src, *src.rglob("*")]:
        os.chmod(p, 0o755 if p.is_dir() else 0o644)
    monkeypatch.setattr(mod, "DATA_DIR", str(src))
    monkeypatch.setattr(mod, "AGENT_VIEW", agent_view)
    monkeypatch.setattr(mod, "GOLD_DIR", "")
    monkeypatch.setattr(mod, "_dataset_cache", None)
    monkeypatch.setattr(mod, "_VIEWS", {})
    mod._preflight_mount(mod._data_dir())
    sb = mod._get_sandbox()
    conv = mod._sanitize_conv_id("goldiso-" + uuid.uuid4().hex[:6])
    try:
        out = sb.execute(conv, "import os\nprint('LS', sorted(os.listdir('/mnt/data/spreadsheet/t1')))")
    finally:
        sb.release(conv)
        sb.shutdown()
    listing = out[out.index("LS"):]
    assert ("golden" in listing) is expect_gold, listing
    assert "1_t1_init.xlsx" in listing           # the input is always there
