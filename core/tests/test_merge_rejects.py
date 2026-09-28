"""merge_rejects.py — systematically try combining safe-but-REJECTED candidates, the gap
`merge_search.py`'s own compliance check leaves open (it only ever looks at ACCEPTED
candidates). A real multi-hour run on a multi-turn tool-use benchmark rejected 6 candidates in a row;
two of them (cand_4, cand_5) each individually measured a positive, zero-regression, still-
sub-threshold signal, and the optimizer improvised combining them by hand (cand_6) — this
module is what makes that a systematic step instead of a one-off improvisation.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"


def _env() -> dict:
    return dict(os.environ, CAPEVOLVE_CORE=str(REPO / "core"),
                CAPEVOLVE_SKILLS_DIR=str(REPO / "skills"))


def _load_merge_rejects():
    spec = importlib.util.spec_from_file_location("merge_rejects", SCRIPTS / "merge_rejects.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _run_dir(tmp_path):
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=8)
    seed = seed_capability_dir(tmp_path, level=0)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci",
                            budget=Budget(max_iterations=10, stall=10))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)
    return run_dir


def _record_targets(run_dir, tag, task_ids):
    line = json.dumps({"owner": tag, "status": "proposed", "tasks": list(task_ids)})
    with (run_dir.root / "mechanisms.jsonl").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _reject(run_dir, tag, *, gate_delta, broke=None, note="", reject_basis="gate"):
    run_dir.log_event("reject", candidate=tag, note=note, reject_basis=reject_basis,
                      gate_delta=gate_delta, broke=list(broke or []), fixed=[],
                      n_broke=len(broke or []), n_fixed=0)


# ---- (a) safe-reject identification ---------------------------------------------------------

def test_identifies_safe_rejects_and_excludes_unsafe_ones(tmp_path):
    mr = _load_merge_rejects()
    run_dir = _run_dir(tmp_path)

    _reject(run_dir, "cand_safe_pos", gate_delta=0.02, broke=[])
    _reject(run_dir, "cand_safe_zero", gate_delta=0.0, broke=[])
    _reject(run_dir, "cand_negative", gate_delta=-0.01, broke=[])          # unsafe: delta < 0
    _reject(run_dir, "cand_broke", gate_delta=0.05, broke=["t3"])          # unsafe: regressed
    _reject(run_dir, "cand_no_gate", gate_delta=None, broke=None,
            reject_basis="screen_kill")                                   # unsafe: no gate evidence

    safe = mr.find_safe_rejects(run_dir.root)
    assert set(safe) == {"cand_safe_pos", "cand_safe_zero"}


# ---- (b) below threshold / non-disjoint: no warning ------------------------------------------

def test_no_warning_with_fewer_than_min_safe_rejects(tmp_path):
    mr = _load_merge_rejects()
    run_dir = _run_dir(tmp_path)

    _reject(run_dir, "cand_a", gate_delta=0.02, broke=[])
    _record_targets(run_dir, "cand_a", ["t0", "t1"])
    _reject(run_dir, "cand_b", gate_delta=0.01, broke=[])
    _record_targets(run_dir, "cand_b", ["t2", "t3"])

    assert mr.check_rejects_compliance(run_dir) is None


def test_no_warning_when_safe_rejects_are_not_disjoint(tmp_path):
    mr = _load_merge_rejects()
    run_dir = _run_dir(tmp_path)

    for tag, tids in (("cand_a", ["t0", "t1"]), ("cand_b", ["t1", "t2"]),
                      ("cand_c", ["t2", "t3"])):
        _reject(run_dir, tag, gate_delta=0.02, broke=[])
        _record_targets(run_dir, tag, tids)

    # every pair overlaps somewhere (a&b share t1, b&c share t2, a&c share nothing but no
    # size-3 clique exists) — no disjoint group of size >= 3.
    assert mr.check_rejects_compliance(run_dir) is None


# ---- (c) 3+ disjoint safe rejects, no prior attempt: warning fires ---------------------------

def test_fires_compliance_warning_for_three_disjoint_safe_rejects(tmp_path):
    mr = _load_merge_rejects()
    run_dir = _run_dir(tmp_path)

    for tag, tids, delta in (("cand_4", ["t0", "t1"], 0.02),
                             ("cand_5", ["t2", "t3"], 0.015),
                             ("cand_7", ["t4", "t5"], 0.01)):
        _reject(run_dir, tag, gate_delta=delta, broke=[])
        _record_targets(run_dir, tag, tids)
    # an unsafe reject present too, must not count towards or block the group
    _reject(run_dir, "cand_bad", gate_delta=-0.05, broke=["t6"])
    _record_targets(run_dir, "cand_bad", ["t6"])

    warning = mr.check_rejects_compliance(run_dir)
    assert warning is not None
    assert warning["reason"] == "safe_rejects_not_merged"
    assert warning["safe_reject_candidates"] == ["cand_4", "cand_5", "cand_7"]
    assert warning["evidence"]["cand_4"]["gate_delta"] == 0.02
    assert warning["evidence"]["cand_4"]["broke"] == []

    # main() logs it to events.jsonl
    rc = mr.main(["--run-dir", str(run_dir.root), "--project", str(tmp_path / "project")])
    assert rc == 0
    events = [json.loads(ln) for ln in run_dir.events_path.read_text().splitlines() if ln.strip()]
    fired = [e for e in events if e["kind"] == "merge_rejects_compliance_warning"]
    assert fired, "merge_rejects_compliance_warning was not logged to events.jsonl"
    assert fired[-1]["safe_reject_candidates"] == ["cand_4", "cand_5", "cand_7"]


def test_no_warning_once_a_merge_of_rejects_was_proposed(tmp_path):
    mr = _load_merge_rejects()
    run_dir = _run_dir(tmp_path)

    for tag, tids in (("cand_4", ["t0", "t1"]), ("cand_5", ["t2", "t3"]),
                      ("cand_7", ["t4", "t5"])):
        _reject(run_dir, tag, gate_delta=0.02, broke=[])
        _record_targets(run_dir, tag, tids)

    assert mr.check_rejects_compliance(run_dir) is not None
    run_dir.log_event("merge_rejects_propose", rejects=["cand_4", "cand_5"], tag="mergereject_x")
    assert mr.check_rejects_compliance(run_dir) is None


# ---- (d) --propose builds a real combined candidate dir --------------------------------------

TOOLS_BASE = '''
def fn_a(x):
    return x

def fn_b(x):
    return x

def fn_c(x):
    return x
'''

TOOLS_FIX_A = '''
def fn_a(x):
    return x + "MARK_A"

def fn_b(x):
    return x

def fn_c(x):
    return x
'''

TOOLS_FIX_B = '''
def fn_a(x):
    return x

def fn_b(x):
    return x + "MARK_B"

def fn_c(x):
    return x
'''

TOOLS_FIX_C = '''
def fn_a(x):
    return x

def fn_b(x):
    return x

def fn_c(x):
    return x + "MARK_C"
'''


def _write_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "adapters").mkdir(parents=True)
    (project / "adapters" / "adapter.py").write_text('''
from pathlib import Path
from cap_evolve.adapter import CapabilityAdapter
from cap_evolve.trials import run_trials_pool
from cap_evolve.types import Task, Rollout, Score

NEEDS = {"t0": "MARK_A", "t1": "MARK_A", "t2": "MARK_B", "t3": "MARK_B",
        "t4": "MARK_C", "t5": "MARK_C"}

class Adapter(CapabilityAdapter):
    def tasks(self, split):
        return [Task(id=f"t{i}") for i in range(6)]

    def run_target(self, task, ctx, *, seed=0):
        src = (Path(ctx) / "tools" / "tools.py").read_text(encoding="utf-8")
        return Rollout(task_id=task.id, output=src)

    def run_trials(self, tasks, ctx, *, n_trials, base_seed):
        return run_trials_pool(lambda t, s: self.run_target(t, ctx, seed=s), tasks,
                               n_trials=n_trials, base_seed=base_seed)

    def score(self, task, rollout):
        src = rollout.output or ""
        need = NEEDS.get(task.id)
        ok = True if need is None else (need in src)
        return Score(task_id=task.id, reward=1.0 if ok else 0.0,
                     feedback="ok" if ok else f"needs {need}", trial_rewards=[1.0 if ok else 0.0])
''', encoding="utf-8")
    return project


def _seed_capability(root: Path, name: str, tools_src: str) -> Path:
    d = root / name
    (d / "tools").mkdir(parents=True, exist_ok=True)
    (d / "tools" / "tools.py").write_text(tools_src, encoding="utf-8")
    (d / "policy").mkdir(parents=True, exist_ok=True)
    (d / "policy" / "policy.md").write_text("base policy\n", encoding="utf-8")
    return d


def _run_dir_with_rejects(tmp_path):
    """A run dir where three candidates (A, B, C) were each measured and REJECTED as safe —
    zero regressions, non-negative gate_delta — and snapshotted as ordinary candidates
    (``commit.py``'s own behaviour on ANY decision, accept or reject)."""
    from cap_evolve import Budget, RunDir, harness

    project = _write_project(tmp_path)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=10))
    seed = _seed_capability(tmp_path, "seed_capability", TOOLS_BASE)
    harness.ensure_splits(None, run_dir, seed=0,
                          split_ids={"val": [f"t{i}" for i in range(6)], "train": [], "test": []})
    run_dir.snapshot("seed", seed)

    for tag, src, tids, delta in (("cand_A", TOOLS_FIX_A, ["t0", "t1"], 0.02),
                                  ("cand_B", TOOLS_FIX_B, ["t2", "t3"], 0.015),
                                  ("cand_C", TOOLS_FIX_C, ["t4", "t5"], 0.01)):
        cdir = _seed_capability(tmp_path / "candidates_src", tag, src)
        run_dir.snapshot(tag, cdir)
        run_dir.log_event("reject", candidate=tag, note=f"rejected {tag}", reject_basis="gate",
                          gate_delta=delta, broke=[], fixed=[], n_broke=0, n_fixed=0)
        _record_targets(run_dir, tag, tids)
    return run_dir, project


