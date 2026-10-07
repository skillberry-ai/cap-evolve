"""round.py's concurrency-budget design (issue #676).

Forensic finding: SKILL.md's own worked example passed ``--max-parallel 2``, serializing
every round regardless of how many candidates it actually had, and a human running 4
full-val evals BY HAND at once (independent processes, each opening its own
``--concurrency`` connections) hit real gateway contention/timeouts. The fix has two
halves, both covered here:

  1. ``--max-parallel`` now defaults to THIS round's own candidate count (never a fixed
     low number) instead of forcing small rounds to serialize.
  2. ``--concurrency`` is shared across whatever actually runs at once via a TOTAL
     concurrency budget, so running more candidates in parallel scales each one's own
     concurrency DOWN rather than opening N independent copies of it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import round as round_mod  # noqa: E402  (sys.path must be seeded first)


def test_effective_concurrency_divides_the_shared_budget_across_max_parallel():
    # 3 candidates truly running at once, budget 24 -> each gets the full 8 it asked for.
    assert round_mod.effective_concurrency(8, 3, 24) == 8
    # 6 candidates truly running at once, same budget -> scaled down to 4 each, not 8 each.
    assert round_mod.effective_concurrency(8, 6, 24) == 4
    # Never raised above what was asked, even with budget to spare.
    assert round_mod.effective_concurrency(8, 1, 24) == 8
    # Never below 1.
    assert round_mod.effective_concurrency(8, 100, 24) == 1


def test_effective_concurrency_passes_through_falsy_concurrency():
    # concurrency=None/0 means "no cap requested" -- never turned into a budgeted number.
    assert round_mod.effective_concurrency(None, 3, 24) is None
    assert round_mod.effective_concurrency(0, 3, 24) == 0


def test_max_parallel_default_is_none_not_a_fixed_low_number():
    """The old hardcoded default (4, and SKILL.md's own worked example of 2) is exactly
    the anti-pattern #676 names: a round with 2-3 real candidates was serialized for no
    reason tied to the round's own size. The CLI default must now be unset so round.py can
    derive it from THIS round's candidate count."""
    args = round_mod.build_parser().parse_args([
        "--run-dir", "r", "--project", "p", "--candidates", "cand_1,cand_2,cand_3",
        "--n-trials", "1"])
    assert args.max_parallel is None
    assert args.max_total_concurrency == round_mod.DEFAULT_TOTAL_CONCURRENCY_BUDGET


def _env():
    return dict(os.environ, CAPEVOLVE_CORE=str(REPO / "core"),
                CAPEVOLVE_SKILLS_DIR=str(REPO / "skills"))


def _cap(root: Path, name: str, tools: str) -> Path:
    d = root / name
    (d / "tools").mkdir(parents=True, exist_ok=True)
    (d / "tools" / "tools.py").write_text(tools, encoding="utf-8")
    (d / "policy").mkdir(parents=True, exist_ok=True)
    (d / "policy" / "policy.md").write_text("base policy\n", encoding="utf-8")
    return d


ADAPTER = '''
from pathlib import Path
from cap_evolve.adapter import CapabilityAdapter
from cap_evolve.trials import run_trials_pool
from cap_evolve.types import Task, Rollout, Score

class Adapter(CapabilityAdapter):
    def tasks(self, split):
        return [Task(id=f"t{i}") for i in range(4)]

    def run_target(self, task, ctx, *, seed=0):
        return Rollout(task_id=task.id,
                       output=(Path(ctx) / "tools" / "tools.py").read_text(encoding="utf-8"))

    def run_trials(self, tasks, ctx, *, n_trials, base_seed):
        return run_trials_pool(lambda t, s: self.run_target(t, ctx, seed=s), tasks,
                               n_trials=n_trials, base_seed=base_seed)

    def score(self, task, rollout):
        r = 1.0
        return Score(task_id=task.id, reward=r, feedback="ok", trial_rewards=[r])
'''

BASE = "def fn_a(x):\n    return x\n"


def test_round_defaults_max_parallel_to_candidate_count_end_to_end(tmp_path):
    """3 real candidates, no --max-parallel passed: the table must record max_parallel 3
    (not a fixed low default), and measurement_concurrency must stay within the shared
    budget rather than being 3 independent copies of a high --concurrency."""
    import importlib.util

    from cap_evolve import Budget, RunDir, harness

    project = tmp_path / "project"
    (project / "adapters").mkdir(parents=True)
    (project / "adapters" / "adapter.py").write_text(ADAPTER, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("budget_adapter",
                                                   project / "adapters" / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=10))
    harness.ensure_splits(mod.Adapter(), run_dir, seed=0,
                          split_ids={"val": [f"t{i}" for i in range(4)], "train": [], "test": []})
    harness.baseline(mod.Adapter(), _cap(tmp_path, "seed_cap", BASE), run_dir=run_dir)
    (run_dir.candidate_dir("seed") / "DIAGNOSIS.json").write_text(
        json.dumps({"clusters": [], "edits": []}), encoding="utf-8")
    work = run_dir.root / "work"
    for tag in ("cand_1", "cand_2", "cand_3"):
        d = _cap(work, tag, BASE)
        (d / "DIAGNOSIS.json").write_text(
            json.dumps({"candidate": tag, "clusters": [], "edits": []}), encoding="utf-8")

    p = subprocess.run([sys.executable, str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
                        "--project", str(project), "--candidates", "cand_1,cand_2,cand_3",
                        "--n-trials", "1", "--concurrency", "20", "--no-merge",
                        "--single-candidate-justification", "concurrency-budget test"],
                       capture_output=True, text=True, env=_env())
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)

    # Never throttled down to a fixed small number just because the old default was one.
    assert out["measurement_max_parallel"] == 3
    # The round asked for --concurrency 20, but 3 candidates sharing the default 24 budget
    # must each be capped well below that -- never 3 independent copies of 20 (60 total).
    assert out["requested_concurrency"] == 20
    assert out["measurement_concurrency"] == round_mod.effective_concurrency(
        20, 3, round_mod.DEFAULT_TOTAL_CONCURRENCY_BUDGET)
    assert out["measurement_concurrency"] < 20
    assert out["max_total_concurrency"] == round_mod.DEFAULT_TOTAL_CONCURRENCY_BUDGET
