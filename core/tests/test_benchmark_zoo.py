"""The benchmark zoo: declarative manifest, ``add`` scaffold, and a verifier that
actually verifies.

The point of these tests is the last part. Every guard in this epic that measured
the wrong artifact passed its own test vacuously, so each breakage case below
*breaks a real benchmark* and asserts ``verify`` fails on it with an actionable
message — a stubbed ``score()``, a non-deterministic ``run_target()``, a dataset too
small for an honest gate, and a missing dataset file.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
ZOO = REPO / "benchmarks"
sys.path.insert(0, str(CORE))

from cap_evolve import zoo  # noqa: E402


@pytest.fixture
def bench(tmp_path):
    """A working copy of the bundled toy_calc zoo entry."""
    d = tmp_path / "toy_calc"
    shutil.copytree(ZOO / "toy_calc", d)
    shutil.rmtree(d / "__pycache__", ignore_errors=True)
    shutil.rmtree(d / "project" / "__pycache__", ignore_errors=True)
    (d / zoo.STAMP_NAME).unlink(missing_ok=True)
    return d


# --- manifest ---------------------------------------------------------------


def test_manifest_rejects_unknown_key(tmp_path):
    p = tmp_path / zoo.MANIFEST_NAME
    p.write_text("name: x\ntasks_fil: tasks.jsonl\n", encoding="utf-8")
    with pytest.raises(zoo.BenchmarkError) as e:
        zoo.load_manifest(p)
    assert "tasks_fil" in str(e.value), "a typo'd key must not be silently ignored"


def test_manifest_rejects_bad_scoring_and_direction(tmp_path):
    p = tmp_path / zoo.MANIFEST_NAME
    p.write_text("name: x\nscoring: fuzzy\n", encoding="utf-8")
    with pytest.raises(zoo.BenchmarkError, match="fuzzy"):
        zoo.load_manifest(p)
    p.write_text("name: x\nmetric_direction: sideways\n", encoding="utf-8")
    with pytest.raises(zoo.BenchmarkError, match="metric_direction"):
        zoo.load_manifest(p)


def test_builtin_predicates():
    assert zoo.match("Paris", "paris", "exact")
    assert not zoo.match("Paris, FR", "paris", "exact")
    assert zoo.match("the capital is Paris.", "Paris", "contains")
    assert zoo.match("answer: 42", r"\d+", "regex")
    assert zoo.match("about 1,024 units", "1024", "numeric")
    assert not zoo.match("no number here", "7", "numeric")


# --- add --------------------------------------------------------------------


def test_add_scaffolds_a_benchmark_that_verifies(tmp_path):
    info = zoo.add(tmp_path / "demo", description="does the agent echo")
    files = set(info["files"])
    assert {"project/benchmark.yaml", "project/target.py", "project/tasks.jsonl",
            "project/adapters/adapter.py", "project/capevolve.yaml",
            "project/seed_capability/prompt.txt"} <= files
    # The whole adapter is a bare subclass — that IS the boilerplate reduction.
    shim = (tmp_path / "demo" / "project" / "adapters" / "adapter.py").read_text()
    assert "ManifestAdapter" in shim
    assert len([ln for ln in shim.splitlines() if ln.strip()]) <= 6
    rep = zoo.verify(tmp_path / "demo")
    assert rep.ok, rep.problems


def test_add_refuses_to_clobber_and_refresh_regenerates(tmp_path):
    zoo.add(tmp_path / "demo")
    with pytest.raises(zoo.BenchmarkError, match="already exists"):
        zoo.add(tmp_path / "demo")
    spec = tmp_path / "demo" / "project" / "capevolve.yaml"
    spec.write_text("clobbered\n", encoding="utf-8")
    zoo.add(tmp_path / "demo", refresh=True)
    assert "capability_path" in spec.read_text()


def test_generated_spec_declares_the_protected_paths(tmp_path):
    zoo.add(tmp_path / "demo")
    spec = (tmp_path / "demo" / "project" / "capevolve.yaml").read_text()
    line = next(ln for ln in spec.splitlines() if ln.startswith("protected_paths:"))
    for must in ("adapters", zoo.MANIFEST_NAME, "target.py", "tasks.jsonl"):
        assert must in line, f"{must} must be protected — it is the grader/data"


# --- the zoo index ----------------------------------------------------------


def test_zoo_index_reads_the_stamp_from_disk_not_the_manifest_flag(bench, monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_BENCHMARKS_DIR", str(bench.parent))
    mpath = bench / "project" / zoo.MANIFEST_NAME
    # The manifest *claims* verified: false, but a stamp is the evidence.
    assert "verified: false" in mpath.read_text()
    entry = next(b for b in zoo.index() if b["name"] == "toy_calc")
    assert entry["verified"] is False
    rep = zoo.verify(bench)
    assert rep.ok, rep.problems
    zoo.stamp(bench, rep)
    entry = next(b for b in zoo.index() if b["name"] == "toy_calc")
    assert entry["verified"] is True and entry["n_tasks"] == 8
    # ... and a *claimed* verified: true with no stamp is still unverified.
    (bench / zoo.STAMP_NAME).unlink()
    mpath.write_text(mpath.read_text().replace("verified: false", "verified: true"))
    assert next(b for b in zoo.index() if b["name"] == "toy_calc")["verified"] is False


def test_bundled_zoo_entry_verifies():
    rep = zoo.verify(ZOO / "toy_calc")
    assert rep.ok, rep.problems
    assert rep.n_tasks == 8 and rep.splits["test"] >= 1
    assert rep.val_reward == 0.0, "the seed prompt lacks [CALC]; headroom must exist"


# --- verify EXECUTES the benchmark ------------------------------------------


def test_verify_runs_the_real_thing_not_just_the_manifest(bench):
    rep = zoo.verify(bench)
    joined = " | ".join(rep.steps)
    assert "cap-evolve check executed" in joined
    assert "REAL smoke eval" in joined and "run_target() -> score()" in joined
    assert rep.val_reward is not None, "a parse-only verify could not produce a reward"


def test_verify_catches_a_stubbed_score(bench):
    m = bench / "project" / zoo.MANIFEST_NAME
    m.write_text(m.read_text().replace("scoring: exact", "scoring: custom"))
    t = bench / "project" / "target.py"
    t.write_text(t.read_text() + '\n\ndef score(task, rollout):\n'
                 '    raise NotImplementedError("IMPLEMENT ME: score(task, rollout)")\n')
    rep = zoo.verify(bench)
    assert not rep.ok
    assert any("unimplemented adapter methods" in p and "score" in p
               for p in rep.problems), rep.problems


def test_verify_catches_a_nondeterministic_run_target(bench):
    t = bench / "project" / "target.py"
    t.write_text(t.read_text().replace(
        "    prompt = (Path(ctx)",
        "    import random\n"
        "    return {'output': str(random.random()), 'trace': 'unseeded'}\n"
        "    prompt = (Path(ctx)"))
    rep = zoo.verify(bench)
    assert not rep.ok
    p = next(p for p in rep.problems if "NON-DETERMINISTIC" in p)
    assert "seed=0" in p and "forward `seed`" in p, p


def test_verify_refuses_a_tiny_dataset_before_the_gate_can_surprise_anyone(bench):
    """A 3-task dataset must fail loudly at verify, not mid-run inside gate.decide."""
    ds = bench / "project" / "tasks.jsonl"
    ds.write_text("\n".join(ds.read_text().splitlines()[:3]) + "\n")
    rep = zoo.verify(bench)
    assert not rep.ok
    assert any(f"below the honest-gate minimum of {zoo.MIN_VAL_TASKS}" in p
               for p in rep.problems), rep.problems
    assert any("test split is EMPTY" in p for p in rep.problems), rep.problems


def test_verify_catches_a_missing_dataset_file(bench):
    (bench / "project" / "tasks.jsonl").unlink()
    rep = zoo.verify(bench)
    assert not rep.ok
    p = " ".join(rep.problems)
    assert "dataset file missing" in p and "tasks.jsonl" in p, rep.problems


def test_verify_catches_duplicate_task_ids(bench):
    """Duplicate ids silently drop tasks and leak across splits — a hard error."""
    ds = bench / "project" / "tasks.jsonl"
    lines = ds.read_text().splitlines()
    ds.write_text("\n".join(lines + [lines[0]]) + "\n")
    rep = zoo.verify(bench)
    assert not rep.ok and "duplicate task id" in " ".join(rep.problems)


def test_verify_catches_undeclared_protected_paths(bench):
    m = bench / "project" / zoo.MANIFEST_NAME
    m.write_text(m.read_text().replace(
        "protected_paths: [adapters, benchmark.yaml, target.py, tasks.jsonl]",
        "protected_paths: [adapters]"))
    zoo.add(bench, refresh=True)  # regenerate the spec from the weakened manifest
    rep = zoo.verify(bench)
    assert not rep.ok
    assert any("protected_paths does not cover" in p for p in rep.problems), rep.problems


def test_stamp_records_measured_evidence(bench):
    rep = zoo.verify(bench)
    p = zoo.stamp(bench, rep)
    d = json.loads(p.read_text())
    assert d["ok"] is True and d["val_reward"] == 0.0 and d["n_tasks"] == 8
    assert d["dataset_sha256"] and d["steps"], "the stamp must carry the evidence"


# --- CLI --------------------------------------------------------------------


def _cli(*args, cwd=None):
    return subprocess.run([sys.executable, "-m", "cap_evolve.cli", *args],
                          capture_output=True, text=True, cwd=cwd,
                          env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(CORE)})


def test_cli_help_lists_benchmark_from_the_generated_listing():
    """`--help` renders COMMANDS + docstrings — no second literal list to go stale."""
    from cap_evolve import cli
    assert "benchmark" in cli.COMMANDS
    r = _cli("--help")
    assert "benchmark" in r.stderr
    for name in cli.COMMANDS:
        assert name in r.stderr, f"{name} missing from the generated listing"
    src = (CORE / "cap_evolve" / "cli.py").read_text()
    assert "version|splits|check|run|estimate|dashboard" not in src, \
        "the literal usage string is back — it will go stale"


def test_cli_benchmark_add_verify_roundtrip_stdout_is_one_json_object(tmp_path):
    r = _cli("benchmark", "add", "demo", "--description", "d", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    json.loads(r.stdout)  # exactly ONE object
    r = _cli("benchmark", "verify", "demo", cwd=tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["ok"] is True and out["val_reward"] is not None
    assert (tmp_path / "demo" / zoo.STAMP_NAME).is_file()


def test_cli_benchmark_verify_exits_nonzero_on_a_broken_benchmark(tmp_path):
    _cli("benchmark", "add", "demo", cwd=tmp_path)
    (tmp_path / "demo" / "project" / "tasks.jsonl").unlink()
    r = _cli("benchmark", "verify", "demo", "--no-stamp", cwd=tmp_path)
    assert r.returncode == 1
    assert json.loads(r.stdout)["ok"] is False


def test_cli_benchmark_list_shows_the_bundled_zoo(tmp_path):
    r = _cli("benchmark", "list", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    names = [b["name"] for b in json.loads(r.stdout)["benchmarks"]]
    assert "toy_calc" in names


def test_cli_benchmark_error_path_still_prints_one_json_object(tmp_path):
    r = _cli("benchmark", "verify", "nope", cwd=tmp_path)
    assert r.returncode == 1
    assert json.loads(r.stdout)["ok"] is False  # not a traceback


# --- end to end -------------------------------------------------------------


def test_zoo_benchmark_runs_end_to_end_to_a_sealed_test_number(bench, tmp_path, monkeypatch):
    """A zoo benchmark, driven by the manifest adapter, reaches a sealed test number."""
    from cap_evolve import Budget, RunDir, TestSealError, harness
    from cap_evolve.check import load_adapter

    proj = bench / "project"
    adapter = load_adapter(proj)
    seed = tmp_path / "seed"
    shutil.copytree(proj / "seed_capability", seed)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="zoo",
                            budget=Budget(max_iterations=3, stall=2))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)
    assert base.reward == 0.0, "seed prompt lacks [CALC]"

    monkeypatch.setenv("CAPEVOLVE_MOCK_SCRIPT", str(bench / "mock_script.json"))
    monkeypatch.setenv("CAPEVOLVE_CORE", str(CORE))
    optimizer = harness.optimizer_from_command([
        "python3", str(REPO / "skills" / "optimizers" / "run-optimizer" / "scripts" / "run.py"),
        "--name", "mock", "--workdir", "{workdir}", "--prompt", "{prompt}"])
    step = harness.run_step(adapter, run_dir=run_dir,
                            parent_dir=run_dir.candidate_dir("seed"),
                            optimizer=optimizer, instructions="raise val pass rate",
                            current_val=base,
                            gate_kwargs={"mode": "significant", "k_se": 1.0})
    assert step["accepted"] is True
    payload = harness.finalize(adapter, run_dir=run_dir,
                               best_dir=run_dir.candidate_dir(run_dir.best_id))
    assert payload["test"]["reward"] == 1.0
    with pytest.raises(TestSealError):
        harness.finalize(adapter, run_dir=run_dir,
                         best_dir=run_dir.candidate_dir(run_dir.best_id))


def test_custom_scoring_entry_gives_graded_partial_credit(tmp_path):
    """json_extract proves `scoring: custom` works AND the signal is non-binary."""
    from cap_evolve.check import load_adapter
    d = tmp_path / "json_extract"
    shutil.copytree(ZOO / "json_extract", d)
    shutil.rmtree(d / "project" / "__pycache__", ignore_errors=True)
    rep = zoo.verify(d)
    assert rep.ok, rep.problems
    adapter = load_adapter(d / "project")
    tasks = adapter.tasks("all")
    cap = tmp_path / "cap"
    cap.mkdir()

    def val(prompt: str) -> float:
        (cap / "prompt.txt").write_text(prompt, encoding="utf-8")
        rs = [adapter.score(t, adapter.run_target(t, cap, seed=0)).reward for t in tasks]
        return sum(rs) / len(rs)

    assert val("prose please") == 0.0
    assert val("[JSON] reply as json") == pytest.approx(1 / 3)
    assert val("[JSON] json\n[FIELDS] all fields") == 1.0


def test_every_bundled_zoo_entry_verifies_and_is_stamped():
    """The zoo is verifier-GATED: every entry must verify from a clean checkout."""
    entries = zoo.index()
    assert len(entries) >= 2, entries
    for e in entries:
        assert "error" not in e, e
        rep = zoo.verify(Path(e["dir"]))
        assert rep.ok, (e["name"], rep.problems)
        assert (Path(e["dir"]) / zoo.STAMP_NAME).is_file(), \
            f"{e['name']} ships without a verified.json stamp"
        assert e["verified"] is True, e
