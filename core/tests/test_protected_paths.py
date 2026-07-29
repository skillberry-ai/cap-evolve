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


def test_pycache_IS_protected(tmp_path):
    """BYPASS 1 regression: bytecode must be hashed, not excluded.

    An earlier revision skipped ``__pycache__``/``*.pyc`` because ``load_adapter``
    wrote them during a run. That exclusion was a working reward hack: a PEP 552
    UNCHECKED_HASH pyc in the adapter's cache slot runs a hacked ``score()`` while
    ``adapter.py``'s SHA-256 stays identical to the manifest. The exclusion is gone
    and ``load_adapter`` no longer writes bytecode, so a pyc appearing mid-run is
    tamper. Verified end to end by ``test_planted_unchecked_hash_pyc_is_caught``.
    """
    from cap_evolve import protect
    _, project, _ = _project(tmp_path)
    pyc = project / "adapters" / "__pycache__" / "adapter.cpython-311.pyc"
    pyc.parent.mkdir(parents=True)
    pyc.write_bytes(b"\x00compiled")
    assert "adapters/__pycache__/adapter.cpython-311.pyc" in protect.resolve_protected(project)
    assert protect.is_protected(project, pyc) is True
    assert protect.is_protected(project, project / "adapters" / "adapter.py") is True


def test_load_adapter_writes_no_bytecode(tmp_path):
    """BYPASS 1, the other half: ``load_adapter`` must leave no ``.pyc`` behind.

    This is what makes hashing bytecode safe — if the loader still wrote a pyc, the
    (now pyc-aware) guard would flag every legitimate run. It must also refuse to
    execute a pre-existing cache, so only the hashed source can run.
    """
    import py_compile

    from cap_evolve.check import load_adapter
    _, project, _ = _project(tmp_path)
    cache = project / "adapters" / "__pycache__"

    # A stale/planted cache is destroyed rather than honoured.
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "adapter.cpython-311.pyc").write_bytes(b"\x00junk")
    py_compile.compile(str(project / "adapters" / "adapter.py"), doraise=True,
                       invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)

    load_adapter(project)
    leftover = sorted(p.name for p in cache.rglob("*")) if cache.exists() else []
    assert leftover == [], f"load_adapter left bytecode behind: {leftover}"


def test_case_folded_path_is_protected_on_case_insensitive_fs(tmp_path):
    """N2: ``Adapters/adapter.py`` is the same inode as the protected path on APFS."""
    from cap_evolve import protect
    _, project, _ = _project(tmp_path)
    varied = project / "Adapters" / "adapter.py"
    if not varied.exists():
        pytest.skip("case-sensitive filesystem — no case-folding hazard here")
    assert protect.is_protected(project, varied) is True


