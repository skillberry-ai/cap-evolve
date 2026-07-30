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


def test_verify_checks_the_generated_spec_not_the_manifest(bench):
    """B5: the guard reads capevolve.yaml, so verify must check capevolve.yaml.

    Weaken ONLY the generated spec and leave the manifest declaring all four paths.
    The old check read the manifest and reported OK while ``rep.protected`` sitting
    right next to it showed a single file — the same wrong-artifact bug as #189.
    """
    cfg = bench / "project" / "capevolve.yaml"
    cfg.write_text(cfg.read_text().replace(
        cfg.read_text().split("protected_paths: ")[1].splitlines()[0],
        "[adapters/adapter.py]"))
    m = (bench / "project" / zoo.MANIFEST_NAME).read_text()
    assert "target.py" in m, "the manifest must still declare it — that is the point"
    rep = zoo.verify(bench)
    assert not rep.ok, "verify read the manifest instead of the artifact the guard reads"
    assert any("runtime tamper guard will NOT hash" in p or
               "does not declare" in p for p in rep.problems), rep.problems


def test_protection_is_additive_not_replacing(bench):
    """A manifest's protected_paths must UNION with #197's defaults, never replace them.

    #197's own ``protected_paths`` replaces its defaults wholesale, so a manifest that
    declared its four known paths silently switched OFF the ``*gold*`` answer-key globs.
    """
    m = zoo.load_manifest(bench / "project")
    eff = zoo.effective_protected(m)
    for want in ("adapters", zoo.MANIFEST_NAME, "target.py", "tasks.jsonl"):
        assert want in eff, want
    assert any("gold" in p for p in eff), \
        "declaring paths must not switch off the answer-key globs"
    spec = (bench / "project" / "capevolve.yaml").read_text()
    assert "*gold*.json" in spec, "the generated spec must carry the union"


def test_verify_flags_a_third_authors_new_files(bench):
    """Under-declaration must be DETECTED, not just uncovered for four hardcoded names.

    A reviewer added helpers.py / scorer2.py / answers_gold.json to a zoo entry: all
    three were silently unprotected and verify still said ok: true.
    """
    proj = bench / "project"
    (proj / "helpers.py").write_text("X = 1\n", encoding="utf-8")
    (proj / "scorer2.py").write_text("def grade(t, r):\n    return 1.0\n", encoding="utf-8")
    (proj / "answers_gold.json").write_text('{"a1": "2"}\n', encoding="utf-8")
    rep = zoo.verify(bench)
    assert not rep.ok, "a third author's code + answer key must not verify silently"
    stray = " ".join(rep.problems)
    assert "UNDER-DECLARED" in stray, rep.problems
    # the two modules are FLAGGED (they need declaring)...
    for name in ("helpers.py", "scorer2.py"):
        assert name in stray, f"{name} not flagged: {rep.problems}"
    # ...and the answer key is already COVERED, because the union keeps #197's *gold*
    # globs alive instead of letting the manifest's list replace them.
    assert "answers_gold.json" in rep.protected, rep.protected

    # declaring them closes the finding: verify passes and all three are guard-hashed.
    m = bench / "project" / zoo.MANIFEST_NAME
    m.write_text(m.read_text().replace(
        "protected_paths: [adapters, benchmark.yaml, target.py, tasks.jsonl]",
        "protected_paths: [adapters, benchmark.yaml, target.py, tasks.jsonl, "
        "helpers.py, scorer2.py]"), encoding="utf-8")
    zoo.add(bench, refresh=True)
    rep2 = zoo.verify(bench)
    assert rep2.ok, rep2.problems
    for name in ("helpers.py", "scorer2.py", "answers_gold.json"):
        assert name in rep2.protected, (name, rep2.protected)


def test_verify_fails_a_saturated_baseline_and_allows_a_declared_opt_out(bench):
    """B1: a benchmark that is already perfect has no headroom to optimize."""
    t = bench / "project" / "target.py"
    t.write_text(t.read_text() + '''

def _cheat(task):
    return str(task.target)
''', encoding="utf-8")
    # make run() echo the gold answer
    t.write_text(t.read_text().replace(
        '    prompt = (Path(ctx) / "prompt.txt").read_text(encoding="utf-8")',
        '    return {"output": str(task.target), "trace": "gold"}\n'
        '    prompt = (Path(ctx) / "prompt.txt").read_text(encoding="utf-8")'),
        encoding="utf-8")
    rep = zoo.verify(bench)
    assert not rep.ok and any("NO HEADROOM" in p for p in rep.problems), rep.problems
    # ...and the loudly-declared opt-out for a genuinely saturated reference fixture
    m = bench / "project" / zoo.MANIFEST_NAME
    m.write_text(m.read_text() + "allow_saturated_baseline: true\n", encoding="utf-8")
    rep2 = zoo.verify(bench)
    assert not any("NO HEADROOM" in p for p in rep2.problems), rep2.problems
    assert any("SATURATED BASELINE ALLOWED" in n for n in rep2.notes), rep2.notes


