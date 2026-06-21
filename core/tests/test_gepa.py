"""GEPA loop tests — offline, deterministic, zero API.

Exercises ``cap_evolve.gepa.gepa_loop`` over the toy_calc adapter with the real
mock optimizer skill (subprocess) and with inline mock optimizers, asserting the
GEPA-specific contract: the cheap minibatch local gate filters before any full-val
spend, the metric-call budget caps the run, the per-instance frontier is used,
acceptance is honest (val-only), the test seal is never burned, and the
system-aware merge recombines complementary lineages.
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "toy_calc"
MOCK_RUN = REPO / "skills" / "optimizers" / "run-optimizer" / "scripts" / "run.py"

sys.path.insert(0, str(CORE))
sys.path.insert(0, str(EXAMPLE))


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    os.environ["CAPEVOLVE_MOCK_SCRIPT"] = str(EXAMPLE / "mock_script.json")
    yield
    os.environ.clear()
    os.environ.update(old)


def _toy_adapter():
    import importlib.util
    spec = importlib.util.spec_from_file_location("toy_calc_adapter", EXAMPLE / "adapter.py")
    toy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(toy)
    return toy.Adapter()


def _setup(tmp_path, ts, **budget):
    from cap_evolve import Budget, RunDir, harness
    adapter = _toy_adapter()
    seed = tmp_path / f"seed_{ts}"
    shutil.copytree(EXAMPLE / "capability", seed)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts=ts, budget=Budget(**budget))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)
    return adapter, run_dir, base


# ---- synthetic adapters for the focused unit tests ------------------------

def _echo_adapter():
    """Two independent markers ([A], [B]) gate two disjoint task groups, so two
    lineages can each fix one group and a merge can recombine both."""
    from cap_evolve import CapabilityAdapter, Rollout, Score, Task

    class _A(CapabilityAdapter):
        def tasks(self, split):  # noqa: ARG002
            return [Task(id=f"a{i}", input=("A" if i % 2 == 0 else "B"), target="ok")
                    for i in range(12)]

        def run_target(self, task, ctx, *, seed=0):  # noqa: ARG002
            txt = ""
            for f in sorted(Path(ctx).glob("*.txt")):
                txt += f.read_text(encoding="utf-8")
            need = f"[{task.input}]"
            return Rollout(task_id=task.id, output=("ok" if need in txt else "no"),
                           trace=f"need={need}")

        def score(self, task, rollout):
            ok = (rollout.output or "") == "ok"
            return Score(task_id=task.id, reward=1.0 if ok else 0.0,
                         feedback=("correct" if ok else f"missing marker for {task.input}"),
                         trial_rewards=[1.0 if ok else 0.0])

        def materialize(self, candidate_dir, edits=None):  # noqa: ARG002
            return None

    return _A()


def test_gepa_loop_accepts_and_seals_test(tmp_path):
    from cap_evolve import gepa
    adapter, run_dir, base = _setup(tmp_path, "g1", max_iterations=8, max_metric_calls=500)
    optimizer = __import__("cap_evolve").harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}", "--prompt", "{prompt}"])
    res = gepa.gepa_loop(adapter, run_dir=run_dir, optimizer=optimizer, seed_val=base,
                         max_metric_calls=400, max_iterations=6, minibatch_size=3,
                         max_merges=0, seed=0,
                         gate_kwargs={"mode": "significant", "k_se": 1.0})
    assert res["algorithm"] == "gepa"
    assert res["accepts"] >= 1
    assert res["best_val"] == 1.0
    assert res["metric_calls"] > 0
    # test never consumed by optimization
    assert run_dir.read_splits().test_used is False
    # result dict shape mirrors the other loops + gepa extras
    for k in ("best_id", "frontier_size", "pool_size", "iterations", "stop_reason", "steps"):
        assert k in res


def test_local_gate_short_circuits_noop(tmp_path):
    """A no-op optimizer must be rejected by the local minibatch gate WITHOUT a
    full-val eval (no ``candidate_val`` on those steps)."""
    from cap_evolve import gepa
    adapter, run_dir, base = _setup(tmp_path, "g2", max_iterations=4, max_metric_calls=500)

    def noop(workdir, instructions):  # noqa: ARG001
        return None

    res = gepa.gepa_loop(adapter, run_dir=run_dir, optimizer=noop, seed_val=base,
                         max_metric_calls=400, max_iterations=4, minibatch_size=3,
                         max_merges=0, seed=0,
                         gate_kwargs={"mode": "significant", "k_se": 1.0})
    assert res["accepts"] == 0
    local_rejects = [s for s in res["steps"] if s.get("local_gate") is False]
    assert local_rejects, "expected the local gate to reject no-op edits"
    assert all("candidate_val" not in s for s in local_rejects), \
        "local-gated steps must not have paid for a full-val eval"


def test_metric_call_budget_caps_run(tmp_path):
    """A tight metric-call budget stops the loop well before max_iterations.

    Uses an optimizer that mutates the capability EVERY step (each child is a new
    content hash), so the eval cache cannot serve the rollouts and metric-calls
    accrue — otherwise a no-op/identical candidate is correctly cache-served at ~0
    cost and the metric budget would never bind (that path is covered by
    ``test_local_gate_short_circuits_noop``)."""
    from cap_evolve import gepa
    adapter, run_dir, base = _setup(tmp_path, "g3", max_iterations=100, max_metric_calls=1000)

    counter = {"n": 0}

    def mutate(workdir, instructions):  # noqa: ARG001
        # A distinct edit each call → distinct candidate hash → real rollouts.
        counter["n"] += 1
        (Path(workdir) / "scratch_edit.txt").write_text(str(counter["n"]), encoding="utf-8")

    res = gepa.gepa_loop(adapter, run_dir=run_dir, optimizer=mutate, seed_val=base,
                         max_metric_calls=12, max_iterations=100, minibatch_size=3,
                         max_merges=0, seed=0)
    assert "max_metric_calls" in res["stop_reason"]
    assert run_dir.spent.metric_calls >= 12
    assert res["iterations"] < 100


def test_per_instance_frontier_used(tmp_path):
    """The loop should retain >1 pool member (specialists) on the echo adapter when
    fixes are partial, exercising the per-instance frontier."""
    from cap_evolve import gepa
    from cap_evolve import Budget, RunDir, harness
    adapter = _echo_adapter()
    seed = tmp_path / "seed_pi"
    seed.mkdir()
    (seed / "cap.txt").write_text("base\n", encoding="utf-8")
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="pi",
                            budget=Budget(max_iterations=20, max_metric_calls=2000))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)

    calls = {"n": 0}

    def opt(workdir, instructions):  # noqa: ARG001
        # Alternate fixing [A] then [B] so two complementary lineages appear.
        calls["n"] += 1
        f = workdir / "cap.txt"
        txt = f.read_text(encoding="utf-8")
        marker = "[A]" if calls["n"] % 2 == 1 else "[B]"
        if marker not in txt:
            f.write_text(txt + marker + "\n", encoding="utf-8")

    res = gepa.gepa_loop(adapter, run_dir=run_dir, optimizer=opt, seed_val=base,
                         max_metric_calls=1500, max_iterations=12, minibatch_size=4,
                         max_merges=2, merge_cadence=1, seed=1,
                         gate_kwargs={"mode": "significant", "k_se": 1.0})
    assert res["accepts"] >= 1
    assert res["pool_size"] >= 2  # seed + at least one accepted child
    assert run_dir.read_splits().test_used is False


def _two_file_echo_adapter(n=24):
    """Two SEPARATE component files gate two disjoint task groups: even tasks need
    ``[A]`` in compA.txt, odd tasks need ``[B]`` in compB.txt. Distinct files (not
    one monolith) so a component-wise merge has something independent to recombine."""
    from cap_evolve import CapabilityAdapter, Rollout, Score, Task

    class _A(CapabilityAdapter):
        def tasks(self, split):  # noqa: ARG002
            return [Task(id=f"a{i}", input=("A" if i % 2 == 0 else "B"), target="ok")
                    for i in range(n)]

        def run_target(self, task, ctx, *, seed=0):  # noqa: ARG002
            a = (Path(ctx) / "compA.txt").read_text(encoding="utf-8") if (Path(ctx) / "compA.txt").exists() else ""
            b = (Path(ctx) / "compB.txt").read_text(encoding="utf-8") if (Path(ctx) / "compB.txt").exists() else ""
            ok = ("[A]" in a) if task.input == "A" else ("[B]" in b)
            return Rollout(task_id=task.id, output=("ok" if ok else "no"))

        def score(self, task, rollout):
            ok = (rollout.output or "") == "ok"
            return Score(task_id=task.id, reward=1.0 if ok else 0.0,
                         feedback=("correct" if ok else f"missing marker for {task.input}"),
                         trial_rewards=[1.0 if ok else 0.0])

        def materialize(self, candidate_dir, edits=None):  # noqa: ARG002
            return None

    return _A()


def test_merge_recombines_complementary_lineages(tmp_path):
    """The system-aware merge must actually FIRE: two complementary frontier
    descendants of a shared ancestor (each fixed a different component file) are
    recombined into a candidate that beats both. Regression test for the ancestor
    val-lookup that previously searched only the frontier (where the shared ancestor
    never lives) so the merge could never find a pair."""
    from cap_evolve import gepa, Budget, RunDir, harness
    adapter = _two_file_echo_adapter(n=24)
    seed = tmp_path / "seed_merge"
    seed.mkdir()
    (seed / "compA.txt").write_text("base\n", encoding="utf-8")
    (seed / "compB.txt").write_text("base\n", encoding="utf-8")
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="merge",
                            budget=Budget(max_iterations=30, max_metric_calls=4000))
    harness.ensure_splits(adapter, run_dir, seed=3, ratios=(0.34, 0.5, 0.16))
    base = harness.baseline(adapter, seed, run_dir=run_dir)

    def opt(workdir, instructions):  # noqa: ARG001
        # Fix whichever focused component is still missing its marker; this builds
        # two complementary single-component lineages off the seed.
        foc = (workdir / "FOCUS.md").read_text(encoding="utf-8") if (workdir / "FOCUS.md").exists() else ""
        head = foc.split("All components")[0]
        a, b = workdir / "compA.txt", workdir / "compB.txt"
        fa, fb = "[A]" in a.read_text(encoding="utf-8"), "[B]" in b.read_text(encoding="utf-8")
        if "compA.txt" in head and not fa:
            a.write_text(a.read_text(encoding="utf-8") + "[A]\n", encoding="utf-8")
        elif "compB.txt" in head and not fb:
            b.write_text(b.read_text(encoding="utf-8") + "[B]\n", encoding="utf-8")
        elif not fa:
            a.write_text(a.read_text(encoding="utf-8") + "[A]\n", encoding="utf-8")
        elif not fb:
            b.write_text(b.read_text(encoding="utf-8") + "[B]\n", encoding="utf-8")

    res = gepa.gepa_loop(adapter, run_dir=run_dir, optimizer=opt, seed_val=base,
                         max_iterations=12, minibatch_size=4, component_selector="round_robin",
                         max_merges=3, merge_cadence=1, seed=0, gate_kwargs={"mode": "paired"})
    merge_steps = [s for s in res["steps"] if "merge_of" in s]
    assert res["merges"] >= 1, f"merge never fired (merges={res['merges']})"
    assert any(s.get("local_gate") for s in merge_steps), "no merge passed the local gate"
    assert run_dir.read_splits().test_used is False


def test_merge_skips_gracefully_monolith(tmp_path):
    """On a single-file capability the system-aware merge has nothing independent to
    recombine and must skip without crashing."""
    from cap_evolve import gepa
    adapter, run_dir, base = _setup(tmp_path, "g4", max_iterations=10, max_metric_calls=2000)
    optimizer = __import__("cap_evolve").harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}", "--prompt", "{prompt}"])
    res = gepa.gepa_loop(adapter, run_dir=run_dir, optimizer=optimizer, seed_val=base,
                         max_metric_calls=1500, max_iterations=8, minibatch_size=3,
                         max_merges=2, merge_cadence=1, seed=0,
                         gate_kwargs={"mode": "significant", "k_se": 1.0})
    # merge attempts either skip (monolith) or produce a valid step; no crash, and
    # any merge step that exists is well-formed.
    for s in res["steps"]:
        if "merge_of" in s:
            assert "accepted" in s and "local_gate" in s
    assert res["best_val"] == 1.0
