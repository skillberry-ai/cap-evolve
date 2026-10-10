"""merge.py — pairwise-merge ANY two live branch tips (#586), not just same-round
screen-survivors (merge_search.py) or events.jsonl-recorded safe rejects (merge_rejects.py).

The scenario this proves: one branch (`cand_old`) is an ALREADY-COMMITTED candidate from an
earlier iteration (a real rejected snapshot under `$R/candidates/`, committed via
`commit.py`), and the other (`cand_new`) is a fresh, still-uncommitted survivor staged under
`$R/work/` from a LATER round. Neither `merge_search.py` (which only looks at `work/`) nor
`merge_rejects.py` (which only looks at `events.jsonl` reject rows recorded THIS run) can name
this exact pair without extra staging. `merge.py` merges them directly by tag, gates the
result through `round.py`'s ordinary cascade with no special-casing, and — on accept —
`commit.py --parents` records BOTH ancestors in `graph.jsonl`, not a single `parent`.
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


TOOLS_BASE = '''
def fn_a(x):
    return x

def fn_b(x):
    return x
'''

TOOLS_FIX_A = '''
def fn_a(x):
    return x + "MARK_A"

def fn_b(x):
    return x
'''

TOOLS_FIX_B = '''
def fn_a(x):
    return x

def fn_b(x):
    return x + "MARK_B"
'''

# Overlaps FIX_A: rewrites fn_a DIFFERENTLY — a real edit collision.
TOOLS_FIX_A_DIFFERENTLY = '''
def fn_a(x):
    return x + "OTHER_MARK_A"

def fn_b(x):
    return x
'''


def _write_project(tmp_path: Path) -> Path:
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
        return [Task(id=f"t{i}") for i in range(4)]

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


def _load_adapter(project: Path):
    spec = importlib.util.spec_from_file_location(
        "merge_branches_project_adapter", project / "adapters" / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str((project / "adapters").parent))
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod.Adapter()


def _seed_capability(root: Path, name: str, tools_src: str) -> Path:
    d = root / name
    (d / "tools").mkdir(parents=True, exist_ok=True)
    (d / "tools" / "tools.py").write_text(tools_src, encoding="utf-8")
    (d / "policy").mkdir(parents=True, exist_ok=True)
    (d / "policy" / "policy.md").write_text("base policy\n", encoding="utf-8")
    return d


def _run_dir_with_mixed_branches(tmp_path: Path):
    """`cand_old` is committed (a real rejected snapshot under candidates/) from an earlier
    iteration; `cand_new` is a fresh survivor still under work/ from a later round — two live
    branches at different lifecycle stages, on disjoint edits."""
    from cap_evolve import Budget, RunDir, harness

    project = _write_project(tmp_path)
    adapter = _load_adapter(project)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=10))
    seed = _seed_capability(tmp_path, "seed_capability", TOOLS_BASE)
    harness.ensure_splits(adapter, run_dir, seed=0,
                          split_ids={"val": [f"t{i}" for i in range(4)], "train": [], "test": []})
    harness.baseline(adapter, seed, run_dir=run_dir)

    # cand_old: proposed, measured, rejected (sub-threshold) — committed and snapshotted, the
    # same way any real reject leaves a candidates/ directory behind.
    old_src = _seed_capability(tmp_path / "candidates_src", "cand_old", TOOLS_FIX_A)
    run_dir.snapshot("cand_old", old_src)
    run_dir.log_event("reject", candidate="cand_old", note="sub-threshold", reject_basis="gate",
                      gate_delta=0.01, broke=[], fixed=[], n_broke=0, n_fixed=0)
    with (run_dir.root / "mechanisms.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"owner": "cand_old", "status": "proposed", "tasks": ["t0", "t1"]}) + "\n")

    # cand_new: a fresh, still-uncommitted survivor from a LATER round, staged under work/ —
    # never touched events.jsonl or a candidates/ snapshot.
    work = run_dir.root / "work"
    _seed_capability(work, "cand_new", TOOLS_FIX_B)
    with (run_dir.root / "mechanisms.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"owner": "cand_new", "status": "proposed", "tasks": ["t2", "t3"]}) + "\n")

    return run_dir, project


def _run_merge(run_dir, project, a, b, **extra):
    cmd = [sys.executable, str(SCRIPTS / "merge.py"),
          "--run-dir", str(run_dir.root), "--project", str(project),
          "--a", a, "--b", b, "--base", "seed", "--n", "2", "--conc", "1"]
    for k, v in extra.items():
        cmd += [f"--{k}", str(v)]
    p = subprocess.run(cmd, capture_output=True, text=True, env=_env())
    return p


def test_merges_a_committed_branch_with_an_uncommitted_survivor(tmp_path):
    run_dir, project = _run_dir_with_mixed_branches(tmp_path)
    p = _run_merge(run_dir, project, "cand_old", "cand_new")
    assert p.returncode == 0, f"merge.py failed: {p.stdout}\n{p.stderr}"
    out = json.loads(p.stdout)

    assert out["conflicts"] == [], f"cand_old/cand_new should not conflict: {out}"
    assert out["built"], f"merge was not built: {out}"
    assert out["tag"] == "merge_cand_old_cand_new"

    merged_src = (run_dir.root / "work" / out["tag"] / "tools" / "tools.py").read_text()
    assert "MARK_A" in merged_src and "MARK_B" in merged_src, (
        f"merged artifact does not carry both branches' fixes:\n{merged_src}")

    ledger = [json.loads(ln) for ln in
             (run_dir.root / "mechanisms.jsonl").read_text().splitlines() if ln.strip()]
    assert any(r["owner"] == out["tag"] for r in ledger), (
        "the merge was not recorded in mechanisms.jsonl")


def test_refuses_an_overlapping_pair(tmp_path):
    run_dir, project = _run_dir_with_mixed_branches(tmp_path)
    # cand_collide rewrites fn_a differently from cand_old — a real edit collision.
    collide_src = _seed_capability(tmp_path / "candidates_src", "cand_collide",
                                   TOOLS_FIX_A_DIFFERENTLY)
    run_dir.snapshot("cand_collide", collide_src)
    with (run_dir.root / "mechanisms.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"owner": "cand_collide", "status": "proposed", "tasks": ["t0"]}) + "\n")

    p = _run_merge(run_dir, project, "cand_old", "cand_collide")
    assert p.returncode == 2
    out = json.loads(p.stdout)
    assert out["conflicts"] == ["tools/tools.py::fn_a"], f"wrong shared-function attribution: {out}"
    assert out.get("attempted") is False
    assert not (run_dir.root / "work" / "merge_cand_old_cand_collide").exists(), (
        "an overlapping pair must never be built")


def test_merged_candidate_gates_and_commits_with_two_parents(tmp_path):
    """The merge candidate goes through round.py's ordinary cascade, and on accept
    commit.py --parents records BOTH ancestors in graph.jsonl — the #586 data-model gap
    this slice closes for a merge coming from an arbitrary pair, not only from
    merge_search.py's own same-round survivors (already covered by test_graph_jsonl.py)."""
    run_dir, project = _run_dir_with_mixed_branches(tmp_path)
    p = _run_merge(run_dir, project, "cand_old", "cand_new")
    assert p.returncode == 0, f"merge.py failed: {p.stdout}\n{p.stderr}"
    tag = json.loads(p.stdout)["tag"]

    screen = subprocess.run(
        [sys.executable, str(SCRIPTS / "screen.py"), "--run-dir", str(run_dir.root),
         "--project", str(project), "--candidate", str(run_dir.root / "work" / tag),
         "--tag", tag, "--tier", "1"],
        capture_output=True, text=True, env=_env())
    assert screen.returncode == 0, f"screen.py failed: {screen.stdout}\n{screen.stderr}"

    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
         "--project", str(project), "--candidates", tag, "--n-trials", "2", "--concurrency", "1",
         "--single-candidate-justification", "merge.py: gating the merge alone (#586)"],
        capture_output=True, text=True, env=_env())
    assert r.returncode == 0, f"round.py failed: {r.stdout}\n{r.stderr}"
    table = json.loads(r.stdout)
    row = next(c for c in table["candidates"] if c["tag"] == tag)
    assert row["reward"] == 1.0, f"merged candidate did not measure the combined fix: {row}"
    assert row["verdict"] == "accept", f"round.py did not accept a real gain: {row}"

    commit = subprocess.run(
        [sys.executable, str(SCRIPTS / "commit.py"), "--run-dir", str(run_dir.root),
         "--candidate-id", tag, "--from-dir", str(run_dir.root / "work" / tag),
         "--decision", "accept", "--val", str(row["reward"]), "--val-unverified", "fixture: val not under test",
         "--parents", "cand_old,cand_new", "--note", "merge of two live branches (#586)",
         # #588 made the JOURNAL.md handover a hard precondition of commit.py; this fixture
         # is testing the --parents plumbing, not the journal discipline, so the same escape
         # hatch used by test_graph_jsonl.py/test_agent_optimize_provisional.py applies here.
         "--missing-handover-justification", "fixture: journal handover not under test",
         "--missing-ranked-issues-justification", "fixture: ranked issues not under test",
         "--missing-diagnosis-justification", "fixture: diagnosis not under test"],
        capture_output=True, text=True, env=_env())
    assert commit.returncode == 0, f"commit.py failed: {commit.stdout}\n{commit.stderr}"

    from cap_evolve import graph as graph_mod
    nodes = {n["id"]: n for n in graph_mod.read_nodes(run_dir)}
    assert nodes[tag]["parents"] == ["cand_old", "cand_new"], (
        f"graph.jsonl did not record both ancestors: {nodes.get(tag)}")
    assert nodes[tag]["edit_kind"] == "merge"