def test_propose_builds_combined_candidate_from_disjoint_safe_rejects(tmp_path):
    run_dir, project = _run_dir_with_rejects(tmp_path)

    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "merge_rejects.py"),
         "--run-dir", str(run_dir.root), "--project", str(project),
         "--propose", "--rejects", "cand_A,cand_B", "--base", "seed",
         "--n", "2", "--conc", "1"],
        capture_output=True, text=True, env=_env())
    assert p.returncode == 0, f"merge_rejects.py --propose failed: {p.stdout}\n{p.stderr}"
    out = json.loads(p.stdout)

    prop = out["propose"]
    assert prop["built"], f"combined candidate was not built: {prop}"
    merged_src = (run_dir.root / "work" / prop["tag"] / "tools" / "tools.py").read_text()
    assert "MARK_A" in merged_src and "MARK_B" in merged_src, (
        f"merged artifact does not carry both safe rejects' fixes:\n{merged_src}")

    # mechanisms.jsonl records the attempt, same ledger merge_search.py's merges use
    ledger = [json.loads(ln) for ln in
             (run_dir.root / "mechanisms.jsonl").read_text().splitlines() if ln.strip()]
    rows = [r for r in ledger if r["owner"] == prop["tag"]]
    assert rows, "the merge-of-rejects was not recorded in mechanisms.jsonl"

    # and a follow-up compliance check on the SAME run dir must not fire again: the
    # merge_rejects_propose event this call logged is the "already attempted" marker.
    mr = _load_merge_rejects()
    assert mr.check_rejects_compliance(run_dir) is None


def test_propose_refuses_a_real_edit_collision(tmp_path):
    """A and C both had cand_A/cand_C rewrite the SAME function differently — the merge must
    be refused, never force-merged (mirrors merge_search.py's own refusal for overlaps)."""
    run_dir, project = _run_dir_with_rejects(tmp_path)
    # overwrite cand_C's snapshot so it collides with cand_A on fn_a instead of fn_c
    other_a = _seed_capability(tmp_path / "candidates_src", "cand_C_collide", '''
def fn_a(x):
    return x + "OTHER_MARK_A"

def fn_b(x):
    return x

def fn_c(x):
    return x
''')
    run_dir.snapshot("cand_C", other_a)

    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "merge_rejects.py"),
         "--run-dir", str(run_dir.root), "--project", str(project),
         "--propose", "--rejects", "cand_A,cand_C", "--base", "seed",
         "--n", "2", "--conc", "1"],
        capture_output=True, text=True, env=_env())
    out = json.loads(p.stdout)
    assert "error" in out["propose"]
    assert not out["propose"].get("built")