def test_symlinked_protected_file_is_tamper_not_an_exemption(tmp_path):
    """BYPASS 4 regression: replacing a protected file BY a symlink used to
    de-protect it silently (``.resolve()`` followed the link out of the project dir,
    so the path vanished from the protected set with no event and no error)."""
    from cap_evolve import RunDir, protect
    base, project, _ = _project(tmp_path)
    run_dir = RunDir.create(base, ts="lnk")
    protect.ensure_manifest(run_dir, project)

    outside = tmp_path / "editable.yaml"
    outside.write_text("gate_mode: strict\n", encoding="utf-8")
    tgt = project / "capevolve.yaml"
    tgt.unlink()
    tgt.symlink_to(outside)

    # Still in the protected set (not silently dropped) AND reported as changed.
    assert "capevolve.yaml" in protect.resolve_protected(project)
    with pytest.raises(protect.TamperError) as ei:
        protect.verify(run_dir, project, context="symlink swap")
    assert "capevolve.yaml" in str(ei.value)
    events = [json.loads(x) for x in
              (run_dir.root / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e for e in events if e.get("kind") == "tamper_detected"]


def test_torn_manifest_after_baseline_is_a_hard_failure(tmp_path):
    """BYPASS 2 regression: a missing/clobbered/altered manifest must NOT be
    silently re-recorded from the (possibly tampered) current tree."""
    from cap_evolve import RunDir, protect
    base, project, _ = _project(tmp_path)

    for mode in ("clobber", "delete", "alter"):
        run_dir = RunDir.create(base, ts=f"torn_{mode}")
        first = protect.ensure_manifest(run_dir, project)
        assert first, "baseline must record a manifest"
        mpath = run_dir.root / protect.MANIFEST_NAME

        # Reward-hack the grader, then attack the evidence.
        grader = project / "adapters" / "adapter.py"
        original = grader.read_text(encoding="utf-8")
        grader.write_text(original + "\n# reward hack\n", encoding="utf-8")
        if mode == "clobber":
            mpath.write_text("CORRUPT", encoding="utf-8")
        elif mode == "delete":
            mpath.unlink()
        else:  # a syntactically valid manifest that blesses the tampered tree
            mpath.write_text(json.dumps({
                "project_dir": str(project.resolve()),
                "globs": protect.protected_globs(project),
                "files": protect.build_manifest(project, exclude=run_dir.root),
            }, indent=2), encoding="utf-8")

        with pytest.raises(protect.TamperError) as ei:
            protect.verify(run_dir, project, context=f"{mode} attack")
        assert "manifest" in str(ei.value).lower() or "adapter.py" in str(ei.value)
        grader.write_text(original, encoding="utf-8")


def test_malformed_protected_paths_is_a_hard_error(tmp_path):
    """N3: a ``protected_paths`` that does not parse as a list must NOT silently fall
    back to the defaults — a config that quietly doesn't apply is the dangerous case.
    The block-list form now parses correctly; a mapping is rejected."""
    from cap_evolve import protect
    from cap_evolve.specfile import read_yaml

    # The idiomatic block form used to parse as {} and fall through to the defaults.
    assert read_yaml("protected_paths:\n  - a.py\n  - b/\n")["protected_paths"] == ["a.py", "b/"]

    _, project, _ = _project(tmp_path)
    (project / "capevolve.yaml").write_text(
        "capability_path: seed_capability\nprotected_paths:\n  nested: oops\n", encoding="utf-8")
    with pytest.raises(protect.TamperError, match="did not parse as a list"):
        protect.protected_globs(project)

    (project / "capevolve.yaml").write_text(
        "capability_path: seed_capability\nprotected_paths: []\n", encoding="utf-8")
    with pytest.raises(protect.TamperError, match="EMPTY list"):
        protect.protected_globs(project)


def test_block_list_protected_paths_applies(tmp_path):
    """N3, positive: the block-list form is honoured, replacing the defaults."""
    from cap_evolve import protect
    _, project, _ = _project(tmp_path,
                             extra_yaml="protected_paths:\n  - tasks.jsonl\n")
    assert set(protect.resolve_protected(project)) == {"tasks.jsonl"}


def test_gold_glob_does_not_over_protect_prose(tmp_path):
    """N5: ``*gold*`` used to protect ``docs/golden-rules.md``; it is data-only now."""
    from cap_evolve import protect
    _, project, _ = _project(tmp_path)
    (project / "docs").mkdir()
    (project / "docs" / "golden-rules.md").write_text("prose\n", encoding="utf-8")
    (project / "gold_answers.json").write_text("{}\n", encoding="utf-8")
    files = protect.resolve_protected(project)
    assert "gold_answers.json" in files, "gold DATA must still be protected"
    assert "docs/golden-rules.md" not in files


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


def test_planted_unchecked_hash_pyc_is_caught(tmp_path):
    """BYPASS 1, end to end: a PEP 552 UNCHECKED_HASH pyc planted in the adapter's
    cache slot used to execute a hacked ``score()`` with ``adapter.py``'s SHA-256 still
    byte-identical to the manifest — a fabricated sealed number with ``tamper_detected:
    0``. Now bytecode is hashed, so the plant is an ``added`` protected file and the
    run aborts. Also asserts the planted bytecode never runs.
    """
    import py_compile

    from cap_evolve import RunDir, harness, protect
    from cap_evolve.check import load_adapter
    base, project, seed = _project(tmp_path)
    run_dir = RunDir.create(base, ts="pyc")
    harness.ensure_splits(_toy_adapter(), run_dir, seed=0)
    protect.ensure_manifest(run_dir, project)

    grader = project / "adapters" / "adapter.py"
    sha_before = protect._sha256(grader)

    # Compile an EVIL adapter into the PRISTINE adapter's cache slot, with the
    # invalidation mode that skips mtime, size AND hash validation.
    evil = tmp_path / "evil_adapter.py"
    evil.write_text(grader.read_text(encoding="utf-8").replace(
        "reward=1.0 if ok else 0.0", "reward=1.0"), encoding="utf-8")
    cache_slot = (project / "adapters" / "__pycache__" /
                  f"adapter.cpython-{sys.version_info.major}{sys.version_info.minor}.pyc")
    cache_slot.parent.mkdir(parents=True, exist_ok=True)
    py_compile.compile(str(evil), cfile=str(cache_slot), dfile=str(grader), doraise=True,
                       invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
    assert cache_slot.exists()
    assert protect._sha256(grader) == sha_before, "the source is untouched, as in the attack"

    # (a) The guard sees the plant.
    with pytest.raises(protect.TamperError) as ei:
        protect.verify(run_dir, project, context="pyc plant")
    assert "__pycache__" in str(ei.value)

    # (b) And even if it somehow ran, ``load_adapter`` refuses to execute the cache.
    #     Re-plant (the verify above did not remove it) and confirm honest scoring.
    py_compile.compile(str(evil), cfile=str(cache_slot), dfile=str(grader), doraise=True,
                       invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
    live = load_adapter(project)
    task = next(t for t in live.tasks("all"))
    from cap_evolve.harness import _live
    with _live(live, seed) as ctx:
        sc = live.score(task, live.run_target(task, ctx, seed=0))
    assert sc.reward == 0.0, "the planted HACKED score() must not have executed"


def test_post_scoring_check_catches_a_racing_writer(tmp_path):
    """BYPASS 3 regression: a writer that edits ground truth AFTER the pre-check but
    DURING scoring (a detached grandchild of the optimizer subprocess outlives
    ``subprocess.run``) used to yield an accepted reward with 0 tamper events. The
    post-scoring re-verify inside ``evaluate_candidate`` now discards that score.
    """
    from cap_evolve import RunDir, harness, protect
    base, project, seed = _project(tmp_path)
    adapter = _toy_adapter()
    run_dir = RunDir.create(base, ts="race")
    harness.ensure_splits(adapter, run_dir, seed=0)
    protect.ensure_manifest(run_dir, project)

    # Simulate the racing writer precisely: it lands after the pre-check, while the
    # scorer is mid-pass. Patching ``score`` is how we hit that window deterministically
    # (a sleeping subprocess would make the test slow and flaky).
    real_score = adapter.score
    fired = {"n": 0}

    def _score_and_race(task, rollout):
        fired["n"] += 1
        if fired["n"] == 1:
            (project / "tasks.jsonl").write_text('{"id":"t1","input":"1+1","target":"99"}\n',
                                                 encoding="utf-8")
        return real_score(task, rollout)

    adapter.score = _score_and_race
    try:
        with pytest.raises(protect.TamperError) as ei:
            harness.evaluate_candidate(adapter, seed, run_dir=run_dir, split="val", tag="raced")
    finally:
        adapter.score = real_score

    assert "post-val eval of raced" in str(ei.value), \
        "the POST-scoring check must be the one that fires"
    assert fired["n"] >= 1, "scoring did happen — the pre-check alone would have missed this"
    events = [json.loads(x) for x in
              run_dir.events_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    tampers = [e for e in events if e["kind"] == "tamper_detected"]
    assert tampers and tampers[-1]["context"] == "post-val eval of raced"
    # No score was recorded for the raced eval.
    assert not [e for e in events if e["kind"] == "evaluate" and e.get("tag") == "raced"]


def test_finalize_reverifies_before_burning_the_seal(tmp_path):
    """The sealed headline number specifically: a tamper landing during finalize must
    leave ``test_used`` False and write no ``final.json``."""
    from cap_evolve import RunDir, harness, protect
    base, project, seed = _project(tmp_path)
    adapter = _toy_adapter()
    run_dir = RunDir.create(base, ts="fin")
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)

    real_score = adapter.score
    fired = {"n": 0}

    def _score_and_race(task, rollout):
        fired["n"] += 1
        if fired["n"] == 1:
            g = project / "adapters" / "adapter.py"
            g.write_text(g.read_text(encoding="utf-8") + "\n# hacked mid-finalize\n",
                         encoding="utf-8")
        return real_score(task, rollout)

    adapter.score = _score_and_race
    try:
        with pytest.raises(protect.TamperError):
            harness.finalize(adapter, run_dir=run_dir,
                             best_dir=run_dir.candidate_dir(run_dir.best_id))
    finally:
        adapter.score = real_score

    assert run_dir.read_splits().test_used is False, "the seal must NOT be burned"
    assert not (run_dir.root / "final.json").exists()


def test_gepa_minibatch_post_check(tmp_path):
    """The post-check covers GEPA's cheap local-gate path too, which also populates
    ``EvalCache`` — a raced minibatch must not be cached as truth."""
    from cap_evolve import RunDir, harness, protect
    from cap_evolve.gepa import _eval_minibatch
    base, project, seed = _project(tmp_path)
    adapter = _toy_adapter()
    run_dir = RunDir.create(base, ts="mb")
    harness.ensure_splits(adapter, run_dir, seed=0)
    protect.ensure_manifest(run_dir, project)

    real_score = adapter.score

    def _score_and_race(task, rollout):
        (project / "tasks.jsonl").write_text("raced\n", encoding="utf-8")
        return real_score(task, rollout)

    adapter.score = _score_and_race
    ids = [t.id for t in adapter.tasks("all")][:1]
    try:
        with pytest.raises(protect.TamperError, match="post-minibatch"):
            _eval_minibatch(adapter, seed, run_dir=run_dir, task_ids=ids, tag="mb1",
                            cache=None)
    finally:
        adapter.score = real_score


def test_reuse_baseline_refuses_a_tampered_prior_run(tmp_path):
    """A reused baseline carries tamper provenance: a prior run that logged a tamper is
    refused, and a clean prior run's manifest is inherited rather than re-recorded."""
    from cap_evolve import Budget, RunDir, harness, protect
    base, project, seed = _project(tmp_path)
    adapter = _toy_adapter()

    prior = RunDir.create(base, ts="prior", budget=Budget(max_iterations=1))
    harness.ensure_splits(adapter, prior, seed=0)
    harness.baseline(adapter, seed, run_dir=prior)
    prior_manifest = (prior.root / protect.MANIFEST_NAME).read_text(encoding="utf-8")

    # (a) clean prior run → manifest inherited, not rebuilt from the current tree.
    fresh = RunDir.create(base, ts="fresh")
    harness.reuse_baseline(prior.root, run_dir=fresh)
    assert (fresh.root / protect.MANIFEST_NAME).read_text(encoding="utf-8") == prior_manifest
    events = [json.loads(x) for x in
              fresh.events_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert any(e.get("kind") == "protected_manifest" and e.get("inherited_from")
               for e in events)

    # (b) prior run logged a tamper → refuse to inherit the number at all.
    prior.log_event("tamper_detected", context="prior run", changes=[])
    with pytest.raises(protect.TamperError, match="refusing to reuse the baseline"):
        harness.reuse_baseline(prior.root, run_dir=RunDir.create(base, ts="fresh2"))


def test_hook_denies_writes_to_the_run_evidence(tmp_path):
    """BYPASS 2, the hook layer: ``protected.json`` / ``events.jsonl`` writes were
    allowed (exit 0), which is what made the manifest rewrite reachable."""
    sys.path.insert(0, str(REPO / "plugins" / "cap-evolve" / "hooks"))
    import importlib
    hook = importlib.import_module("deny_sealed_edits")
    from cap_evolve import RunDir, harness
    base, project, _ = _project(tmp_path)
    run_dir = RunDir.create(base, ts="ev")
    harness.ensure_splits(_toy_adapter(), run_dir, seed=0)
    os.environ["CAPEVOLVE_RUN_DIR"] = str(run_dir.root)
    try:
        for name in ("protected.json", "events.jsonl", "state.json", "best.txt"):
            rc = hook.decide({"tool_name": "Write", "cwd": str(base),
                              "tool_input": {"file_path": str(run_dir.root / name)}})
            assert rc == 2, f"writing {name} must be blocked"
        pyc = project / "adapters" / "__pycache__" / "adapter.cpython-314.pyc"
        assert hook.decide({"tool_name": "Write", "cwd": str(base),
                            "tool_input": {"file_path": str(pyc)}}) == 2, \
            "a pyc under a protected dir must be blocked (it is protected now)"
    finally:
        os.environ.pop("CAPEVOLVE_RUN_DIR", None)


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
