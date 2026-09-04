"""merge_search — disjoint-cluster survivors get merged via existing integrate.py machinery,
and the result is an ordinary candidate directory that round.py's normal gate cascade picks up
with no special-casing (#438, child of #434/#438's "4. Concurrent multi-issue candidates, then
graph-search merge").

A fixture capability exposes a `tools/tools.py` with three independent functions. Two survivor
branches each fix ONE function (disjoint edits); a third branch fixes the SAME function branch A
does, but differently (an overlapping edit). merge_search.py must:
  1. identify the (A, B) pair as mergeable and the (A, C) / (B, C)-with-C pairs as NOT (shared
     function), never attempting a merge across a real edit collision;
  2. build the (A, B) merge via `integrate.py`/`funcmerge.py` — the SAME merge engine any
     hand-driven merge in this skill uses, not a bespoke one;
  3. leave the merged artifact as a plain `$R/work/merge_A_B` directory that `round.py` gates
     exactly like any other candidate tag, control included.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"

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

# Overlaps branch A: rewrites fn_a DIFFERENTLY — a real edit collision, not a pure insertion.
TOOLS_FIX_A_DIFFERENTLY = '''
def fn_a(x):
    return x + "OTHER_MARK_A"

def fn_b(x):
    return x

def fn_c(x):
    return x
'''


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _write_project(tmp_path: Path) -> Path:
    """A tiny cap-evolve project whose adapter scores tasks by reading tools/tools.py's
    text — t0/t1 need MARK_A, t2/t3 need MARK_B, t4/t5 pass unconditionally (stable canaries).
    """
    project = tmp_path / "project"
    (project / "adapters").mkdir(parents=True)
    (project / "adapters" / "adapter.py").write_text('''
from pathlib import Path
from cap_evolve.adapter import CapabilityAdapter
from cap_evolve.trials import run_trials_pool
from cap_evolve.types import Task, Rollout, Score

NEEDS = {"t0": "MARK_A", "t1": "MARK_A", "t2": "MARK_B", "t3": "MARK_B"}

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


def _run_dir_with_survivors(tmp_path: Path):
    """A run dir past baseline, with base/A/B/C staged under work/ like a real round would
    leave them, plus mechanisms.jsonl rows recording each survivor's target tasks."""
    from cap_evolve import Budget, RunDir, harness

    project = _write_project(tmp_path)
    adapter = _load("forge_project_adapter", project / "adapters" / "adapter.py").Adapter()

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=10))
    seed = _seed_capability(tmp_path, "seed_capability", TOOLS_BASE)
    harness.ensure_splits(adapter, run_dir, seed=0,
                          split_ids={"val": [f"t{i}" for i in range(6)], "train": [], "test": []})
    harness.baseline(adapter, seed, run_dir=run_dir)

    work = run_dir.root / "work"
    for tag, src in (("A", TOOLS_FIX_A), ("B", TOOLS_FIX_B), ("C", TOOLS_FIX_A_DIFFERENTLY)):
        _seed_capability(work, tag, src)

    mech = SCRIPTS / "mechanisms.py"
    for tag, tids in (("A", ["t0", "t1"]), ("B", ["t2", "t3"]), ("C", ["t0", "t1"])):
        subprocess.run([sys.executable, str(mech), "add", "--run-dir", str(run_dir.root),
                       "--owner", tag, "--status", "proposed",
                       "--mechanism", f"fixes {tag}", "--evidence", "screen promoted it",
                       "--touches", "tools/tools.py",
                       *[a for t in tids for a in ("--task", t)]],
                      capture_output=True, text=True, check=True)
    return run_dir, project, adapter


