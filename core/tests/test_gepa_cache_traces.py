"""A GEPA eval-cache HIT must yield the same reflective signal as a fresh eval (#111).

The cache used to store only ``{reward, feedback}``, so ``_eval_minibatch`` rebuilt a
``Score`` with ``raw={"cached": True}`` and no ``output``/``trace``. ``_write_reflection``
then emitted ``- Agent output:`` (empty) for cached failing tasks — GEPA's whole learning
signal, blank, on exactly the parents it re-samples most.

These tests pin the fix at both levels: the cache entry carries a pointer to the rollout
json that produced the score, and a hit re-reads it (and re-materializes it under the new
eval tag so the tag-pinned ``trajectories/`` dir still exists).
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))


def _adapter():
    """A deterministic adapter whose rollouts carry a distinctive output AND trace."""
    from cap_evolve import CapabilityAdapter, Rollout, Score, Task

    class _A(CapabilityAdapter):
        def tasks(self, split):  # noqa: ARG002
            return [Task(id=f"t{i}", input=f"in-{i}", target="ok") for i in range(4)]

        def run_target(self, task, ctx, *, seed=0):  # noqa: ARG002
            return Rollout(task_id=task.id,
                           output=f"WRONG-ANSWER-for-{task.id}",
                           trace=f"STEP1 read {task.input}; STEP2 guessed")

        def score(self, task, rollout):  # noqa: ARG002
            return Score(task_id=task.id, reward=0.0,
                         feedback=f"expected ok, got {rollout.output}",
                         trial_rewards=[0.0])

        def materialize(self, candidate_dir, edits=None):  # noqa: ARG002
            return None

    return _A()


@pytest.fixture
def setup(tmp_path):
    from cap_evolve import Budget, RunDir
    from cap_evolve.cache import EvalCache
    cand = tmp_path / "cand"
    cand.mkdir()
    (cand / "cap.md").write_text("seed capability\n", encoding="utf-8")
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="c1", budget=Budget(max_iterations=4))
    return _adapter(), run_dir, cand, EvalCache(run_dir.root / "eval_cache.json")


def test_cache_hit_reflective_dataset_has_output_and_trace(setup):
    """Fail-before / pass-after: a fully-cached minibatch must still produce a
    REFLECTION.md with the agent's real output AND trajectory."""
    from cap_evolve import gepa
    adapter, run_dir, cand, cache = setup
    ids = ["t0", "t1", "t2"]

    first = gepa._eval_minibatch(adapter, cand, ids, run_dir=run_dir, cache=cache,
                                 tag="mb_p_0000", seed=0)
    # Second eval of the same candidate + tasks: every task is a cache hit (0 rollouts).
    before = run_dir.spent.metric_calls
    second = gepa._eval_minibatch(adapter, cand, ids, run_dir=run_dir, cache=cache,
                                  tag="mb_p_0001", seed=0)
    assert run_dir.spent.metric_calls == before, "expected a full cache hit"
    assert second.reward == first.reward

    for pt in second.per_task:
        raw = pt.get("raw") or {}
        assert raw.get("cached") is True
        assert f"WRONG-ANSWER-for-{pt['task_id']}" in str(raw.get("output"))
        assert "STEP1 read" in str(raw.get("trace"))

    wd = run_dir.root / "work" / "x"
    wd.mkdir(parents=True)
    gepa._write_reflection(wd, second)
    refl = (wd / "REFLECTION.md").read_text(encoding="utf-8")
    assert "- Agent output: \n" not in refl, "hollow reflective dataset"
    assert "WRONG-ANSWER-for-t0" in refl
    assert "- Trajectory: STEP1 read in-0" in refl


def test_cache_hit_rematerializes_rollouts_under_new_tag(setup):
    """The cached hit must leave ``rollouts/train/*__<tag>__t0.json`` for the NEW tag, so
    ``harness._copy_step_trajectories(tag=...)`` still finds this minibatch verbatim."""
    from cap_evolve import gepa
    adapter, run_dir, cand, cache = setup
    gepa._eval_minibatch(adapter, cand, ["t0", "t1"], run_dir=run_dir, cache=cache,
                         tag="mb_p_0000", seed=0)
    gepa._eval_minibatch(adapter, cand, ["t0", "t1"], run_dir=run_dir, cache=cache,
                         tag="mb_p_0001", seed=0)
    got = sorted(p.name for p in (run_dir.rollouts / "train").glob("*__mb_p_0001__t0.json"))
    assert got == ["t0__mb_p_0001__t0.json", "t1__mb_p_0001__t0.json"]
    rec = json.loads((run_dir.rollouts / "train" / "t0__mb_p_0001__t0.json")
                     .read_text(encoding="utf-8"))
    assert rec["rollout"]["output"] == "WRONG-ANSWER-for-t0"
    assert "STEP1" in rec["rollout"]["trace"]


