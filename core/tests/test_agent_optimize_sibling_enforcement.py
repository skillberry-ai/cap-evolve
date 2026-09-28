"""``round.py`` must ENFORCE the N>=3 sibling default, not just recommend it.

Audited runs (``.capevolve/run_20260928_v13_.../events.jsonl`` and
``.capevolve/run_20260924_v7_.../events.jsonl``) showed every real round proposing exactly
one candidate, never the N>=3 SKILL.md step 2 already recommends ("sibling candidates,
default N>=3"). ``round.py`` already runs sibling candidates in parallel processes
(``--candidates cand_1,cand_2,cand_3``) — the tooling was never the gap, the guidance being
optional prose was. This pins the guard: fewer than ``round.MIN_SIBLINGS`` candidates now
requires either an explicit ``--single-candidate-justification`` or an auto-detected budget
block read from ``--afford-check-file`` (spend.py's own ``--n-siblings`` output), and either
way the reason is recorded on the ``agent_optimize_round_batch`` event so going serial is
auditable rather than silent.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"


def _round():
    spec = importlib.util.spec_from_file_location("_ao_round_sibling_enforce", SCRIPTS / "round.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


class _Proc:
    """Just enough of subprocess.CompletedProcess for round.py's two subprocess call sites."""

    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_subprocess_run(cmd, capture_output=True, text=True, env=None):
    """Stub both the evaluate phase and gate_check.py — no real rollout is ever paid here."""
    script = str(cmd[1])
    if script.endswith("gate_check.py"):
        return _Proc(0, stdout=json.dumps({
            "candidate": {"reward": 0.5, "stderr": 0.01},
            "gate": {"delta": 0.0, "threshold": 0.05, "resolvable_effect_size": 0.05},
            "verdict": "reject",
            "paired_n": 20,
            "regressions": [],
            "movement": {"broke": [], "fixed": []},
            "n_broke": 0,
            "n_fixed": 0,
            "footprint": {"restricted": False},
        }))
    return _Proc(0, stdout=json.dumps({"reward": 0.5}))


def _run_dir_with_candidates(tmp_path, n_candidates: int):
    """A real run dir, past baseline, with ``n_candidates`` sibling work dirs staged."""
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=20)
    seed = seed_capability_dir(tmp_path, level=3)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=5))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)

    work = run_dir.root / "work"
    work.mkdir(parents=True, exist_ok=True)
    tags = []
    for i in range(n_candidates):
        tag = f"cand_{i + 1}"
        shutil.copytree(run_dir.root / "candidates" / "seed", work / tag)
        tags.append(tag)
    return run_dir, tags


def _round_batch_event(run_dir) -> dict:
    events = [json.loads(l) for l in run_dir.events_path.read_text(encoding="utf-8").splitlines()
              if l.strip()]
    batches = [e for e in events if e.get("kind") == "agent_optimize_round_batch"]
    assert batches, "no agent_optimize_round_batch event was logged"
    return batches[-1]


# ---------------------------------------------------------- pure resolution logic


def test_three_or_more_candidates_need_no_justification_at_all():
    rnd = _round()
    justification, source = rnd.sibling_justification(3, None, None)
    assert justification is None and source is None


def test_below_three_with_nothing_supplied_raises():
    rnd = _round()
    with pytest.raises(rnd.SingleCandidateUnjustified) as exc:
        rnd.sibling_justification(1, None, None)
    msg = str(exc.value)
    assert "N>=3" in msg or "MIN_SIBLINGS" in msg
    assert "--single-candidate-justification" in msg and "--afford-check-file" in msg


def test_below_three_with_blank_justification_still_raises():
    """Free text, but non-empty: whitespace does not count as a recorded reason."""
    rnd = _round()
    with pytest.raises(rnd.SingleCandidateUnjustified):
        rnd.sibling_justification(1, "   ", None)


def test_below_three_with_explicit_justification_is_accepted_and_tagged():
    rnd = _round()
    justification, source = rnd.sibling_justification(
        1, "diagnose surfaced only one well-evidenced cluster this round", None)
    assert justification == "diagnose surfaced only one well-evidenced cluster this round"
    assert source == "explicit"


def test_afford_check_file_reporting_unaffordable_is_accepted(tmp_path):
    rnd = _round()
    f = tmp_path / "afford.json"
    f.write_text(json.dumps({
        "afford": {"affordable": False,
                   "blockers": ["needs 60 rollouts, 10 left under max_metric_calls"]},
    }), encoding="utf-8")
    justification, source = rnd.sibling_justification(1, None, str(f))
    assert source == "afford_unaffordable"
    assert "needs 60 rollouts" in justification


def test_afford_check_file_accepts_the_bare_afford_dict_too(tmp_path):
    """spend.py's full output nests it under "afford"; a caller may also hand the inner dict
    straight through (e.g. having already extracted it) — both shapes must resolve."""
    rnd = _round()
    f = tmp_path / "afford.json"
    f.write_text(json.dumps({"affordable": False, "blockers": ["budget"]}), encoding="utf-8")
    justification, source = rnd.sibling_justification(1, None, str(f))
    assert source == "afford_unaffordable" and "budget" in justification