def _run_merge_search(run_dir, project, **extra):
    cmd = [sys.executable, str(SCRIPTS / "merge_search.py"),
          "--run-dir", str(run_dir.root), "--project", str(project),
          "--base", "seed", "--survivors", "A,B,C",
          "--canary-auto", str(run_dir.root / "baseline.json"),
          "--n", "2", "--conc", "1"]
    for k, v in extra.items():
        if isinstance(v, list):
            for item in v:
                cmd += [f"--{k}", item]
        else:
            cmd += [f"--{k}", str(v)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    assert p.returncode == 0, f"merge_search.py failed: {p.stdout}\n{p.stderr}"
    return json.loads(p.stdout)


def test_disjoint_survivors_are_identified_as_a_merge_pair_and_overlapping_ones_are_not(tmp_path):
    run_dir, project, _adapter = _run_dir_with_survivors(tmp_path)
    out = _run_merge_search(run_dir, project)

    assert ["A", "B"] in out["disjoint_pairs"], f"A+B (disjoint edits) not offered: {out}"
    overlapping = {tuple(o["pair"]) for o in out["overlapping_pairs_skipped"]}
    assert ("A", "C") in overlapping, f"A+C (both rewrite fn_a) must be flagged overlapping: {out}"
    assert ("B", "C") not in overlapping and ["B", "C"] in out["disjoint_pairs"], (
        f"B+C touch different functions and should be offered too: {out}")
    # C's own overlap reason must name the actually-shared function.
    a_c = next(o for o in out["overlapping_pairs_skipped"] if tuple(o["pair"]) == ("A", "C"))
    assert a_c["shared"] == ["fn_a"], f"wrong shared-function attribution: {a_c}"


def test_the_merge_is_attempted_via_existing_integrate_py_machinery(tmp_path):
    run_dir, project, _adapter = _run_dir_with_survivors(tmp_path)
    out = _run_merge_search(run_dir, project)

    ab = next(m for m in out["merges"] if m["pair"] == ["A", "B"])
    assert ab["attempted"] and ab["built"], f"A+B merge was not built: {ab}"
    assert ab["result"].get("final_objective") is not None, (
        f"integrate.py's own measurement is missing from the result: {ab}")
    # The written artifact is the union of both branches' fixes — funcmerge.py's per-function
    # merge, not a hand-written stitch.
    merged_src = (run_dir.root / "work" / ab["tag"] / "tools" / "tools.py").read_text()
    assert "MARK_A" in merged_src and "MARK_B" in merged_src, (
        f"merged artifact does not carry both branches' fixes:\n{merged_src}")

    # A merge that overlaps (A, C) must never even be attempted.
    ac = [m for m in out["merges"] if m["pair"] == ["A", "C"]]
    assert not ac, f"an overlapping pair must not appear in merges[] at all: {out['merges']}"

    assert ab["tag"] in out["ready_for_gate"]

    # mechanisms.jsonl records the merge as a first-class finding, same ledger any hand-driven
    # merge would use (per-task-fanout.md), not a side channel only this script can read.
    ledger = [json.loads(ln) for ln in
             (run_dir.root / "mechanisms.jsonl").read_text().splitlines() if ln.strip()]
    merge_rows = [r for r in ledger if r["owner"] == ab["tag"]]
    assert merge_rows, "the merge was not recorded in mechanisms.jsonl"
    assert sorted(merge_rows[0]["tasks"]) == ["t0", "t1", "t2", "t3"]


def test_the_merge_result_goes_through_rounds_normal_gate_cascade(tmp_path):
    """The merged candidate is gated by round.py with NO special-casing: the SAME mandatory
    screen ladder (#420/#442), null control, and paired significance a hand-authored
    candidate goes through — a merge is a candidate, not a shortcut past the cascade."""
    run_dir, project, _adapter = _run_dir_with_survivors(tmp_path)
    out = _run_merge_search(run_dir, project)
    ab = next(m for m in out["merges"] if m["pair"] == ["A", "B"])
    assert ab["built"]

    screen = subprocess.run(
        [sys.executable, str(SCRIPTS / "screen.py"), "--run-dir", str(run_dir.root),
         "--project", str(project), "--candidate", str(run_dir.root / "work" / ab["tag"]),
         "--tag", ab["tag"], "--tier", "1"],
        capture_output=True, text=True)
    assert screen.returncode == 0, f"screen.py failed on the merge candidate: {screen.stdout}\n{screen.stderr}"
    assert json.loads(screen.stdout)["decision"] == "promote", (
        "the merge should screen as a real improvement, not get killed pre-gate: "
        f"{screen.stdout}")

    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
         "--project", str(project), "--candidates", ab["tag"], "--n-trials", "2",
         "--concurrency", "1"],
        capture_output=True, text=True)
    assert p.returncode == 0, f"round.py could not gate the merge candidate: {p.stdout}\n{p.stderr}"
    table = json.loads(p.stdout)

    row = next(c for c in table["candidates"] if c["tag"] == ab["tag"])
    # t0,t1,t2,t3 now pass (both fixes merged); t4,t5 already passed. Full val = 1.0, seed = 0.0.
    assert row["reward"] == 1.0, f"merged candidate did not measure the combined fix: {row}"
    assert row["verdict"] == "accept", f"round.py's ordinary gate did not accept a real gain: {row}"
    assert row["gate_delta"] is not None and row["gate_threshold"] is not None, (
        f"the merge did not get the SAME structured gate numbers any candidate gets: {row}")