def test_cache_entry_stores_rollout_pointer_not_payload(setup):
    """Cache format: reward + feedback + a POINTER. The trace is NOT copied into the
    cache, so the cache stays tiny however large the traces get."""
    from cap_evolve import gepa
    adapter, run_dir, cand, cache = setup
    gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                         tag="mb_p_0000", seed=0)
    raw = json.loads((run_dir.root / "eval_cache.json").read_text(encoding="utf-8"))
    (entry,) = raw.values()
    assert set(entry) == {"reward", "feedback", "rollout_file"}
    assert entry["rollout_file"] == "t0__mb_p_0000__t0.json"
    assert "STEP1" not in json.dumps(entry), "trace must not be duplicated into the cache"


def test_pointerless_or_missing_rollout_is_treated_as_a_miss(setup):
    """A pre-#111 (score-only) entry, or one whose rollout json was pruned, must be
    RE-RUN rather than served as an empty reflective row."""
    from cap_evolve import gepa
    adapter, run_dir, cand, cache = setup

    # (a) legacy score-only entry
    from cap_evolve.cache import hash_candidate_dir
    chash = hash_candidate_dir(cand)
    cache._data[f"{chash}::t0"] = {"reward": 0.0, "feedback": "legacy"}
    cache._flush()
    before = run_dir.spent.metric_calls
    res = gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                               tag="mb_p_0000", seed=0)
    assert run_dir.spent.metric_calls == before + 1, "legacy entry must miss"
    assert "WRONG-ANSWER-for-t0" in str((res.per_task[0]["raw"] or {}).get("output"))

    # (b) pointer present but the rollout json is gone
    (run_dir.rollouts / "train" / "t0__mb_p_0000__t0.json").unlink()
    before = run_dir.spent.metric_calls
    res = gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                               tag="mb_p_0002", seed=0)
    assert run_dir.spent.metric_calls == before + 1, "dangling pointer must miss"
    assert "WRONG-ANSWER-for-t0" in str((res.per_task[0]["raw"] or {}).get("output"))


def test_trace_is_bounded_in_the_reflective_signal(setup):
    """Cache size + prompt size stay bounded: the replayed output/trace go through the
    same ``_short`` truncation a fresh eval uses."""
    from cap_evolve import gepa
    adapter, run_dir, cand, cache = setup
    huge = "X" * 50_000
    orig = adapter.run_target

    def _big(task, ctx, *, seed=0):
        r = orig(task, ctx, seed=seed)
        r.trace = huge
        return r
    adapter.run_target = _big
    gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                         tag="mb_p_0000", seed=0)
    res = gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                               tag="mb_p_0001", seed=0)
    trace = str((res.per_task[0]["raw"] or {}).get("trace"))
    assert len(trace) < 2000 and trace.endswith("…[truncated]")
    # and the cache itself never grew by the trace
    assert (run_dir.root / "eval_cache.json").stat().st_size < 1000


# --- security / integrity of the re-materialization mechanism (review of #210) -------
#
# ``eval_cache.json`` is plain JSON in the OPTIMIZER-WRITABLE run dir, so every field it
# carries is untrusted input — exactly #142's threat model. #197's tamper guard hashes
# ``.capevolve/project`` and excludes the run dir, so it does not cover this file.


