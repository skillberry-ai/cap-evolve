"""merge_search.is_mergeable / build_merge — GEPA's Appendix D mergeable-ness check
(arXiv:2507.19457, Algorithms 3-4), adapted to this project's capability tree (#684 item 4).

Confirmed gap this closes: across a real run's 4 rounds, `merge_eligible_pairs` was empty
every time — intra-round merging of compatible siblings was never even EVALUATED, because
`round.py`'s old `mergeable_pairs` skipped any pair sharing a diagnose cluster WITHOUT ever
looking at which files/functions they actually touched. `is_mergeable` replaces that
cluster-label heuristic with GEPA's real per-module divergence check: two candidates are
mergeable at a common ancestor iff, for every module (file; per-function/constant block for
`.py` files — the SAME split `funcmerge.py`/`integrate.py` already merge on), at most one of
them diverged from the ancestor.
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

import merge_search  # noqa: E402


def _env() -> dict:
    return dict(os.environ, CAPEVOLVE_CORE=str(REPO / "core"),
                CAPEVOLVE_SKILLS_DIR=str(REPO / "skills"))


def _cap(root: Path, name: str, tools_src: str, policy_src: str = "base policy\n") -> Path:
    d = root / name
    (d / "tools").mkdir(parents=True, exist_ok=True)
    (d / "tools" / "tools.py").write_text(tools_src, encoding="utf-8")
    (d / "policy").mkdir(parents=True, exist_ok=True)
    (d / "policy" / "policy.md").write_text(policy_src, encoding="utf-8")
    return d


BASE_TOOLS = "def fn_a(x):\n    return x\n\n\ndef fn_b(x):\n    return x\n"
FIX_A = BASE_TOOLS.replace("def fn_a(x):\n    return x",
                           'def fn_a(x):\n    return x + "MARK_A"')
FIX_B = BASE_TOOLS.replace("def fn_b(x):\n    return x",
                           'def fn_b(x):\n    return x + "MARK_B"')
FIX_A_OTHER = BASE_TOOLS.replace("def fn_a(x):\n    return x",
                                 'def fn_a(x):\n    return x + "OTHER_MARK_A"')


# --------------------------------------------------------------------------------------------
# is_mergeable
# --------------------------------------------------------------------------------------------

def test_disjoint_module_edits_are_mergeable(tmp_path):
    """Two candidates each diverging on a DIFFERENT module (fn_a vs fn_b) are mergeable."""
    ancestor = _cap(tmp_path, "ancestor", BASE_TOOLS)
    a = _cap(tmp_path, "a", FIX_A)
    b = _cap(tmp_path, "b", FIX_B)
    out = merge_search.is_mergeable(a, b, ancestor)
    assert out["mergeable"] is True
    assert out["conflicts"] == []


def test_both_diverged_same_module_differently_is_not_mergeable(tmp_path):
    """Both candidates rewrite fn_a, but to DIFFERENT content — a real collision."""
    ancestor = _cap(tmp_path, "ancestor", BASE_TOOLS)
    a = _cap(tmp_path, "a", FIX_A)
    b = _cap(tmp_path, "b", FIX_A_OTHER)
    out = merge_search.is_mergeable(a, b, ancestor)
    assert out["mergeable"] is False
    assert out["conflicts"] == ["tools/tools.py::fn_a"]
    assert out["identical_overlaps"] == []


def test_both_diverged_same_module_identically_is_mergeable_edge_case(tmp_path):
    """Both candidates make the EXACT SAME edit to fn_a — documented edge case: this is
    reported mergeable (not a real disagreement), listed under identical_overlaps rather than
    conflicts, even though GEPA's own Desirable() check (Algorithm 4) does not distinguish
    this from a true collision."""
    ancestor = _cap(tmp_path, "ancestor", BASE_TOOLS)
    a = _cap(tmp_path, "a", FIX_A)
    b = _cap(tmp_path, "b", FIX_A)
    out = merge_search.is_mergeable(a, b, ancestor)
    assert out["mergeable"] is True
    assert out["conflicts"] == []
    # Both candidates' tools.py are byte-IDENTICAL, so the file-level check (cheaper than the
    # per-function split) already resolves this at file granularity, never descending into
    # funcmerge.blocks at all — see test_only_one_diverger_... below for the function-level case.
    assert out["identical_overlaps"] == ["tools/tools.py"]


def test_whole_file_module_both_diverged_differently_on_prose(tmp_path):
    """Non-.py files are a single whole-file module (no sub-file granularity exists for
    prose) — both candidates editing policy.md differently is a conflict."""
    ancestor = _cap(tmp_path, "ancestor", BASE_TOOLS, "base policy\n")
    a = _cap(tmp_path, "a", BASE_TOOLS, "base policy\nadded by A\n")
    b = _cap(tmp_path, "b", BASE_TOOLS, "base policy\nadded by B\n")
    out = merge_search.is_mergeable(a, b, ancestor, md_blocks=False)
    assert out["mergeable"] is False
    assert out["conflicts"] == ["policy/policy.md"]
    # #709: with heading-block splitting (default) the same-block edit is still a conflict.
    out = merge_search.is_mergeable(a, b, ancestor)
    assert out["mergeable"] is False
    assert out["conflicts"] == ["policy/policy.md::"]


def test_only_one_diverger_is_mergeable_even_on_a_module_the_other_also_touches_elsewhere(
        tmp_path):
    """A diverges on fn_a only, B diverges on fn_b only — no module has two divergers."""
    ancestor = _cap(tmp_path, "ancestor", BASE_TOOLS)
    both_fix = BASE_TOOLS.replace("def fn_a(x):\n    return x",
                                  'def fn_a(x):\n    return x + "MARK_A"').replace(
        "def fn_b(x):\n    return x", 'def fn_b(x):\n    return x + "MARK_B"')
    a = _cap(tmp_path, "a", FIX_A)
    b = _cap(tmp_path, "b", both_fix)  # diverges on BOTH fn_a (same as A) and fn_b
    out = merge_search.is_mergeable(a, b, ancestor)
    # fn_a: both diverged, IDENTICALLY (A's fn_a == B's fn_a) -> identical_overlaps, not a
    # conflict. fn_b: only B diverged -> fine. So the pair is mergeable overall.
    assert out["mergeable"] is True
    assert out["identical_overlaps"] == ["tools/tools.py::fn_a"]


# --------------------------------------------------------------------------------------------
# build_merge construction
# --------------------------------------------------------------------------------------------

def test_build_merge_output_matches_per_module_resolution(tmp_path):
    """Single-diverger-per-module wins; a module neither touched keeps the ancestor's bytes
    unchanged."""
    ancestor = _cap(tmp_path, "ancestor", BASE_TOOLS, "base policy\n")
    a = _cap(tmp_path, "a", FIX_A, "base policy\n")   # only diverges on tools.py (fn_a)
    b = _cap(tmp_path, "b", FIX_B, "base policy\n")   # only diverges on tools.py (fn_b)
    check = merge_search.is_mergeable(a, b, ancestor)
    assert check["mergeable"] is True

    out_dir = tmp_path / "merged"
    result = merge_search.build_merge(a, b, ancestor, out_dir)
    assert result["built"] is True, result

    merged_tools = (out_dir / "tools" / "tools.py").read_text(encoding="utf-8")
    assert "MARK_A" in merged_tools and "MARK_B" in merged_tools
    merged_policy = (out_dir / "policy" / "policy.md").read_text(encoding="utf-8")
    assert merged_policy == "base policy\n"  # neither touched it: ancestor's bytes, unchanged


def test_build_merge_identical_both_diverged_edge_case(tmp_path):
    """Both candidates made the identical edit; build_merge resolves to that (either) content,
    not a conflict."""
    ancestor = _cap(tmp_path, "ancestor", BASE_TOOLS)
    a = _cap(tmp_path, "a", FIX_A)
    b = _cap(tmp_path, "b", FIX_A)
    assert merge_search.is_mergeable(a, b, ancestor)["mergeable"] is True

    out_dir = tmp_path / "merged"
    result = merge_search.build_merge(a, b, ancestor, out_dir)
    assert result["built"] is True, result
    assert "MARK_A" in (out_dir / "tools" / "tools.py").read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------------
# round.py integration — synthetic 2-sibling rounds
# --------------------------------------------------------------------------------------------

ADAPTER = '''
from pathlib import Path
from cap_evolve.adapter import CapabilityAdapter
from cap_evolve.trials import run_trials_pool
from cap_evolve.types import Task, Rollout, Score

NEEDS = {"t0": "MARK_A", "t1": "MARK_B"}

class Adapter(CapabilityAdapter):
    def tasks(self, split):
        return [Task(id=f"t{i}") for i in range(2)]

    def run_target(self, task, ctx, *, seed=0):
        return Rollout(task_id=task.id,
                       output=(Path(ctx) / "tools" / "tools.py").read_text(encoding="utf-8"))

    def run_trials(self, tasks, ctx, *, n_trials, base_seed):
        return run_trials_pool(lambda t, s: self.run_target(t, ctx, seed=s), tasks,
                               n_trials=n_trials, base_seed=base_seed)

    def score(self, task, rollout):
        src = rollout.output or ""
        need = NEEDS.get(task.id)
        ok = need is None or need in src
        r = 1.0 if ok else 0.0
        return Score(task_id=task.id, reward=r, feedback="ok" if ok else f"needs {need}",
                     trial_rewards=[r])
'''


def _round_setup(tmp_path: Path, sibling_a_src: str, sibling_b_src: str):
    import importlib.util

    from cap_evolve import Budget, RunDir, harness

    project = tmp_path / "project"
    (project / "adapters").mkdir(parents=True)
    (project / "adapters" / "adapter.py").write_text(ADAPTER, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("mergeable_check_adapter",
                                                   project / "adapters" / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=10))
    harness.ensure_splits(mod.Adapter(), run_dir, seed=0,
                          split_ids={"val": ["t0", "t1"], "train": [], "test": []})
    harness.baseline(mod.Adapter(), _cap(tmp_path, "seed_cap", BASE_TOOLS), run_dir=run_dir)

    work = run_dir.root / "work"
    for tag, src, cl, tasks in (("cand_a", sibling_a_src, "SAME", ["t0"]),
                                ("cand_b", sibling_b_src, "SAME", ["t1"])):
        d = _cap(work, tag, src)
        # Both siblings share one diagnose cluster on purpose: the old cluster-overlap
        # heuristic would have skipped this pair unconditionally. #684 item 4 requires the
        # structural is_mergeable check to decide instead.
        (d / "DIAGNOSIS.json").write_text(json.dumps(
            {"candidate": tag, "clusters": [{"id": cl, "tasks": tasks}],
             "edits": [{"id": f"E_{tag}", "clusters": [cl]}]}), encoding="utf-8")
    return run_dir, project


def _run_round(run_dir, project, cands):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
         "--project", str(project), "--candidates", cands, "--n-trials", "1",
         "--concurrency", "1", "--single-candidate-justification",
         "mergeable-check test: only 2 siblings needed to exercise is_mergeable"],
        capture_output=True, text=True, env=_env())


def test_disjoint_file_siblings_same_cluster_build_a_merge_candidate(tmp_path):
    """Two siblings sharing a diagnose cluster but editing DISJOINT functions: a merge
    candidate must be built and included in gating — the exact "never even evaluated" gap
    #684 item 4 closes."""
    run_dir, project = _round_setup(tmp_path, FIX_A, FIX_B)
    p = _run_round(run_dir, project, "cand_a,cand_b")
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)
    merges = (out.get("merge_stage") or {}).get("merges") or []
    assert any(m["parents"] == ["cand_a", "cand_b"] for m in merges), (
        f"no merge was built for a disjoint-file sibling pair: {out}")
    assert out["merge_stage"]["chosen"] == ["merge_cand_a_cand_b"]
    assert sorted(r["tag"] for r in out["candidates"]) == ["merge_cand_a_cand_b"], (
        "parents must not ALSO be gated separately once their merge carries them")


def test_same_file_conflicting_siblings_are_gated_independently(tmp_path):
    """Two siblings that both rewrite fn_a, differently: no merge is attempted (is_mergeable
    is False), and both are gated independently, as before #684."""
    run_dir, project = _round_setup(tmp_path, FIX_A, FIX_A_OTHER)
    p = _run_round(run_dir, project, "cand_a,cand_b")
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)
    merges = (out.get("merge_stage") or {}).get("merges") or []
    assert merges == [], f"a same-module collision must never build a merge: {out}"
    assert sorted(r["tag"] for r in out["candidates"]) == ["cand_a", "cand_b"]
