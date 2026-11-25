"""The held-out split must not be scored twice, even when a finalize attempt dies mid-way.

Seal-on-success (``reserve_test`` + ``commit_test``) exists so a finalize that crashes before
scoring can be retried without destroying the run's headline number. It cannot, by itself, tell that
case apart from a crash AFTER test was scored -- and there the held-out set has already been
observed, so a retry makes the reported number a second look at test.

Observed in a real run: a finalize killed by a foreground timeout had already scored test, the retry
scored it again, and the headline came from the second look. These tests pin the fix and, just as
importantly, pin the behaviour it must NOT break -- one honest finalize scores test twice by design
(the best as ``FINAL`` and the baseline as ``FINAL_seed``).
"""

import json
from pathlib import Path

import pytest

from cap_evolve.rundir import RunDir
from cap_evolve.splits import TestSealError, make_splits


def _run(tmp_path):
    rd = RunDir.create(tmp_path)
    rd.write_splits(make_splits([f"t{i}" for i in range(8)], seed=0))
    return rd


def _write_test_rollout(rd, name="t1__FINAL__t0.json"):
    (rd.rollouts / "test").mkdir(parents=True, exist_ok=True)
    (rd.rollouts / "test" / name).write_text("{}", encoding="utf-8")


def test_first_attempt_is_allowed(tmp_path):
    _run(tmp_path).begin_test_attempt()          # must not raise


def test_crash_before_scoring_can_still_be_retried(tmp_path):
    """The whole point of seal-on-success: no test rollouts yet, so a retry is honest."""
    rd = _run(tmp_path)
    rd.begin_test_attempt()
    rd.begin_test_attempt()


def test_retry_after_test_was_scored_is_refused(tmp_path):
    rd = _run(tmp_path)
    rd.begin_test_attempt()
    _write_test_rollout(rd)
    with pytest.raises(TestSealError) as exc:
        rd.begin_test_attempt()
    msg = str(exc.value)
    assert "already SCORED" in msg
    assert "second look" in msg.lower()
    assert "sealed" in msg.lower()
    # #799: an optimizer agent read the override's name in this message and switched the guard off.
    assert "CAPEVOLVE_ALLOW_TEST_RESCORE" not in msg
    assert "ALLOW_TEST" not in msg


def test_override_is_explicit_and_opt_in(tmp_path, monkeypatch):
    rd = _run(tmp_path)
    _write_test_rollout(rd)
    monkeypatch.setenv("CAPEVOLVE_ALLOW_TEST_RESCORE", "1")
    rd.begin_test_attempt()                      # deliberate, disclosed
    monkeypatch.setenv("CAPEVOLVE_ALLOW_TEST_RESCORE", "0")
    with pytest.raises(TestSealError):
        rd.begin_test_attempt()                  # and it is genuinely opt-in


def test_reserve_test_still_allows_two_evals_in_one_finalize(tmp_path):
    """Regression guard: the check belongs at ATTEMPT granularity, not per evaluation.

    Putting it in ``reserve_test`` broke seven core tests, because one finalize reserves twice --
    once for the best candidate and once for the baseline, to report a held-out delta.
    """
    rd = _run(tmp_path)
    rd.begin_test_attempt()
    rd.reserve_test()
    _write_test_rollout(rd, "t1__FINAL__t0.json")
    rd.reserve_test()                            # FINAL_seed, same attempt: must not raise
    _write_test_rollout(rd, "t1__FINAL_seed__t0.json")
    rd.commit_test()


def test_committed_seal_still_refuses(tmp_path):
    rd = _run(tmp_path)
    rd.begin_test_attempt()
    rd.commit_test()
    with pytest.raises(TestSealError):
        rd.begin_test_attempt()
    with pytest.raises(TestSealError):
        rd.reserve_test()


def test_no_skill_file_names_the_override():
    """#799: agents read everything under skills/, so the override must not be named there."""
    skills = Path(__file__).resolve().parents[2] / "skills"
    assert skills.is_dir()
    hits = []
    for f in skills.rglob("*"):
        if f.is_file():
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if "CAPEVOLVE_ALLOW_TEST_RESCORE" in text:
                hits.append(str(f.relative_to(skills)))
    assert hits == []


def _events(rd):
    p = rd.root / "events.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_override_use_is_recorded_in_events_and_final_json(tmp_path, monkeypatch):
    rd = _run(tmp_path)
    _write_test_rollout(rd)
    monkeypatch.setenv("CAPEVOLVE_ALLOW_TEST_RESCORE", "1")
    rd.begin_test_attempt()
    ev = [e for e in _events(rd) if e["kind"] == "test_rescore_override"]
    assert len(ev) == 1 and ev[0]["existing_test_rollouts"] == 1
    (rd.root / "final.json").write_text(json.dumps({"test": {"reward": 0.5}}), encoding="utf-8")
    rd.commit_test()
    final = json.loads((rd.root / "final.json").read_text(encoding="utf-8"))
    assert final["test"] == {"reward": 0.5}
    assert final["test_rescore_override"]["used"] is True
    assert final["test_rescore_override"]["count"] == 1


def test_no_override_leaves_no_mark(tmp_path, monkeypatch):
    monkeypatch.delenv("CAPEVOLVE_ALLOW_TEST_RESCORE", raising=False)
    rd = _run(tmp_path)
    rd.begin_test_attempt()
    (rd.root / "final.json").write_text(json.dumps({"test": {"reward": 0.5}}), encoding="utf-8")
    rd.commit_test()
    final = json.loads((rd.root / "final.json").read_text(encoding="utf-8"))
    assert "test_rescore_override" not in final
    assert not [e for e in _events(rd) if e["kind"] == "test_rescore_override"]


