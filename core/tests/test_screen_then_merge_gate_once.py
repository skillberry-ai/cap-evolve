"""End-to-end proof of the flow SKILL.md's step 2 now mandates for Bucket-A siblings:
screen every sibling first (cheap, kill-only), merge the disjoint SCREEN-SURVIVORS via
``merge_search.py``, and pay full val exactly ONCE on the merged candidate — never once
per sibling.

Two disjoint sibling edits (cand_1 fixes fn_a, cand_2 fixes fn_b) are:
  1. screened independently via ``screen.py`` (each must survive: "promote", never "kill");
  2. merged via ``merge_search.py`` into one candidate directory;
  3. gated via ``round.py`` — passing ONLY the merged tag, not the two originals.

The assertion that matters: the full-val evaluate phase runs exactly once (one tag's
rollouts land on disk under val), not twice, and ``round.py``'s table has exactly one row.
This is a real subprocess run against a real (tiny, zero-API) adapter — no simulation.
"""

from __future__ import annotations

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


def _write_project(tmp_path: Path) -> Path:
    """t0/t1 need MARK_A, t2/t3 need MARK_B, t4/t5 pass unconditionally (stable canaries)."""
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


def _load(name: str, path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _setup(tmp_path: Path):
    from cap_evolve import Budget, RunDir, harness

    project = _write_project(tmp_path)
    adapter = _load("proj_adapter", project / "adapters" / "adapter.py").Adapter()

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=10))
    seed = _seed_capability(tmp_path, "seed_capability", TOOLS_BASE)
    harness.ensure_splits(adapter, run_dir, seed=0,
                          split_ids={"val": [f"t{i}" for i in range(6)], "train": [], "test": []})
    harness.baseline(adapter, seed, run_dir=run_dir)

    work = run_dir.root / "work"
    _seed_capability(work, "cand_1", TOOLS_FIX_A)
    _seed_capability(work, "cand_2", TOOLS_FIX_B)
    return run_dir, project


def _run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, env=_env(), **kw)
    assert p.returncode == 0, f"{cmd}\nstdout={p.stdout}\nstderr={p.stderr}"
    return json.loads(p.stdout)


def _val_rollout_tags(run_dir) -> set[str]:
    """Distinct <tag> prefixes with full-val (non-screen) rollout files on disk."""
    tags = set()
    for f in (run_dir.root / "rollouts" / "val").glob("*.json"):
        parts = f.name.split("__")
        # <task>__<tag>__t<k>.json ; skip anything with a __screen* segment (subset evals)
        if len(parts) >= 3 and not any(p.startswith("screen") for p in parts[1:-1]):
            tags.add("__".join(parts[1:-1]))
    return tags


def test_two_disjoint_siblings_screen_survive_merge_and_gate_exactly_once(tmp_path):
    run_dir, project = _setup(tmp_path)

    # 1. Screen each sibling independently — cheap, kill-only, per SKILL.md step 3.
    for tag in ("cand_1", "cand_2"):
        out = _run([sys.executable, str(SCRIPTS / "screen.py"),
                    "--run-dir", str(run_dir.root), "--project", str(project),
                    "--candidate", str(run_dir.root / "work" / tag), "--tag", tag,
                    "--tier", "1", "--n-trials", "1"])
        assert out["decision"] == "promote", f"{tag} should survive screening: {out}"

    # No full-val rollouts should exist yet — only the seed's baseline eval has run.
    pre_tags = _val_rollout_tags(run_dir) - {"seed"}
    assert pre_tags == set(), f"screening must not itself pay for a full-val eval: {pre_tags}"

    # 2. Merge the two disjoint screen-survivors into ONE candidate — the required step
    #    before gating, per SKILL.md step 2 / algorithm.md's screen-then-merge section.
    for tag, tids in (("cand_1", ["t0", "t1"]), ("cand_2", ["t2", "t3"])):
        _run([sys.executable, str(SCRIPTS / "mechanisms.py"), "add",
              "--run-dir", str(run_dir.root), "--owner", tag, "--status", "proposed",
              "--mechanism", f"fixes {tag}", "--evidence", "screen promoted it",
              "--touches", "tools/tools.py", *[a for t in tids for a in ("--task", t)]])

    merge_out = _run([sys.executable, str(SCRIPTS / "merge_search.py"),
                       "--run-dir", str(run_dir.root), "--project", str(project),
                       "--base", "seed", "--survivors", "cand_1,cand_2",
                       "--canary-auto", str(run_dir.root / "baseline.json"),
                       "--n", "1", "--conc", "1"])
    assert merge_out["disjoint_pairs"] == [["cand_1", "cand_2"]], merge_out
    merged = next(m for m in merge_out["merges"] if m["pair"] == ["cand_1", "cand_2"])
    assert merged["built"], f"the merge was not built: {merged}"
    merged_tag = merged["tag"]

    # The merged candidate itself still owes round.py a screen record (its own mandatory
    # ladder, unrelated to whether its parts were screened) — one more cheap screen, still
    # far short of a second full-val eval.
    merge_screen = _run([sys.executable, str(SCRIPTS / "screen.py"),
                         "--run-dir", str(run_dir.root), "--project", str(project),
                         "--candidate", str(run_dir.root / "work" / merged_tag),
                         "--tag", merged_tag, "--tier", "1", "--n-trials", "1"])
    assert merge_screen["decision"] == "promote", merge_screen

    # 3. Gate ONLY the merged candidate on full val — never the two originals separately.
    table = _run([sys.executable, str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
                   "--project", str(project), "--candidates", merged_tag,
                   "--n-trials", "2", "--concurrency", "1"])

    assert len(table["candidates"]) == 1, (
        f"round.py must gate exactly one candidate dir, not one per sibling: {table}")
    row = table["candidates"][0]
    assert row["tag"] == merged_tag
    assert row["reward"] == 1.0, f"merged candidate should fix both siblings' tasks: {row}"
    assert row["verdict"] == "accept", f"a real combined gain must accept: {row}"

    # The full-val rollouts on disk carry exactly ONE non-seed, non-control tag family —
    # proof this flow paid for full val once, not twice.
    post_tags = _val_rollout_tags(run_dir) - {"seed"}
    non_control = {t for t in post_tags if not t.startswith("ctl_")}
    assert non_control == {merged_tag}, (
        f"full val must be paid for exactly once, on the merged candidate only: {non_control}")
