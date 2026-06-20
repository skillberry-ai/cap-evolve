"""G3 core-signal tests: per-task impact of prior candidates (C1) and the
infra-noise classification fix (C3).

These guard the two highest-value behavior changes:
  - the optimizer is shown the SPECIFIC tasks a prior candidate BROKE/FIXED, and
  - a mostly-passing task with one errored trial is solid/protected, NOT bucketed
    as uncontrollable infra "ignore".
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


def _write_rollout(run_dir, tag, task_id, k, reward, *, errored=False, split="val"):
    """Persist one synthetic per-trial rollout file in the harness's on-disk format."""
    vdir = run_dir.rollouts / split
    vdir.mkdir(parents=True, exist_ok=True)
    rec = {
        "input": {},
        "rollout": {"task_id": task_id, "error": "boom" if errored else None},
        "score": {"task_id": task_id, "reward": reward, "feedback": "",
                  "raw": {"errored": errored}},
    }
    (vdir / f"{task_id}__{tag}__t{k}.json").write_text(json.dumps(rec), encoding="utf-8")


def test_per_task_impact_lists_broken_task():
    """A candidate that regressed a previously-passing task must be reported in the
    per-task impact block as having BROKEN that task."""
    from cap_evolve import RunDir, harness
    from cap_evolve.memory import RejectedMemory
    import tempfile

    tmp = Path(tempfile.mkdtemp())
    rd = RunDir.create(tmp / ".capevolve", ts="impact")

    # Parent (seed): tasks 1 & 2 pass, task 3 fails.
    for tid, r in [("1", 1.0), ("2", 1.0), ("3", 0.0)]:
        _write_rollout(rd, "seed", tid, 0, r)
    # Candidate cand_0001: BROKE task 2 (1->0), FIXED task 3 (0->1), task 1 unchanged.
    for tid, r in [("1", 1.0), ("2", 0.0), ("3", 1.0)]:
        _write_rollout(rd, "cand_0001", tid, 0, r)

    # Lineage: cand_0001 forked from seed (a step event), and it was rejected.
    rd.log_event("step", candidate="cand_0001", parent="seed", accept=False)
    rejected = RejectedMemory(rd.rejected_path)
    rejected.add("cand_0001", "candidate cand_0001 (val 0.667)", "no significant gain", 0.667)

    block = harness._per_task_impact_block(rd, rejected, None)
    assert block, "expected a non-empty per-task impact block"
    assert "cand_0001" in block
    # The broken task id must be surfaced in the BROKE set.
    assert "BROKE" in block and "2" in block
    assert "FIXED" in block and "3" in block

    # And the memory record carries the localized broke/fixed lists (C4).
    impact = harness._candidate_task_impact(rd, "cand_0001", "val",
                                            parent_of={"cand_0001": "seed"})
    assert impact["broke"] == ["2"]
    assert impact["fixed"] == ["3"]


def test_mostly_passing_errored_trial_not_infra_ignore():
    """A task that passes on most trials but had ONE errored trial is solid/flaky and
    PROTECTED — it must NOT be bucketed as uncontrollable infra-ignore (C3)."""
    from cap_evolve import harness

    # mostly_pass: 2 of 3 trials passed, one errored -> mean ~0.67, minority errored.
    mostly_pass = {"task_id": "mp", "reward": 0.667, "feedback": "",
                   "raw": {"errored": True, "errored_trials": 1, "n_trials": 3}}
    # truly_infra: all trials errored, mean 0 -> uncontrollable.
    truly_infra = {"task_id": "ti", "reward": 0.0, "feedback": "",
                   "raw": {"errored": True, "errored_trials": 3, "n_trials": 3}}
    # clean_fail: no error, reward 0 -> always-failing (actionable).
    clean_fail = {"task_id": "cf", "reward": 0.0, "feedback": "",
                  "raw": {"errored": False, "errored_trials": 0, "n_trials": 3}}

    assert harness._is_infra_ignore(mostly_pass) is False
    assert harness._is_infra_ignore(truly_infra) is True

    errored, always_fail, flaky, solid = harness._classify(
        [mostly_pass, truly_infra, clean_fail])
    ignore_ids = {pt["task_id"] for pt in errored}
    assert "mp" not in ignore_ids          # mostly-passing is NOT ignored
    assert "ti" in ignore_ids              # truly-infra IS ignored
    # mostly-passing falls through to flaky (protected/actionable), never "ignore"
    assert "mp" in {pt["task_id"] for pt in flaky}
    assert "cf" in {pt["task_id"] for pt in always_fail}