def test_verify_catches_a_constant_scorer(bench):
    """B1: the degenerate-scorer probe — a score() that ignores its input."""
    t = bench / "project" / "target.py"
    t.write_text(t.read_text() + '''

def score(task, rollout):
    from cap_evolve.types import Score
    return Score(task_id=task.id, reward=1.0, feedback="perfect", trial_rewards=[1.0])
''', encoding="utf-8")
    # declared, so B2's hard error is not what fires here
    m = bench / "project" / zoo.MANIFEST_NAME
    m.write_text(m.read_text().replace("scoring: exact", "scoring: custom"),
                 encoding="utf-8")
    rep = zoo.verify(bench)
    assert not rep.ok
    assert any("DOES NOT DISCRIMINATE" in p or "NO HEADROOM" in p
               for p in rep.problems), rep.problems


def test_undeclared_custom_scorer_is_a_hard_error(bench):
    """B2: a score() that silently overrides the declared mode makes `list` lie."""
    t = bench / "project" / "target.py"
    t.write_text(t.read_text() + '''

def score(task, rollout):
    from cap_evolve.types import Score
    return Score(task_id=task.id, reward=1.0, trial_rewards=[1.0])
''', encoding="utf-8")
    rep = zoo.verify(bench)
    assert not rep.ok
    assert any("scoring: custom" in p for p in rep.problems), rep.problems


@pytest.mark.parametrize("key,value", [
    ("target_module", "../../pwned.py"),
    ("tasks_file", "../../evil.jsonl"),
    ("capability_path", "../../elsewhere"),
    ("split_ids_file", "/etc/passwd"),
])
def test_path_fields_are_contained_in_the_project_dir(bench, key, value):
    """B4: `target_module: ../../pwned.py` EXECUTED code outside the project dir."""
    m = bench / "project" / zoo.MANIFEST_NAME
    txt = m.read_text()
    import re as _re
    txt = _re.sub(rf"(?m)^{key}:.*$", f"{key}: {value}", txt)
    if f"{key}:" not in txt:
        txt += f"\n{key}: {value}\n"
    m.write_text(txt, encoding="utf-8")
    with pytest.raises(zoo.BenchmarkError) as e:
        zoo.load_manifest(bench / "project")
    assert key in str(e.value) and "relative path" in str(e.value)


def test_target_module_escape_never_imports(bench, tmp_path):
    """The containment guard must fire BEFORE the module is executed."""
    marker = tmp_path / "PWNED"
    (tmp_path / "pwned.py").write_text(
        f"from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('x')\n"
        "def run(task, ctx, *, seed=0):\n    return 'x'\n", encoding="utf-8")
    m = bench / "project" / zoo.MANIFEST_NAME
    m.write_text(m.read_text().replace("target_module: target.py",
                                       "target_module: ../../pwned.py"),
                 encoding="utf-8")
    rep = zoo.verify(bench)
    assert not rep.ok
    assert not marker.exists(), "code outside the project dir was EXECUTED during verify"


def test_zero_holdout_and_empty_train_are_refused(bench):
    """B6: train == val == test passed the honesty floor; #99's tau^2 number was one."""
    ids = [t.id for t in zoo.ManifestAdapter(bench / "project").tasks("all")]
    sf = bench / "project" / "splits.json"
    sf.write_text(json.dumps({"train": ids, "val": ids, "test": ids}), encoding="utf-8")
    m = bench / "project" / zoo.MANIFEST_NAME
    m.write_text(m.read_text().replace('split_ids_file: ""',
                                       "split_ids_file: splits.json"), encoding="utf-8")
    rep = zoo.verify(bench)
    assert not rep.ok
    assert any("OVERLAP" in p for p in rep.problems), rep.problems

    # and an empty train split, via ratios
    m.write_text(m.read_text().replace("split_ids_file: splits.json",
                                       'split_ids_file: ""')
                 .replace("split_train: 0.5", "split_train: 0.0")
                 .replace("split_val: 0.25", "split_val: 0.9")
                 .replace("split_test: 0.25", "split_test: 0.1"), encoding="utf-8")
    rep2 = zoo.verify(bench)
    assert not rep2.ok
    assert any("train split is EMPTY" in p for p in rep2.problems), rep2.problems


def test_content_duplicate_tasks_are_refused(bench):
    """Fresh ids on identical rows split cleanly, so val became a copy of train."""
    d = bench / "project" / "tasks.jsonl"
    rows = [json.loads(x) for x in d.read_text().splitlines() if x.strip()]
    d.write_text("".join(json.dumps(r) + "\n" for r in
                         rows + [{**r, "id": r["id"] + "_dup"} for r in rows]),
                 encoding="utf-8")
    rep = zoo.verify(bench)
    assert not rep.ok
    assert any("CONTENT duplicate" in p for p in rep.problems), rep.problems


