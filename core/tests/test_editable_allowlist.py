"""The allow-list seal (#871): ``editable_paths`` / ``run_step(editable_patterns=...)``.

What is proved here:

* ``integrity.snapshot_files`` + ``verify`` flag a changed or deleted sealed file, and allow
  additions (the optimizer's own scratch);
* ``sealed_capability_files`` seals every seed file that is not editable, and never the
  framework/optimizer working files;
* in ``run_step`` a candidate that edits only editable files is measured normally, one that
  changes a sealed file is INDECISIVE and costs no rollouts, scratch files are fine, and the
  optimizer is told which files are which;
* off by default: no ``editable_patterns`` ⇒ no sealed manifest.
"""

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "toy_calc"

sys.path.insert(0, str(CORE))

GATE = {"mode": "significant", "k_se": 1.0}


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    yield
    os.environ.clear()
    os.environ.update(old)


def _toy_adapter():
    spec = importlib.util.spec_from_file_location("toy_calc_adapter", EXAMPLE / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Adapter()


class CountingAdapter:
    def __init__(self, inner):
        self._inner = inner
        self.rollouts = 0

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def run_target(self, task, ctx, *, seed: int = 0):
        self.rollouts += 1
        return self._inner.run_target(task, ctx, seed=seed)


def _fresh_run(tmp_path: Path, adapter, ts: str):
    """Toy capability + a FRAME file that the allow-list must seal."""
    from cap_evolve import Budget, RunDir, harness
    seed = tmp_path / ts / "seed_capability"
    shutil.copytree(EXAMPLE / "capability", seed)
    (seed / "frame.md").write_text("FIXED FRAME\n", encoding="utf-8")
    rd = RunDir.create(tmp_path / ts / ".capevolve", ts=ts,
                       budget=__import__("cap_evolve").Budget(max_iterations=5, stall=2))
    harness.ensure_splits(adapter, rd, seed=0)
    return rd, harness.baseline(adapter, seed, run_dir=rd)


def _fix_prompt(workdir: Path, instructions: str):
    p = workdir / "prompt.txt"
    p.write_text(p.read_text(encoding="utf-8") + "\n[CALC] Compute and output only the number.\n",
                 encoding="utf-8")


def _edit_frame(workdir: Path, instructions: str):
    _fix_prompt(workdir, instructions)
    p = workdir / "frame.md"
    p.unlink()
    p.write_text("I REWROTE THE FRAME\n", encoding="utf-8")


def _events(run_dir, kind):
    out = []
    for line in (run_dir.root / "events.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip() and json.loads(line).get("kind") == kind:
            out.append(json.loads(line))
    return out


# --- integrity ---------------------------------------------------------------

def test_snapshot_files_flags_changes_and_removals_but_allows_additions(tmp_path):
    from cap_evolve import integrity
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "b.md").write_text("b", encoding="utf-8")
    man = integrity.snapshot_files(tmp_path, ["a.md", "b.md", "missing.md"])
    assert sorted(man["files"]) == ["a.md", "b.md"]           # a missing name is not sealed
    assert integrity.verify(man, tmp_path).ok

    (tmp_path / "scratch.py").write_text("print(1)", encoding="utf-8")
    assert integrity.verify(man, tmp_path).ok                  # additions are scratch

    (tmp_path / "a.md").write_text("A", encoding="utf-8")
    (tmp_path / "b.md").unlink()
    rep = integrity.verify(man, tmp_path)
    assert not rep.ok and rep.modified == ["a.md"] and rep.removed == ["b.md"] and rep.added == []


def test_glob_manifests_keep_their_old_semantics(tmp_path):
    """The existing deny-list manifest still reports additions — unchanged by this PR."""
    from cap_evolve import integrity
    (tmp_path / "gold.json").write_text("{}", encoding="utf-8")
    man = integrity.snapshot(tmp_path, ["*gold*"])
    (tmp_path / "gold2.json").write_text("{}", encoding="utf-8")
    assert integrity.verify(man, tmp_path).added == ["gold2.json"]


# --- which files are sealed -------------------------------------------------

def test_sealed_capability_files_skips_editable_and_working_files(tmp_path):
    from cap_evolve import harness
    for rel in ("prompt.md", "guidance.md", "task_frame.md", "lib/helper.py", "JOURNAL.md",
                "PROCESS.md", "INSTRUCTIONS.md", "trajectories/t1.json", "lib/__pycache__/x.pyc"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    sealed = harness.sealed_capability_files(tmp_path, ("prompt.md", "guidance.md"))
    assert sealed == ["lib/helper.py", "task_frame.md"]


def test_parse_editable_paths():
    from cap_evolve import harness
    assert harness.parse_editable_paths("") is None
    assert harness.parse_editable_paths(None) is None
    assert harness.parse_editable_paths("prompt.md, guidance.md") == ("prompt.md", "guidance.md")
    assert harness.parse_editable_paths(["a", " ", "b"]) == ("a", "b")


# --- wiring into run_step ---------------------------------------------------

def test_default_off_writes_no_sealed_manifest(tmp_path):
    from cap_evolve import harness
    adapter = _toy_adapter()
    rd, base = _fresh_run(tmp_path, adapter, "off")
    step = harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                            optimizer=_edit_frame, instructions="x", current_val=base,
                            gate_kwargs=GATE)
    assert step["candidate_val"] is not None
    assert not list((rd.root / "work").glob("*.sealed.json"))


def test_editing_only_editable_files_is_measured_and_told(tmp_path):
    from cap_evolve import harness
    adapter = _toy_adapter()
    rd, base = _fresh_run(tmp_path, adapter, "clean")
    seen = {}

    def optimizer(workdir, instructions):
        seen["instructions"] = instructions
        _fix_prompt(workdir, instructions)
        (workdir / "notes.md").write_text("my scratch", encoding="utf-8")   # allowed

    step = harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                            optimizer=optimizer, instructions="improve", current_val=base,
                            gate_kwargs=GATE, editable_patterns=("prompt.txt",))
    assert step["candidate_val"] is not None and step["accepted"] is True
    assert "## Editable files" in seen["instructions"]
    assert "`prompt.txt`" in seen["instructions"] and "`frame.md`" in seen["instructions"]
    ev = _events(rd, "capability_sealed")
    assert ev and ev[0]["sealed"] == ["frame.md"] and ev[0]["editable"] == ["prompt.txt"]


def test_changing_a_sealed_file_is_indecisive_and_costs_nothing(tmp_path):
    from cap_evolve import harness
    adapter = CountingAdapter(_toy_adapter())
    rd, base = _fresh_run(tmp_path, adapter, "tamper")
    best_before, stall_before, rollouts_before = rd.best_id, rd.spent.stall, adapter.rollouts
    step = harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                            optimizer=_edit_frame, instructions="improve", current_val=base,
                            gate_kwargs=GATE, editable_patterns=("prompt.txt",))
    assert step["candidate_val"] is None
    assert step["decision"]["indecisive"] is True and step["accepted"] is False
    assert adapter.rollouts == rollouts_before            # verified BEFORE any rollout
    assert rd.best_id == best_before and rd.spent.stall == stall_before
    assert _events(rd, "tamper_detected")