def test_act_finalize_keeps_the_override_mark_in_final_json(tmp_path, capsys, monkeypatch):
    """`act finalize` rewrites final.json from the phase's printed payload, which lacks the mark
    commit_test stamped on disk; the mark must survive that rewrite (#799)."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from test_digest_and_act_verbs import Sh, _act, _args, _run as _act_run

    monkeypatch.setenv("CAPEVOLVE_ALLOW_TEST_RESCORE", "1")
    rd, project, _, _ = _act_run(tmp_path)
    d = rd.rollouts / "test"
    d.mkdir(parents=True, exist_ok=True)
    for t in rd.read_splits().ids("test"):  # an earlier attempt scored test, no intent left
        (d / f"{t}__FINAL__t0.json").write_text(json.dumps({"input": None,
            "rollout": {"task_id": t, "output": "", "error": None},
            "score": {"task_id": t, "reward": 1.0, "feedback": "", "n": 1, "stderr": 0.0,
                      "trial_rewards": [1.0], "raw": {}}}), encoding="utf-8")

    def fake_finalize(cmd):  # the same steps harness.finalize takes
        r = RunDir.open(rd.root)
        r.begin_test_attempt()
        payload = {"test": {"reward": 1.0}, "best_id": "cur"}
        (r.root / "final.json").write_text(json.dumps(payload), encoding="utf-8")
        r.commit_test()
        return 0, json.dumps(payload), ""  # run.py prints the returned payload, without the mark

    _act(monkeypatch, capsys, ["finalize", "--n-confirm", "0", *_args(rd, project)],
         Sh(**{"run.py": fake_finalize}))
    assert [e for e in _events(rd) if e["kind"] == "test_rescore_override"]
    final = json.loads((rd.root / "final.json").read_text(encoding="utf-8"))
    assert final["final"] == {"test": {"reward": 1.0}, "best_id": "cur"}
    assert final["test_rescore_override"]["used"] is True
    assert final["test_rescore_override"]["count"] == 1


def test_act_finalize_completion_path_keeps_the_override_mark(tmp_path, capsys, monkeypatch):
    """An override attempt re-scored test, then died before final.json; the next `act finalize`
    completes from the existing rollouts and must still mark final.json (#799)."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from test_digest_and_act_verbs import Sh, _act, _args, _run as _act_run

    monkeypatch.setenv("CAPEVOLVE_ALLOW_TEST_RESCORE", "1")
    rd, project, _, _ = _act_run(tmp_path)
    d = rd.rollouts / "test"
    d.mkdir(parents=True, exist_ok=True)
    for tag in ("FINAL", "FINAL_seed"):
        for t in rd.read_splits().ids("test"):
            (d / f"{t}__{tag}__t0.json").write_text(json.dumps({"input": None,
                "rollout": {"task_id": t, "output": "", "error": None},
                "score": {"task_id": t, "reward": 1.0, "feedback": "", "n": 1, "stderr": 0.0,
                          "trial_rewards": [1.0], "raw": {}}}), encoding="utf-8")
    RunDir.open(rd.root).begin_test_attempt()  # records the override use, then the process dies
    (rd.root / "finalize.intent").write_text(json.dumps({"champion": "seed"}), encoding="utf-8")
    monkeypatch.delenv("CAPEVOLVE_ALLOW_TEST_RESCORE")

    _act(monkeypatch, capsys, ["finalize", "--n-confirm", "0", *_args(rd, project)], Sh())
    final = json.loads((rd.root / "final.json").read_text(encoding="utf-8"))
    assert final["completed_from_existing"] is True
    assert final["test_rescore_override"]["used"] is True
    assert final["test_rescore_override"]["count"] == 1


def test_act_finalize_result_is_readable_by_report_and_dashboard(tmp_path, capsys, monkeypatch):
    """final.json written by `act finalize` keeps the test score at the TOP level, so the report
    does not say NOT FINALIZED and the dashboard sees the held-out reward (T-79)."""
    import subprocess
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from test_digest_and_act_verbs import Sh, _act, _args, _run as _act_run
    from cap_evolve import dashboard

    monkeypatch.delenv("CAPEVOLVE_ALLOW_TEST_RESCORE", raising=False)
    rd, project, _, _ = _act_run(tmp_path)
    d = rd.rollouts / "test"
    d.mkdir(parents=True, exist_ok=True)
    for tag in ("FINAL", "FINAL_seed"):
        for t in rd.read_splits().ids("test"):
            (d / f"{t}__{tag}__t0.json").write_text(json.dumps({"input": None,
                "rollout": {"task_id": t, "output": "", "error": None},
                "score": {"task_id": t, "reward": 1.0, "feedback": "", "n": 1, "stderr": 0.0,
                          "trial_rewards": [1.0], "raw": {}}}), encoding="utf-8")
    (rd.root / "finalize.intent").write_text(json.dumps({"champion": "seed"}), encoding="utf-8")
    _act(monkeypatch, capsys, ["finalize", "--n-confirm", "0", *_args(rd, project)], Sh())

    final = json.loads((rd.root / "final.json").read_text(encoding="utf-8"))
    assert final["test"]["reward"] == 1.0 and final["best_id"] == "seed"
    assert final["champion"] and final["completed_from_existing"] is True
    assert final["final"]["test"] == final["test"]

    repo = Path(__file__).resolve().parents[2]
    r = subprocess.run([sys.executable, str(repo / "skills/phases/report/scripts/run.py"),
                        "--run-dir", str(rd.root), "--no-dashboard"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    md = (rd.root / "report.md").read_text(encoding="utf-8")
    assert "NOT FINALIZED" not in md
    assert "1.0" in md or "1.000" in md
    run = dashboard.reduce_run(RunDir.open(rd.root))
    assert run["summary"]["test_reward"] is not None
