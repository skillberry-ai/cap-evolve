"""``provisional`` candidates: sequential evidence on the SAME candidate, not compounded
edits (agent-optimize round 4).

A candidate with Δ>0 that misses the significance gate is not the same as one with
Δ<=0 — the first is real positive signal the gate could not yet resolve at this n. This
locks down the mechanism that lets the driver buy more trials on that SAME, unmodified
candidate instead of discarding it or building a new edit on unconfirmed ground:

  * ``loop.pool_split_results`` pools two evaluations' trial vectors correctly (not two
    means averaged) — the primitive scenario (a)/(b) below are built on;
  * a pooled evaluation that now crosses the gate promotes; one that still doesn't is
    correctly abandoned, never silently accepted;
  * ``commit.py --decision provisional`` books the state without prematurely charging an
    iteration or moving ``best_id``, and a later real accept/reject on the SAME candidate
    id is still allowed;
  * ``dashboard.reduce_run`` renders a ``provisional`` verdict instead of choking on it or
    misreporting it as accepted/rejected;
  * ``grow.py`` end-to-end: new trials land under a throwaway tag, get pooled, and are
    merged onto the candidate's own tag so later readers see one candidate at the pooled n.

Offline, deterministic, zero API.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
AGENT_SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"
AGENT_COMMIT = AGENT_SCRIPTS / "commit.py"
AGENT_GROW = AGENT_SCRIPTS / "grow.py"

sys.path.insert(0, str(CORE))


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    yield
    os.environ.clear()
    os.environ.update(old)


def _sc(task_id, trial_rewards, feedback=""):
    """A per_task dict shaped like ``Score.to_dict()``, for building synthetic
    ``SplitResult``s without running any adapter."""
    from cap_evolve.stats import mean, stderr
    tr = list(trial_rewards)
    return {
        "task_id": task_id, "reward": mean(tr), "feedback": feedback,
        "n": len(tr), "stderr": stderr(tr), "trial_rewards": tr,
        "raw": {"errored": False, "errored_trials": 0, "valid_trials": len(tr),
                "n_trials": len(tr)},
        "metrics": [],
    }


def _split(per_task):
    from cap_evolve.loop import SplitResult
    return SplitResult.from_dict({"split": "val", "per_task": per_task,
                                  "reward": 0.0, "stderr": 0.0,
                                  "n_tasks": len(per_task), "n_scored": len(per_task)})


# --- pool_split_results: real pooling, not two means averaged ---------------

def test_pool_split_results_concatenates_trial_vectors_not_means():
    from cap_evolve.loop import pool_split_results

    a = _split([_sc("t1", [1.0, 0.0]), _sc("t2", [0.0, 0.0])])
    b = _split([_sc("t1", [1.0]), _sc("t2", [1.0, 0.0])])
    pooled = pool_split_results(a, b)

    by_id = {pt["task_id"]: pt for pt in pooled.per_task}
    # t1: [1,0] + [1] = [1,0,1] -> mean 2/3, n=3 (NOT (0.5+1.0)/2 = 0.75, the wrong
    # "average the two means" shortcut this helper exists to avoid).
    assert by_id["t1"]["n"] == 3
    assert by_id["t1"]["reward"] == pytest.approx(2 / 3)
    # t2: [0,0] + [1,0] = [0,0,1,0] -> mean 0.25, n=4
    assert by_id["t2"]["n"] == 4
    assert by_id["t2"]["reward"] == pytest.approx(0.25)
    # Overall reward is the mean of the (correctly pooled) per-task means, over 2 tasks.
    assert pooled.reward == pytest.approx((2 / 3 + 0.25) / 2)
    assert pooled.n_tasks == 2


def test_pool_split_results_keeps_a_task_present_on_only_one_side():
    from cap_evolve.loop import pool_split_results

    a = _split([_sc("t1", [1.0, 1.0])])
    b = _split([_sc("t2", [0.0, 0.0])])
    pooled = pool_split_results(a, b)
    ids = {pt["task_id"] for pt in pooled.per_task}
    assert ids == {"t1", "t2"}
    by_id = {pt["task_id"]: pt for pt in pooled.per_task}
    assert by_id["t1"]["n"] == 2
    assert by_id["t2"]["n"] == 2


# --- (a) pooled evaluation crosses the bar; (b) pooled evaluation still doesn't ---------

def _gate(current, candidate, k_se=1.0):
    from cap_evolve import harness
    from cap_evolve.gate import decide
    deltas = harness._paired_deltas(current, candidate)
    return decide(current.reward, candidate.reward, split="val", mode="paired", k_se=k_se,
                 candidate_stderr=candidate.stderr, current_stderr=current.stderr,
                 paired_deltas=deltas, coverage=candidate.coverage)


_TASKS = ("t1", "t2", "t3", "t4", "t5", "t6")


def _current_all_zero():
    return _split([_sc(t, [0.0, 0.0, 0.0, 0.0]) for t in _TASKS])


def test_provisional_candidate_promotes_once_pooled_trials_cross_the_bar():
    from cap_evolve.loop import pool_split_results

    current = _current_all_zero()
    # First measurement (n=4 trials/task): one task hit once, the rest never did — a
    # real but thin positive signal that misses the bar at only 6 tasks.
    first = _split([_sc("t1", [0, 0, 0, 0]), _sc("t2", [0, 0, 0, 0]), _sc("t3", [0, 0, 0, 0]),
                    _sc("t4", [1, 0, 0, 0]), _sc("t5", [0, 0, 0, 0]), _sc("t6", [0, 0, 0, 0])])
    d0 = _gate(current, first)
    assert not d0.indecisive
    assert d0.delta > 0, "the direction must be positive for this to be a provisional case"
    assert not d0.accept, "the bar must be missed at n=4, or growing n proves nothing"

    # 8 more trials/task on the SAME candidate, converging every task toward the SAME
    # true rate (~35-50%) — the honest positive effect this candidate always had, now
    # resolvable because the across-task spread that hid it has shrunk.
    more = _split([_sc("t1", [1, 1, 1, 0, 0, 0, 0, 0]), _sc("t2", [1, 1, 1, 1, 0, 0, 0, 0]),
                  _sc("t3", [1, 1, 1, 0, 0, 0, 0, 0]), _sc("t4", [1, 1, 1, 1, 0, 0, 0, 0]),
                  _sc("t5", [1, 1, 1, 1, 0, 0, 0, 0]), _sc("t6", [1, 1, 1, 0, 0, 0, 0, 0])])
    pooled = pool_split_results(first, more)
    d1 = _gate(current, pooled)
    assert d1.accept, f"pooled evaluation should have crossed the bar: {d1.reason}"


def test_provisional_candidate_still_abandoned_when_pooling_does_not_resolve_it():
    from cap_evolve.loop import pool_split_results

    current = _current_all_zero()
    first = _split([_sc("t1", [0, 0, 0, 0]), _sc("t2", [0, 0, 0, 0]), _sc("t3", [0, 0, 0, 0]),
                    _sc("t4", [1, 0, 0, 0]), _sc("t5", [0, 0, 0, 0]), _sc("t6", [0, 0, 0, 0])])
    d0 = _gate(current, first)
    assert d0.delta > 0 and not d0.accept

    # The extra trials confirm the SAME thin, noisy signal rather than a real effect —
    # the honest outcome is still a reject at the pooled n, and it must not become a
    # silent accept just because more budget was spent on this candidate.
    more = _split([_sc("t1", [0] * 8), _sc("t2", [0] * 8), _sc("t3", [0] * 8),
                  _sc("t4", [1, 0, 0, 0, 0, 0, 0, 0]), _sc("t5", [0] * 8), _sc("t6", [0] * 8)])
    pooled = pool_split_results(first, more)
    d1 = _gate(current, pooled)
    assert not d1.accept, f"pooling must not manufacture an accept: {d1.reason}"


# --- commit.py --decision provisional ---------------------------------------

def _run_dir(tmp_path, ts):
    from cap_evolve import Budget, RunDir
    return RunDir.create(tmp_path / ".capevolve", ts=ts,
                         budget=Budget(max_iterations=10, max_metric_calls=400, stall=10))


def _commit(run_dir, candidate_id, from_dir, decision, val=None, extra=()):
    env = dict(os.environ, PYTHONPATH=str(CORE))
    cmd = [sys.executable, str(AGENT_COMMIT), "--run-dir", str(run_dir.root),
           "--candidate-id", candidate_id, "--from-dir", str(from_dir),
           "--decision", decision, "--note", f"{decision} via test"]
    if val is not None:
        cmd += ["--val", str(val)]
    cmd += list(extra)
    return subprocess.run(cmd, capture_output=True, text=True, env=env,
                          cwd=str(AGENT_COMMIT.parent))


def _events(run_dir, kind=None):
    evs = [json.loads(ln) for ln in
           run_dir.events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return evs if kind is None else [e for e in evs if e.get("kind") == kind]


def test_commit_provisional_books_the_verdict_without_advancing_the_run(tmp_path):
    run_dir = _run_dir(tmp_path, "prov1")
    run_dir.set_best("seed")
    work = tmp_path / "cand_1"
    work.mkdir()
    (work / "policy.md").write_text("v1\n", encoding="utf-8")

    out = _commit(run_dir, "cand_1", work, "provisional", val=0.6)
    assert out.returncode == 0, out.stdout + out.stderr
    payload = json.loads(out.stdout)
    assert payload["decision"] == "provisional"

    # Snapshotted for the audit trail, but NOT promoted...
    assert run_dir.candidate_dir("cand_1").is_dir()
    assert run_dir.best_id == "seed"
    # ...and the iteration/stall/JOURNAL machinery must not have advanced: the round is
    # not over yet, it is pending more evidence.
    assert run_dir.spent.iterations == 0
    assert not _events(run_dir, "step")

    provisional_events = _events(run_dir, "provisional")
    assert len(provisional_events) == 1
    assert provisional_events[0]["verdict"] == "provisional"
    assert provisional_events[0]["candidate"] == "cand_1"


def test_commit_accept_after_a_provisional_commit_is_still_allowed(tmp_path):
    """The candidate-id reuse guard blocks a second accept/reject over the SAME
    rollouts — it must NOT block the real decision that follows a provisional one."""
    run_dir = _run_dir(tmp_path, "prov2")
    run_dir.set_best("seed")
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "policy.md").write_text("seed\n", encoding="utf-8")
    run_dir.snapshot("seed", seed_dir)
    work = tmp_path / "cand_1"
    work.mkdir()
    (work / "policy.md").write_text("v1\n", encoding="utf-8")

    out1 = _commit(run_dir, "cand_1", work, "provisional", val=0.6)
    assert out1.returncode == 0, out1.stdout + out1.stderr

    out2 = _commit(run_dir, "cand_1", work, "accept", val=0.7)
    assert out2.returncode == 0, out2.stdout + out2.stderr
    payload = json.loads(out2.stdout)
    assert payload["decision"] == "accept"
    assert payload["best_id"] == "cand_1"
    assert run_dir.spent.iterations == 1
    assert _events(run_dir, "step")


def test_commit_rejects_reject_basis_on_a_provisional_decision(tmp_path):
    run_dir = _run_dir(tmp_path, "prov3")
    run_dir.set_best("seed")
    work = tmp_path / "cand_1"
    work.mkdir()
    (work / "policy.md").write_text("v1\n", encoding="utf-8")
    out = _commit(run_dir, "cand_1", work, "provisional", val=0.6,
                  extra=["--reject-basis", "gate"])
    assert out.returncode != 0
    assert "reject-basis" in out.stdout


# --- dashboard.reduce_run must not choke on a provisional verdict -----------

def test_dashboard_reduce_run_handles_provisional_verdict(tmp_path):
    from cap_evolve import harness
    from cap_evolve.dashboard import reduce_run

    run_dir = _run_dir(tmp_path, "prov4")
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "policy.md").write_text("seed\n", encoding="utf-8")
    run_dir.snapshot("seed", seed_dir)
    run_dir.set_best("seed")
    run_dir.log_event("baseline", val=0.5, stderr=0.0, n_scored=4, n_tasks=4)

    work = tmp_path / "cand_1"
    work.mkdir()
    (work / "policy.md").write_text("v1\n", encoding="utf-8")
    out = _commit(run_dir, "cand_1", work, "provisional", val=0.6)
    assert out.returncode == 0, out.stdout + out.stderr

    result = reduce_run(run_dir)  # must not raise
    graph = result["graph"]
    node = next((n for n in graph["nodes"] if n["id"] == "cand_1"), None)
    assert node is not None, "the provisional candidate must still appear in the graph"
    assert node["status"] == "provisional"
    assert result["summary"]["counts"].get("provisional") == 1
    # A provisional candidate is not the champion — it must never move `best`/best_id.
    assert result["summary"]["best_id"] == "seed"


# --- grow.py: pool + merge trials onto the candidate's own tag --------------

_SCRIPTED_ADAPTER = '''
from cap_evolve import CapabilityAdapter, Rollout, Score, Task

class Adapter(CapabilityAdapter):
    SCRIPTS = {"t1": [1.0], "t2": [1.0], "t3": [0.0], "t4": [1.0]}

    def tasks(self, split):
        return [Task(id=t, input=t, target="1") for t in sorted(self.SCRIPTS)]

    def run_target(self, task, ctx, *, seed=0):
        r = self.SCRIPTS[task.id][0]
        return Rollout(task_id=task.id, output=str(r))

    def score(self, task, rollout):
        r = float(rollout.output)
        return Score(task_id=task.id, reward=r, feedback="", trial_rewards=[r])

    def apply(self, candidate_dir, edits=None):
        return None
'''


def test_grow_merges_new_trials_onto_the_candidates_own_tag(tmp_path):
    from cap_evolve import RunDir, harness

    project = tmp_path / "project"
    (project / "adapters").mkdir(parents=True)
    (project / "adapters" / "adapter.py").write_text(_SCRIPTED_ADAPTER, encoding="utf-8")

    run_dir = _run_dir(tmp_path, "grow1")
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    run_dir.snapshot("seed", seed_dir)
    run_dir.set_best("seed")

    from cap_evolve.check import load_adapter
    adapter = load_adapter(project)
    run_dir.write_splits(harness.Splits(
        train=[], val=["t1", "t2", "t3", "t4"], test=[], seed=0))

    # "seed" (current best) never passes any task -> Δ>0 whenever the candidate does.
    harness.evaluate_candidate(adapter, seed_dir, run_dir=run_dir, split="val",
                               n_trials=1, tag="seed")

    cand_dir = tmp_path / "cand_1"
    cand_dir.mkdir()
    run_dir.snapshot("cand_1", cand_dir)
    # First measurement: 3 of 4 tasks pass -> directionally positive.
    harness.evaluate_candidate(adapter, cand_dir, run_dir=run_dir, split="val",
                               n_trials=1, tag="cand_1")
    before = harness.split_result_from_rollouts(run_dir, "cand_1", "val")
    assert before.n_scored == 4

    env = dict(os.environ, PYTHONPATH=str(CORE))
    out = subprocess.run(
        [sys.executable, str(AGENT_GROW), "--run-dir", str(run_dir.root),
         "--project", str(project), "--candidate", "cand_1", "--current", "seed",
         "--add-trials", "1", "--growth-round", "1"],
        capture_output=True, text=True, env=env, cwd=str(AGENT_GROW.parent))
    assert out.returncode == 0, out.stdout + out.stderr
    payload = json.loads(out.stdout)
    assert payload["paired_n"] == 4

    after = harness.split_result_from_rollouts(run_dir, "cand_1", "val")
    by_id = {pt["task_id"]: pt for pt in after.per_task}
    # 1 original trial + 1 grow trial, pooled onto the SAME tag.
    assert all(pt["n"] == 2 for pt in by_id.values()), by_id
    # No stray throwaway-tag files left behind after the merge.
    vdir = run_dir.rollouts / "val"
    assert not list(vdir.glob("*__cand_1__grow1__t*.json"))

    # grow.py persists its POOLED row in round.py's own `work/` table shape, so the final
    # commit books the post-growth verdict and numbers. Without it, commit.py reads the
    # round's PRE-growth table and a promote is logged as `gate_verdict: reject` — the
    # accept then reads as a driver override of a gate that in fact accepted at pooled n.
    # (this adapter's `apply` is a no-op, so the candidate measures identically to the
    # parent — Δ=0, the honest pooled verdict is `reject`.)
    assert payload["verdict"] == "reject", payload
    (run_dir.root / "work").mkdir(exist_ok=True)
    stale = run_dir.root / "work" / "round_i0.json"
    stale.write_text(json.dumps({"candidates": [
        {"tag": "cand_1", "verdict": "accept", "gate_delta": 0.75, "n": 4}]}), encoding="utf-8")
    os.utime(stale, (1, 1))  # older than grow.py's row, which must win
    rc = _commit(run_dir, "cand_1", cand_dir, "reject", val=after.reward,
                 extra=["--reject-basis", "gate"])
    assert rc.returncode == 0, rc.stdout + rc.stderr
    ev = _events(run_dir, "reject")[-1]
    assert ev["gate_verdict"] == "reject", ev
    assert ev["overrode_gate"] is False, ev
    # ...and the numbers on the event are the POOLED ones, not the stale table's Δ=0.75.
    # `gate_*` is the field naming `dashboard.reduce_run` reads verbatim onto a graph node.
    assert ev["gate_n"] == 4 and ev["gate_delta"] == 0.0, ev
