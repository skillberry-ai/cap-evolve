"""Protected-paths tamper guard (#142).

Adversarial case: an optimizer that edits the project's grader (adapters/adapter.py)
must make the run FAIL with a message naming the tampered file, log a
``tamper_detected`` event, and never advance the candidate or seal the test split.

Negative case (the one that matters more): a legitimate candidate edit — the mock
optimizer changing the capability under optimization — must NOT be flagged. A guard
that blocks normal runs is worse than no guard.
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
MOCK_RUN = REPO / "skills" / "optimizers" / "run-optimizer" / "scripts" / "run.py"

sys.path.insert(0, str(CORE))


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    os.environ["CAPEVOLVE_MOCK_SCRIPT"] = str(EXAMPLE / "mock_script.json")
    yield
    os.environ.clear()
    os.environ.update(old)


def _toy_adapter():
    spec = importlib.util.spec_from_file_location("toy_calc_adapter_prot", EXAMPLE / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Adapter()


def _project(tmp_path: Path, *, extra_yaml: str = "") -> tuple[Path, Path, Path]:
    """A realistic project layout: .capevolve/project + seed capability.

    Returns ``(base, project_dir, seed_dir)`` where ``base`` is the ``.capevolve``
    dir the run dir is created under — so ``protect.project_dir_for`` finds the
    project the same way a real run does.
    """
    base = tmp_path / ".capevolve"
    project = base / "project"
    (project / "adapters").mkdir(parents=True)
    shutil.copy(EXAMPLE / "adapter.py", project / "adapters" / "adapter.py")
    shutil.copy(EXAMPLE / "tasks.jsonl", project / "tasks.jsonl")
    (project / "capevolve.yaml").write_text(
        "capability_path: seed_capability\ndataset_source: tasks.jsonl\n" + extra_yaml,
        encoding="utf-8")
    seed = project / "seed_capability"
    shutil.copytree(EXAMPLE / "capability", seed)
    return base, project, seed


def _mock_optimizer():
    from cap_evolve import harness
    return harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}",
         "--prompt", "{prompt}"])


def _tamper_optimizer(grader: Path):
    """An optimizer that edits the GRADER instead of the capability (reward hacking)."""
    def _run(workdir, instructions):  # noqa: ARG001
        src = grader.read_text(encoding="utf-8")
        # "make score() always return 1.0" — the classic reward hack
        grader.write_text(src.replace("reward=1.0 if ok else 0.0", "reward=1.0"),
                          encoding="utf-8")
        return None
    return _run


# ---- unit level ------------------------------------------------------------

def test_defaults_protect_grader_and_data_not_the_capability(tmp_path):
    from cap_evolve import protect
    _, project, _ = _project(tmp_path)
    files = protect.resolve_protected(project)
    assert "adapters/adapter.py" in files, "the grader must be protected"
    assert "capevolve.yaml" in files
    assert "tasks.jsonl" in files, "dataset_source must be protected"
    assert not any(f.startswith("seed_capability/") for f in files), \
        "the capability under optimization must NOT be protected"


def test_override_replaces_defaults(tmp_path):
    from cap_evolve import protect
    _, project, _ = _project(tmp_path, extra_yaml="protected_paths: [tasks.jsonl]\n")
    files = protect.resolve_protected(project)
    assert set(files) == {"tasks.jsonl"}


def test_pycache_never_protected(tmp_path):
    """Importing the adapter writes adapters/__pycache__/*.pyc during a NORMAL run —
    hashing that would flag every legitimate run."""
    from cap_evolve import protect
    _, project, _ = _project(tmp_path)
    pyc = project / "adapters" / "__pycache__" / "adapter.cpython-311.pyc"
    pyc.parent.mkdir(parents=True)
    pyc.write_bytes(b"\x00compiled")
    assert not any("__pycache__" in f for f in protect.resolve_protected(project))
    assert protect.is_protected(project, pyc) is False
    assert protect.is_protected(project, project / "adapters" / "adapter.py") is True


def test_content_hash_not_mtime(tmp_path):
    """A same-size, same-mtime edit is still caught — mtime alone is spoofable."""
    from cap_evolve import RunDir, protect
    base, project, _ = _project(tmp_path)
    run_dir = RunDir.create(base, ts="hash")
    protect.ensure_manifest(run_dir, project)
    target = project / "tasks.jsonl"
    st = target.stat()
    body = target.read_text(encoding="utf-8")
    target.write_text(body.replace('"target": "7"', '"target": "9"'), encoding="utf-8")
    assert len(target.read_text(encoding="utf-8")) == len(body), "same size on purpose"
    os.utime(target, (st.st_atime, st.st_mtime))  # spoof mtime back
    with pytest.raises(protect.TamperError) as ei:
        protect.verify(run_dir, project)
    assert "tasks.jsonl" in str(ei.value)


# ---- end to end ------------------------------------------------------------

def test_adversarial_optimizer_editing_the_grader_fails_the_run(tmp_path):
    from cap_evolve import Budget, RunDir, TamperError, harness
    base, project, seed = _project(tmp_path)
    adapter = _toy_adapter()
    run_dir = RunDir.create(base, ts="tamper", budget=Budget(max_iterations=3))
    harness.ensure_splits(adapter, run_dir, seed=0)
    b = harness.baseline(adapter, seed, run_dir=run_dir)
    assert b.reward == 0.0
    best_before = run_dir.best_id

    grader = project / "adapters" / "adapter.py"
    with pytest.raises(TamperError) as ei:
        harness.run_step(
            adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir("seed"),
            optimizer=_tamper_optimizer(grader), instructions="(hack the grader)",
            current_val=b, project_dir=project,
            gate_kwargs={"mode": "significant", "k_se": 1.0},
        )

    msg = str(ei.value)
    assert "TAMPER DETECTED" in msg
    assert "adapters/adapter.py" in msg, "the message must NAME the tampered file"

    events = [json.loads(l) for l in
              run_dir.events_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    tampers = [e for e in events if e["kind"] == "tamper_detected"]
    assert len(tampers) == 1
    assert tampers[0]["changes"][0] == {
        "path": "adapters/adapter.py", "change": "modified",
        "expected_sha256": tampers[0]["changes"][0]["expected_sha256"],
        "actual_sha256": tampers[0]["changes"][0]["actual_sha256"],
    }
    assert (tampers[0]["changes"][0]["expected_sha256"]
            != tampers[0]["changes"][0]["actual_sha256"])

    # The candidate could not advance...
    assert run_dir.best_id == best_before
    # ...and the test split was never sealed, so the headline number is unspendable
    # on a tampered grader.
    assert run_dir.read_splits().test_used is False
    with pytest.raises(TamperError):
        harness.finalize(adapter, run_dir=run_dir,
                         best_dir=run_dir.candidate_dir(run_dir.best_id))
    assert run_dir.read_splits().test_used is False


def test_legitimate_candidate_edit_is_not_flagged(tmp_path):
    """The real mock optimizer editing the CAPABILITY must run clean to a sealed test."""
    from cap_evolve import Budget, RunDir, harness
    base, project, seed = _project(tmp_path)
    adapter = _toy_adapter()
    run_dir = RunDir.create(base, ts="clean", budget=Budget(max_iterations=3))
    harness.ensure_splits(adapter, run_dir, seed=0)
    b = harness.baseline(adapter, seed, run_dir=run_dir)

    step = harness.run_step(
        adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir("seed"),
        optimizer=_mock_optimizer(), instructions="improve val pass rate",
        current_val=b, project_dir=project,
        gate_kwargs={"mode": "significant", "k_se": 1.0},
    )
    assert step["accepted"] is True, "a legitimate edit must not be blocked"
    payload = harness.finalize(adapter, run_dir=run_dir,
                              best_dir=run_dir.candidate_dir(run_dir.best_id),
                              baseline_dir=run_dir.candidate_dir("seed"))
    assert payload["test"]["reward"] == 1.0

    events = [json.loads(l) for l in
              run_dir.events_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert not [e for e in events if e["kind"] == "tamper_detected"], \
        "NO false positive on a normal run"
    assert [e for e in events if e["kind"] == "protected_manifest"], \
        "the manifest must have been recorded"


def test_no_project_dir_is_a_silent_noop(tmp_path):
    """Bare unit-test / library use (no .capevolve/project) must be unaffected."""
    from cap_evolve import RunDir, harness
    adapter = _toy_adapter()
    seed = tmp_path / "seed"
    shutil.copytree(EXAMPLE / "capability", seed)
    run_dir = RunDir.create(tmp_path / "nowhere", ts="bare")
    harness.ensure_splits(adapter, run_dir, seed=0)
    assert harness.baseline(adapter, seed, run_dir=run_dir).reward == 0.0
    assert not (run_dir.root / "protected.json").exists()


def test_deleted_and_added_protected_files_are_caught(tmp_path):
    from cap_evolve import RunDir, protect
    base, project, _ = _project(tmp_path)
    run_dir = RunDir.create(base, ts="delta")
    protect.ensure_manifest(run_dir, project)
    (project / "tasks.jsonl").unlink()
    (project / "adapters" / "sneaky_scorer.py").write_text("# extra grader\n", encoding="utf-8")
    with pytest.raises(protect.TamperError) as ei:
        protect.verify(run_dir, project)
    msg = str(ei.value)
    assert "deleted tasks.jsonl" in msg
    assert "added adapters/sneaky_scorer.py" in msg


def test_dashboard_surfaces_tamper_events(tmp_path):
    from cap_evolve import RunDir, protect
    from cap_evolve.dashboard import reduce_run
    base, project, _ = _project(tmp_path)
    run_dir = RunDir.create(base, ts="dash")
    protect.ensure_manifest(run_dir, project)
    (project / "tasks.jsonl").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(protect.TamperError):
        protect.verify(run_dir, project, context="unit")
    summary = reduce_run(run_dir)["summary"]
    assert len(summary["tamper_events"]) == 1
    assert summary["tamper_events"][0]["context"] == "unit"


def test_hook_blocks_a_protected_write(tmp_path):
    """The PreToolUse honesty hook denies the write early (core still enforces)."""
    sys.path.insert(0, str(REPO / "plugins" / "cap-evolve" / "hooks"))
    import importlib
    hook = importlib.import_module("deny_sealed_edits")
    from cap_evolve import RunDir, harness
    base, project, _ = _project(tmp_path)
    run_dir = RunDir.create(base, ts="hook")
    harness.ensure_splits(_toy_adapter(), run_dir, seed=0)
    os.environ["CAPEVOLVE_RUN_DIR"] = str(run_dir.root)
    try:
        blocked = hook.decide({"tool_name": "Edit", "cwd": str(base),
                               "tool_input": {"file_path": str(project / "adapters" / "adapter.py")}})
        allowed = hook.decide({"tool_name": "Edit", "cwd": str(base),
                               "tool_input": {"file_path": str(project / "seed_capability" / "prompt.txt")}})
    finally:
        os.environ.pop("CAPEVOLVE_RUN_DIR", None)
    assert blocked == 2, "editing the grader must be blocked"
    assert allowed == 0, "editing the capability must be allowed"
