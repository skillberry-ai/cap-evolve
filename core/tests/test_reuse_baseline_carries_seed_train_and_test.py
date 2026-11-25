"""`reuse_baseline` must let a later run skip EVERY seed evaluation, not just val.

It used to copy the seed's val score and rollouts only, so a run built on a prior baseline still
paid for the seed on train (finalize's bookend) and on test (``FINAL_seed``) — for spreadsheetbench's
no-skill seed that test eval alone is ~5 h. The seed's train rollouts and its sealed test RESULT now
carry over too; the test result is used only while the seed bytes are unchanged, and never as test
rollouts on disk (that would trip the second-look guard).

Uses the real zero-cost toy_calc adapter, wrapped to count what it actually evaluates.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXAMPLE = REPO / "benchmarks" / "toy" / "examples" / "calc"
sys.path.insert(0, str(REPO / "core"))
sys.path.insert(0, str(EXAMPLE))


class _Counting:
    def __init__(self, inner):
        self._inner = inner
        self.rollouts: list[str] = []

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def run_target(self, task, *a, **k):
        self.rollouts.append(task.id)
        return self._inner.run_target(task, *a, **k)


def _adapter():
    spec = importlib.util.spec_from_file_location("toy_calc_adapter_reuse", EXAMPLE / "adapter.py")
    toy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(toy)
    return _Counting(toy.Adapter())


def _prior_run(tmp_path):
    from cap_evolve import Budget, RunDir, harness

    adapter = _adapter()
    seed = tmp_path / "seed_capability"
    shutil.copytree(EXAMPLE / "capability", seed)
    rd = RunDir.create(tmp_path / ".capevolve", ts="prior", budget=Budget(max_iterations=0))
    harness.ensure_splits(adapter, rd, seed=0)
    harness.baseline(adapter, seed, run_dir=rd)
    harness.finalize(adapter, run_dir=rd, best_dir=rd.candidate_dir("seed"),
                     baseline_dir=rd.candidate_dir("seed"))
    return rd


def test_a_reused_baseline_evaluates_nothing_for_the_seed(tmp_path):
    from cap_evolve import Budget, RunDir, harness

    prior = _prior_run(tmp_path)
    prior_final = json.loads((prior.root / "final.json").read_text(encoding="utf-8"))

    adapter = _adapter()
    rd = RunDir.create(tmp_path / ".capevolve", ts="next", budget=Budget(max_iterations=0))
    harness.reuse_baseline(prior.root, run_dir=rd)
    payload = harness.finalize(adapter, run_dir=rd, best_dir=rd.candidate_dir("seed"),
                               baseline_dir=rd.candidate_dir("seed"))

    assert adapter.rollouts == [], f"seed was re-evaluated on {adapter.rollouts}"
    assert payload["test"]["reward"] == prior_final["test"]["reward"]
    assert payload["seed_test_reused_from"] == str(prior.root)
    assert payload["seed"]["train"].get("reused_rollouts") is True
    assert not list((rd.rollouts / "test").glob("*.json")), "test rollouts must not be copied"


def test_the_prior_runs_candidate_rollouts_are_not_copied(tmp_path):
    """Candidate ids restart at cand_0001 in every run, so a copied prior candidate rollout would
    read as this run's result for a candidate it has not evaluated yet (seen in run 36523096755)."""
    from cap_evolve import Budget, RunDir, harness

    prior = _prior_run(tmp_path)
    seed_val = next((prior.rollouts / "val").glob("*__seed__t0.json"))
    for split in ("val", "train"):
        (prior.rollouts / split / seed_val.name.replace("__seed__", "__cand_0001__")).write_text("{}")

    rd = RunDir.create(tmp_path / ".capevolve", ts="next", budget=Budget(max_iterations=0))
    harness.reuse_baseline(prior.root, run_dir=rd)

    for split in ("val", "train"):
        names = [f.name for f in (rd.rollouts / split).glob("*.json")]
        assert names and all("__seed__" in n for n in names), f"{split}: {names}"


def test_a_changed_seed_is_rescored_on_test(tmp_path):
    from cap_evolve import Budget, RunDir, harness

    prior = _prior_run(tmp_path)
    adapter = _adapter()
    rd = RunDir.create(tmp_path / ".capevolve", ts="next", budget=Budget(max_iterations=0))
    harness.reuse_baseline(prior.root, run_dir=rd)
    (rd.candidate_dir("seed") / "prompt.md").write_text("edited after reuse\n", encoding="utf-8")

    harness.finalize(adapter, run_dir=rd, best_dir=rd.candidate_dir("seed"),
                     baseline_dir=rd.candidate_dir("seed"))

    test_ids = set(rd.read_splits().test)
    assert test_ids <= set(adapter.rollouts), "a stale seed test score was reused for different bytes"


def test_a_better_candidate_is_scored_but_the_seed_is_not(tmp_path):
    from cap_evolve import Budget, RunDir, harness

    prior = _prior_run(tmp_path)
    adapter = _adapter()
    rd = RunDir.create(tmp_path / ".capevolve", ts="next", budget=Budget(max_iterations=1))
    harness.reuse_baseline(prior.root, run_dir=rd)
    rd.snapshot("cand_0001", rd.candidate_dir("seed"))
    (rd.candidate_dir("cand_0001") / "prompt.md").write_text("a different capability\n", encoding="utf-8")
    rd.set_best("cand_0001")

    payload = harness.finalize(adapter, run_dir=rd, best_dir=rd.candidate_dir("cand_0001"),
                               baseline_dir=rd.candidate_dir("seed"))

    splits = rd.read_splits()
    assert sorted(adapter.rollouts).count(splits.test[0]) == 1, "test scored for the seed again"
    assert payload["test_baseline"]["reward"] == json.loads(
        (prior.root / "final.json").read_text(encoding="utf-8"))["test"]["reward"]