@pytest.mark.parametrize("pointer", [
    "../../../../secrets.json",   # relative traversal escapes out_dir
    "sub/secrets.json",           # subdir
    "/etc/passwd",                # absolute path REPLACES out_dir entirely
])
def test_crafted_rollout_pointer_cannot_read_outside_the_rollouts_dir(setup, tmp_path,
                                                                     pointer):
    """A tampered ``rollout_file`` must not read any file outside ``rollouts/<split>/``
    into the reflective signal (i.e. into the optimizer LLM's prompt), and must not
    hardlink an out-of-tree inode into the run dir. It degrades to an honest MISS."""
    from cap_evolve import gepa
    from cap_evolve.cache import hash_candidate_dir
    adapter, run_dir, cand, cache = setup

    secrets = tmp_path / "secrets.json"
    secrets.write_text(json.dumps({
        "input": "x", "score": {"reward": 0.0},
        "rollout": {"task_id": "t0", "output": "sk-SUPER-SECRET-KEY",
                    "trace": "AWS_SECRET=xyz", "error": None},
    }), encoding="utf-8")
    ptr = str(secrets) if pointer.startswith("/etc") else pointer
    cache._data[f"{hash_candidate_dir(cand)}::t0"] = {
        "reward": 0.0, "feedback": "fb", "rollout_file": ptr}
    cache._flush()

    before = run_dir.spent.metric_calls
    res = gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                               tag="mb_p_0000", seed=0)
    assert run_dir.spent.metric_calls == before + 1, "crafted pointer must MISS, not serve"
    raw = res.per_task[0].get("raw") or {}
    assert "SUPER-SECRET" not in json.dumps(raw), "exfiltrated into the reflective signal"
    assert "WRONG-ANSWER-for-t0" in str(raw.get("output")), "must be the real re-run"

    wd = run_dir.root / "work" / "x"
    wd.mkdir(parents=True)
    gepa._write_reflection(wd, res)
    refl = (wd / "REFLECTION.md").read_text(encoding="utf-8")
    assert "SUPER-SECRET" not in refl and "AWS_SECRET" not in refl
    assert secrets.stat().st_nlink == 1, "out-of-tree inode hardlinked into the run dir"


def test_malformed_cached_reward_degrades_to_a_miss_instead_of_crashing(setup):
    """A non-numeric ``reward`` in the cache must not raise mid-loop."""
    from cap_evolve import gepa
    from cap_evolve.cache import hash_candidate_dir
    adapter, run_dir, cand, cache = setup
    gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                         tag="mb_p_0000", seed=0)
    cache._data[f"{hash_candidate_dir(cand)}::t0"]["reward"] = "not-a-number"
    cache._flush()

    before = run_dir.spent.metric_calls
    res = gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                               tag="mb_p_0001", seed=0)
    assert run_dir.spent.metric_calls == before + 1
    assert res.reward == 0.0


def test_fresh_write_never_rewrites_a_hardlinked_archived_rollout(setup):
    """A cache hit hardlinks a prior rollout under the new tag. A later FRESH eval on
    that same tag (a torn iteration + ``--resume`` reuses tags) must replace the
    directory entry, not truncate the shared inode — otherwise it silently rewrites a
    PREVIOUS iteration's archived evidence with another candidate's output."""
    from cap_evolve import gepa
    adapter, run_dir, cand, cache = setup
    train = run_dir.rollouts / "train"

    gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                         tag="mb_p_0000", seed=0)
    archived = train / "t0__mb_p_0000__t0.json"
    original = archived.read_text(encoding="utf-8")
    # cache hit under a second tag -> hardlink, shared inode
    gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                         tag="mb_c_0000", seed=0)
    linked = train / "t0__mb_c_0000__t0.json"
    assert linked.stat().st_ino == archived.stat().st_ino, "expected a hardlink"

    # a REAL edit -> new hash -> MISS -> fresh write onto the reused tag
    (cand / "cap.md").write_text("REAL-EDIT\n", encoding="utf-8")
    adapter.run_target = lambda task, ctx, *, seed=0: __import__(
        "cap_evolve").Rollout(task_id=task.id, output="CHILD-REAL-EDIT", trace="tr")
    gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                         tag="mb_c_0000", seed=0)

    assert archived.read_text(encoding="utf-8") == original, \
        "fresh write rewrote a PREVIOUS iteration's archived rollout via the shared inode"
    assert "CHILD-REAL-EDIT" in linked.read_text(encoding="utf-8")
    assert linked.stat().st_ino != archived.stat().st_ino, "link must be broken, not reused"