def test_forged_and_stale_stamps_read_as_unverified(bench, monkeypatch, tmp_path):
    """B3: dataset_sha256 was written and never compared."""
    zoo_root = tmp_path / "zoo"
    zoo_root.mkdir()
    shutil.copytree(bench, zoo_root / "toy_calc")
    monkeypatch.setenv("CAPEVOLVE_BENCHMARKS_DIR", str(zoo_root))
    b = zoo_root / "toy_calc"
    m = zoo.load_manifest(b / "project")

    # forged: a hand-written stamp with no evidence
    (b / zoo.STAMP_NAME).write_text(json.dumps(
        {"ok": True, "val_reward": 0.99, "n_tasks": 999}), encoding="utf-8")
    assert zoo.stamp_state(b, m)["verified"] is False
    assert zoo.index()[0]["verified"] is False
    assert "hand-written" in zoo.index()[0]["stale_reason"]

    # real stamp, then edit the dataset
    zoo.stamp(b, zoo.verify(b))
    assert zoo.stamp_state(b, m)["verified"] is True
    d = b / "project" / "tasks.jsonl"
    d.write_text(d.read_text() + json.dumps({"id": "zz", "input": "1+1",
                                             "target": "2"}) + "\n", encoding="utf-8")
    st = zoo.stamp_state(b, m)
    assert st["verified"] is False and st["stale"] is True
    assert "dataset_sha256" in st["why"]

    # a stamped grader change also invalidates it
    zoo.stamp(b, zoo.verify(b))
    t = b / "project" / "target.py"
    t.write_text(t.read_text() + "\n# touched\n", encoding="utf-8")
    assert zoo.stamp_state(b, m)["verified"] is False
    assert "target_sha256" in zoo.stamp_state(b, m)["why"]


def test_description_newline_cannot_redefine_manifest_keys(tmp_path):
    """B7: --description was interpolated unquoted into YAML."""
    zoo.add(tmp_path / "b", name="b",
            description="oops\nscoring: contains\ntasks_file: /etc/hosts")
    m = zoo.load_manifest(tmp_path / "b" / "project")
    assert m["scoring"] == "exact", m
    assert m["tasks_file"] == "tasks.jsonl", m
    assert "\n" in m["description"], "the description itself must survive intact"


def test_refresh_keeps_a_hand_edited_adapter_shim(bench):
    """N2: --refresh clobbered an authored override with no warning."""
    shim = bench / "project" / "adapters" / "adapter.py"
    override = shim.read_text() + "\n    def trajectories(self, *a, **k):\n        return []\n"
    shim.write_text(override, encoding="utf-8")
    info = zoo.add(bench, refresh=True)
    assert shim.read_text() == override, "an authored override was clobbered"
    assert info.get("kept_hand_edited") == ["adapters/adapter.py"], info
    # an untouched shim is still re-derived
    shim.write_text(zoo._shim_text(zoo.load_manifest(bench / "project")), encoding="utf-8")
    assert "kept_hand_edited" not in zoo.add(bench, refresh=True)


def test_tasks_honours_the_split_argument(bench):
    """N1: tasks("test") handed out the sealed test split to any caller."""
    a = zoo.ManifestAdapter(bench / "project")
    allt = {t.id for t in a.tasks("all")}
    tr = {t.id for t in a.tasks("train")}
    va = {t.id for t in a.tasks("val")}
    te = {t.id for t in a.tasks("test")}
    assert tr | va | te == allt
    assert not (te & (tr | va)), "tasks() must not leak test ids into train/val"
    assert te != allt, 'tasks("test") returned the whole dataset'


def test_empty_target_is_not_a_free_point(tmp_path):
    """N5: match("anything", "", "contains") is True — a missing answer scored 1.0."""
    zoo.add(tmp_path / "b", name="b")
    proj = tmp_path / "b" / "project"
    m = proj / zoo.MANIFEST_NAME
    m.write_text(m.read_text().replace("scoring: exact", "scoring: contains"),
                 encoding="utf-8")
    (proj / "tasks.jsonl").write_text(
        json.dumps({"id": "t1", "input": "q", "target": ""}) + "\n", encoding="utf-8")
    with pytest.raises(zoo.BenchmarkError, match="free"):
        zoo.ManifestAdapter(proj).tasks("all")


def test_bad_regex_target_fails_at_load(tmp_path):
    """N3: an invalid pattern surfaced as a smoke-eval crash, not a dataset error."""
    zoo.add(tmp_path / "b", name="b")
    proj = tmp_path / "b" / "project"
    m = proj / zoo.MANIFEST_NAME
    m.write_text(m.read_text().replace("scoring: exact", "scoring: regex"),
                 encoding="utf-8")
    (proj / "tasks.jsonl").write_text(
        json.dumps({"id": "t1", "input": "q", "target": "([unclosed"}) + "\n",
        encoding="utf-8")
    with pytest.raises(zoo.BenchmarkError, match="valid regex"):
        zoo.ManifestAdapter(proj).tasks("all")


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