def _project_with_scorer(tmp_path):
    project = tmp_path / ".capevolve" / "project"
    (project / "adapters").mkdir(parents=True)
    (project / "adapters" / "adapter.py").write_text("X = 1\n")
    (project / "scorer.py").write_text("def score(*a): return 0.0\n")
    return project


def _events(rd, kind):
    lines = rd.events_path.read_text(encoding="utf-8").splitlines() if rd.events_path.exists() else []
    return [e for e in map(json.loads, lines) if e.get("kind") == kind]


def _act_module():
    d = str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts")
    if d not in sys.path:
        sys.path.insert(0, d)
    import act
    return act


def _ctx(rd, project):
    import types
    return types.SimpleNamespace(run_dir=rd, project=str(project))


def test_reuse_from_another_work_folder_with_identical_files_seals_on_time(tmp_path):
    from cap_evolve import Budget, RunDir, harness, integrity

    work_a, work_b = tmp_path / "a", tmp_path / "b"
    pa = _project_with_scorer(work_a)
    prior = _prior_run(work_a)
    assert _events(prior, "eval_surface_recorded")[0]["late"] is False
    pb = _project_with_scorer(work_b)
    rd = RunDir.create(work_b / ".capevolve", ts="next", budget=Budget(max_iterations=0))
    harness.reuse_baseline(prior.root, run_dir=rd)
    ev = _events(rd, "eval_surface_carried")
    assert ev and ev[-1]["ok"] is True
    rec = _events(rd, "eval_surface_recorded")
    assert rec and rec[-1]["late"] is False
    man = integrity.read_manifest(Path(rd.private_dir) / integrity.EVAL_SURFACE_MANIFEST)
    assert man["root"] == str(pb.resolve())
    _act_module().guard_eval_surface(_ctx(rd, pb), "promote")  # does not raise
    assert pa != pb


def test_reuse_reports_an_edited_scorer_and_does_not_seal(tmp_path, capsys):
    from cap_evolve import Budget, RunDir, harness, integrity

    project = _project_with_scorer(tmp_path)
    prior = _prior_run(tmp_path)
    (project / "scorer.py").write_text("def score(*a): return 1.0\n")  # edited since the earlier run
    rd = RunDir.create(tmp_path / ".capevolve", ts="next", budget=Budget(max_iterations=0))
    harness.reuse_baseline(prior.root, run_dir=rd)
    ev = _events(rd, "eval_surface_carried")
    assert ev and ev[-1]["ok"] is False and "scorer.py" in ev[-1]["reason"]
    assert "TAMPERED" in capsys.readouterr().err
    assert not _events(rd, "eval_surface_recorded")
    assert not (Path(rd.private_dir) / integrity.EVAL_SURFACE_MANIFEST).exists()


def test_reuse_of_a_late_earlier_seal_records_no_baseline_seal(tmp_path, capsys):
    from cap_evolve import Budget, RunDir, harness, integrity

    project = _project_with_scorer(tmp_path)
    prior = _prior_run(tmp_path)
    # make the earlier seal a late one, as any run from before the baseline seal existed has
    ev_path = Path(prior.events_path)
    lines = [json.loads(x) for x in ev_path.read_text(encoding="utf-8").splitlines()]
    for e in lines:
        if e.get("kind") == "eval_surface_recorded":
            e["late"] = True
            e.pop("at", None)
    ev_path.write_text("".join(json.dumps(e) + "\n" for e in lines), encoding="utf-8")
    rd = RunDir.create(tmp_path / ".capevolve", ts="next", budget=Budget(max_iterations=0))
    harness.reuse_baseline(prior.root, run_dir=rd)
    assert not (Path(rd.private_dir) / integrity.EVAL_SURFACE_MANIFEST).exists()
    assert not _events(rd, "eval_surface_recorded") and not _events(rd, "eval_surface_carried")
    capsys.readouterr()
    _act_module().record_eval_surface(_ctx(rd, project))
    rec = _events(rd, "eval_surface_recorded")
    assert rec and rec[-1]["late"] is True
    assert "sealed only now" in capsys.readouterr().err


def test_reuse_without_an_earlier_seal_records_no_baseline_seal(tmp_path):
    from cap_evolve import Budget, RunDir, harness, integrity

    prior = _prior_run(tmp_path)
    (Path(prior.private_dir) / integrity.EVAL_SURFACE_MANIFEST).unlink(missing_ok=True)
    _project_with_scorer(tmp_path)
    rd = RunDir.create(tmp_path / ".capevolve", ts="next", budget=Budget(max_iterations=0))
    harness.reuse_baseline(prior.root, run_dir=rd)
    assert not (Path(rd.private_dir) / integrity.EVAL_SURFACE_MANIFEST).exists()
    assert not _events(rd, "eval_surface_recorded")