def test_tag_reuse_replaces_a_prior_parents_trajectory(setup):
    """#199's prompt claims ``trajectories/`` holds this minibatch VERBATIM. On a resumed
    run a tag can already hold a DIFFERENT parent's rollout, so the replay must overwrite
    it — serving parent A on disk while REFLECTION.md shows parent B is dishonest."""
    from cap_evolve import Rollout, gepa
    adapter, run_dir, cand_a, cache = setup
    cand_b = cand_a.parent / "cand_b"
    cand_b.mkdir()
    (cand_b / "cap.md").write_text("candidate B\n", encoding="utf-8")
    train = run_dir.rollouts / "train"

    gepa._eval_minibatch(adapter, cand_a, ["t0"], run_dir=run_dir, cache=cache,
                         tag="mb_p_0000", seed=0)  # parent A owns tag mb_p_0000
    adapter.run_target = lambda task, ctx, *, seed=0: Rollout(
        task_id=task.id, output="OUT-B", trace="tr-B")
    gepa._eval_minibatch(adapter, cand_b, ["t0"], run_dir=run_dir, cache=cache,
                         tag="mb_p_0001", seed=0)  # parent B cached under its own tag
    # resumed run: frontier picks B, but tag mb_p_0000 exists from A -> cache HIT for B
    res = gepa._eval_minibatch(adapter, cand_b, ["t0"], run_dir=run_dir, cache=cache,
                               tag="mb_p_0000", seed=0)

    on_disk = json.loads((train / "t0__mb_p_0000__t0.json")
                         .read_text(encoding="utf-8"))["rollout"]["output"]
    in_prompt = str((res.per_task[0]["raw"] or {}).get("output"))
    assert on_disk == "OUT-B" == in_prompt, \
        f"trajectories/ serves {on_disk!r} while REFLECTION.md shows {in_prompt!r}"


def test_cross_filesystem_link_failure_falls_back_to_a_byte_identical_copy(setup,
                                                                          monkeypatch):
    """``EXDEV`` / a filesystem without hardlinks must fall back to a real copy."""
    import errno
    import os as _os
    from cap_evolve import gepa
    adapter, run_dir, cand, cache = setup
    train = run_dir.rollouts / "train"
    gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                         tag="mb_p_0000", seed=0)
    src = train / "t0__mb_p_0000__t0.json"

    def _no_link(*a, **k):
        raise OSError(errno.EXDEV, "Cross-device link")
    monkeypatch.setattr(_os, "link", _no_link)
    gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                         tag="mb_p_0001", seed=0)

    dst = train / "t0__mb_p_0001__t0.json"
    assert dst.is_file() and dst.stat().st_ino != src.stat().st_ino, "expected a copy"
    a, b = (json.loads(p.read_text(encoding="utf-8")) for p in (src, dst))
    assert a == b, "copy fallback is not equivalent to the link source"


def test_rematerialize_failure_is_logged_not_swallowed(setup, monkeypatch):
    """When BOTH link and copy fail, trajectories/ silently lacks this task while the
    prompt still claims VERBATIM completeness. Make it loud."""
    import errno
    import os as _os
    from cap_evolve import gepa
    adapter, run_dir, cand, cache = setup
    gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                         tag="mb_p_0000", seed=0)

    def _boom(*a, **k):
        raise OSError(errno.EROFS, "Read-only file system")
    monkeypatch.setattr(_os, "link", _boom)
    monkeypatch.setattr(gepa, "_atomic_write", _boom)  # only gepa's writer, not rundir's
    res = gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                               tag="mb_p_0001", seed=0)

    assert res.reward == 0.0, "the Score itself is still complete"
    kinds = [json.loads(ln)["kind"] for ln in
             (run_dir.root / "events.jsonl").read_text(encoding="utf-8").splitlines() if ln]
    assert "rollout_rematerialize_failed" in kinds, "silent failure looks like success"


def test_copy_step_trajectories_never_writes_through_a_hardlink(setup):
    """``harness._copy_step_trajectories`` uses ``shutil.copyfile``, which DOES write
    through a pre-existing hardlinked destination. It is safe only because ``_copy_tag``
    rmtree's ``trajectories/`` first — pin that invariant: no copied trajectory may share
    an inode with the ``rollouts/`` record it came from, or copying would mutate the
    archive."""
    from cap_evolve import gepa, harness
    adapter, run_dir, cand, cache = setup
    gepa._eval_minibatch(adapter, cand, ["t0", "t1"], run_dir=run_dir, cache=cache,
                         tag="seed", seed=0)
    workdir = run_dir.root / "work" / "step"
    workdir.mkdir(parents=True)
    harness._copy_step_trajectories(adapter, run_dir, workdir, "train")

    copied = sorted((workdir / "trajectories").glob("*.json"))
    assert copied, "expected the seed tag's rollouts to be copied"
    rollout_inodes = {p.stat().st_ino for p in (run_dir.rollouts / "train").glob("*.json")}
    assert not [p for p in copied if p.stat().st_ino in rollout_inodes], \
        "a trajectories/ copy shares a rollouts/ inode — a later copyfile would mutate it"
    # and copying twice (a second step) must not corrupt the archive either
    archived = (run_dir.rollouts / "train" / "t0__seed__t0.json")
    original = archived.read_text(encoding="utf-8")
    harness._copy_step_trajectories(adapter, run_dir, workdir, "train")
    assert archived.read_text(encoding="utf-8") == original