def test_afford_check_file_reporting_affordable_is_not_a_valid_excuse(tmp_path):
    """affordable: true means 3 siblings WOULD fit — it cannot justify proposing only 1."""
    rnd = _round()
    f = tmp_path / "afford.json"
    f.write_text(json.dumps({"afford": {"affordable": True, "blockers": []}}), encoding="utf-8")
    with pytest.raises(rnd.SingleCandidateUnjustified):
        rnd.sibling_justification(1, None, str(f))


def test_a_missing_or_malformed_afford_check_file_raises_not_silently_passes(tmp_path):
    rnd = _round()
    with pytest.raises(rnd.SingleCandidateUnjustified):
        rnd.sibling_justification(1, None, str(tmp_path / "does_not_exist.json"))


def test_explicit_justification_wins_even_when_an_afford_file_is_also_given(tmp_path):
    """Both supplied: the hand-typed reason is honored rather than silently preferring the file."""
    rnd = _round()
    f = tmp_path / "afford.json"
    f.write_text(json.dumps({"afford": {"affordable": True}}), encoding="utf-8")
    justification, source = rnd.sibling_justification(1, "only one cluster this round", str(f))
    assert source == "explicit" and justification == "only one cluster this round"


# ---------------------------------------------------------- end-to-end via main()


def test_main_refuses_below_three_with_no_justification_and_logs_nothing(tmp_path, monkeypatch):
    rnd = _round()
    run_dir, tags = _run_dir_with_candidates(tmp_path, 1)
    monkeypatch.setattr(rnd.subprocess, "run", _fake_subprocess_run)

    rc = rnd.main(["--run-dir", str(run_dir.root), "--project", str(tmp_path),
                   "--candidates", tags[0], "--n-trials", "1", "--skip-screen-ladder"])
    assert rc == 2

    events = [json.loads(l) for l in run_dir.events_path.read_text(encoding="utf-8").splitlines()
              if l.strip()]
    assert not [e for e in events if e.get("kind") == "agent_optimize_round_batch"], (
        "the round was refused before spending anything, so no round_batch event should exist")


def test_main_proceeds_with_an_explicit_justification_and_records_it(tmp_path, monkeypatch):
    rnd = _round()
    run_dir, tags = _run_dir_with_candidates(tmp_path, 1)
    monkeypatch.setattr(rnd.subprocess, "run", _fake_subprocess_run)

    rc = rnd.main(["--run-dir", str(run_dir.root), "--project", str(tmp_path),
                   "--candidates", tags[0], "--n-trials", "1", "--skip-screen-ladder",
                   "--single-candidate-justification",
                   "diagnose surfaced only one well-evidenced cluster this round"])
    assert rc == 0

    batch = _round_batch_event(run_dir)
    assert batch["n_candidates"] == 1
    assert batch["single_candidate_justification"] == (
        "diagnose surfaced only one well-evidenced cluster this round")
    assert batch["single_candidate_justification_source"] == "explicit"


def test_main_proceeds_when_spend_py_reports_three_siblings_unaffordable(tmp_path, monkeypatch):
    rnd = _round()
    run_dir, tags = _run_dir_with_candidates(tmp_path, 1)
    monkeypatch.setattr(rnd.subprocess, "run", _fake_subprocess_run)

    afford_file = tmp_path / "afford_check.json"
    afford_file.write_text(json.dumps({
        "afford": {"n_siblings": 3, "affordable": False,
                   "blockers": ["needs 60 rollouts, 10 left under max_metric_calls"]},
    }), encoding="utf-8")

    rc = rnd.main(["--run-dir", str(run_dir.root), "--project", str(tmp_path),
                   "--candidates", tags[0], "--n-trials", "1", "--skip-screen-ladder",
                   "--afford-check-file", str(afford_file)])
    assert rc == 0

    batch = _round_batch_event(run_dir)
    assert batch["single_candidate_justification_source"] == "afford_unaffordable"
    assert "needs 60 rollouts" in batch["single_candidate_justification"]


def test_main_still_refuses_when_the_afford_file_says_affordable(tmp_path, monkeypatch):
    """A caller cannot point --afford-check-file at a file that says 3 WOULD fit and use it to
    dodge the guard — that is the exact silent-serial failure this whole change exists to close."""
    rnd = _round()
    run_dir, tags = _run_dir_with_candidates(tmp_path, 1)
    monkeypatch.setattr(rnd.subprocess, "run", _fake_subprocess_run)

    afford_file = tmp_path / "afford_check.json"
    afford_file.write_text(json.dumps({"afford": {"affordable": True}}), encoding="utf-8")

    rc = rnd.main(["--run-dir", str(run_dir.root), "--project", str(tmp_path),
                   "--candidates", tags[0], "--n-trials", "1", "--skip-screen-ladder",
                   "--afford-check-file", str(afford_file)])
    assert rc == 2


def test_main_with_three_candidates_needs_no_justification(tmp_path, monkeypatch):
    """The unaffected path: N>=3 must run exactly as it did before this change."""
    rnd = _round()
    run_dir, tags = _run_dir_with_candidates(tmp_path, 3)
    monkeypatch.setattr(rnd.subprocess, "run", _fake_subprocess_run)

    rc = rnd.main(["--run-dir", str(run_dir.root), "--project", str(tmp_path),
                   "--candidates", ",".join(tags), "--n-trials", "1", "--skip-screen-ladder"])
    assert rc == 0

    batch = _round_batch_event(run_dir)
    assert batch["n_candidates"] == 3
    assert batch["single_candidate_justification"] is None
    assert batch["single_candidate_justification_source"] is None
