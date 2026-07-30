"""End-to-end proof slice — the whole pipeline, zero API cost, deterministic.

Drives the real toy_calc adapter and the real `mock` optimizer skill script
(via subprocess, exactly as a host would) through:
    cap-evolve check -> baseline -> all-at-once step -> finalize -> report-equivalent
and asserts the honesty guarantees hold. This is the CI gate that proves the
architecture works without any model.
"""

import os
import re
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "toy_calc"
MOCK_RUN = REPO / "skills" / "optimizers" / "run-optimizer" / "scripts" / "run.py"

sys.path.insert(0, str(CORE))
sys.path.insert(0, str(EXAMPLE))  # import the toy adapter


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    os.environ["CAPEVOLVE_MOCK_SCRIPT"] = str(EXAMPLE / "mock_script.json")
    yield
    os.environ.clear()
    os.environ.update(old)


def test_full_slice(tmp_path):
    from cap_evolve import Budget, RunDir, TestSealError, harness
    from cap_evolve.loop import SplitResult
    import importlib.util
    spec = importlib.util.spec_from_file_location("toy_calc_adapter", EXAMPLE / "adapter.py")
    toy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(toy)

    adapter = toy.Adapter()

    # seed capability (copy so the loop can mutate copies, not the example)
    seed = tmp_path / "seed_capability"
    shutil.copytree(EXAMPLE / "capability", seed)

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="t", budget=Budget(max_iterations=5, stall=2))

    # baseline: splits frozen, seed scored on val
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)
    assert base.reward == 0.0, "seed prompt lacks [CALC]; baseline must fail"

    # one optimize step using the REAL mock optimizer skill (subprocess)
    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}", "--prompt", "{prompt}"]
    )
    step = harness.run_step(
        adapter, run_dir=run_dir,
        parent_dir=run_dir.candidate_dir("seed"),
        optimizer=optimizer,
        instructions="improve val pass rate",
        current_val=base,
        gate_kwargs={"mode": "significant", "k_se": 1.0},
    )
    assert step["accepted"] is True, "adding [CALC] should clear the significance gate"
    assert SplitResult.from_dict(step["candidate_val"]).reward == 1.0

    # finalize: test scored once
    best_dir = run_dir.candidate_dir(run_dir.best_id)
    payload = harness.finalize(adapter, run_dir=run_dir, best_dir=best_dir)
    assert payload["test"]["reward"] == 1.0

    # test is sealed: a second finalize must refuse
    with pytest.raises(TestSealError):
        harness.finalize(adapter, run_dir=run_dir, best_dir=best_dir)


def test_cyclic_variant_also_improves(tmp_path):
    """The shared hill-climb loop works for a focus variant (cyclic), end to end."""
    from cap_evolve import RunDir, harness
    import importlib.util
    spec = importlib.util.spec_from_file_location("toy_calc_adapter", EXAMPLE / "adapter.py")
    toy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(toy)
    adapter = toy.Adapter()
    seed = tmp_path / "seed"
    shutil.copytree(EXAMPLE / "capability", seed)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="cyc",
                            budget=__import__("cap_evolve").Budget(max_iterations=5, stall=2))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)

    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}", "--prompt", "{prompt}"])
    summary = harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=optimizer, current_val=base,
        focus="cyclic", max_iterations=5, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="cyclic",
    )
    assert summary["accepts"] >= 1
    assert summary["best_val"] == 1.0


def test_baseline_better_than_nothing_is_gated(tmp_path):
    """A no-op edit (no change) must be rejected by the significance gate."""
    from cap_evolve import RunDir, harness
    import importlib.util
    spec = importlib.util.spec_from_file_location("toy_calc_adapter", EXAMPLE / "adapter.py")
    toy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(toy)
    adapter = toy.Adapter()
    seed = tmp_path / "seed"
    shutil.copytree(EXAMPLE / "capability", seed)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="t2")
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)

    noop = harness.optimizer_from_command(["python3", "-c", "import sys; sys.exit(0)"])
    step = harness.run_step(
        adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir("seed"),
        optimizer=noop, instructions="(no-op)", current_val=base,
        gate_kwargs={"mode": "significant", "k_se": 1.0},
    )
    assert step["accepted"] is False


# --------------------------------------------------------------------------
# The worked reference project (issue #108). These drive the COMMITTED example
# files — capevolve.yaml, PROJECT.md, adapter.py — through the real CLI, so a
# contract change breaks a test instead of silently rotting the docs.
# --------------------------------------------------------------------------

def _build_reference_project(dest: Path) -> Path:
    """Assemble the project dir exactly as examples/toy_calc/run.sh does."""
    proj = dest / ".capevolve" / "project"
    (proj / "adapters").mkdir(parents=True)
    shutil.copy(EXAMPLE / "adapter.py", proj / "adapters" / "adapter.py")
    shutil.copy(EXAMPLE / "capevolve.yaml", proj / "capevolve.yaml")
    shutil.copy(EXAMPLE / "PROJECT.md", proj / "PROJECT.md")
    shutil.copytree(EXAMPLE / "capability", dest / "seed_capability")
    return proj


def test_worked_reference_check_and_spec_are_honest(tmp_path):
    """`cap-evolve check` accepts the reference, and its spec obeys the current rules.

    Guards the two rules a scaffolded example most easily gets wrong:
      * `protected_paths: []` is a HARD ERROR (#142/#197), so the reference must OMIT
        the key rather than declare an empty list;
      * the val split must clear the harness floor (#113) — these ratios give val=2,
        which is exactly MIN_VAL_TASKS.
    """
    from cap_evolve.check import run_check
    from cap_evolve.specfile import read_yaml

    proj = _build_reference_project(tmp_path)

    rep = run_check(proj)
    assert rep.ok, f"cap-evolve check rejected the worked reference: {rep.to_dict()}"
    assert rep.stubs == [] and rep.problems == []

    raw = (proj / "capevolve.yaml").read_text(encoding="utf-8")
    spec = read_yaml(raw)
    # An empty protected_paths is a hard error, so the reference must not declare one.
    assert "protected_paths" not in spec, "the reference must OMIT protected_paths (empty = hard error)"
    # ...and not as a live (uncommented) line either.
    assert not [ln for ln in raw.splitlines()
                if ln.strip().startswith("protected_paths")], "protected_paths is declared"

    # Splits must clear the val floor on the real dataset.
    import importlib.util
    aspec = importlib.util.spec_from_file_location("ref_adapter_spec", EXAMPLE / "adapter.py")
    toy = importlib.util.module_from_spec(aspec)
    aspec.loader.exec_module(toy)
    n = len(toy.Adapter().tasks("all"))
    n_val = int(n * float(spec["split_val"]))
    assert n_val >= 2, f"val split is {n_val} task(s); the harness floor is 2"

    # No unfilled template placeholders left in either doc (issue #108's ask).
    template = (REPO / "templates" / "project" / "PROJECT.md").read_text(encoding="utf-8")
    tokens = set(re.findall(r"<[^<>\n]{2,40}>", template))
    assert tokens, "template has no placeholders to compare against — did its shape change?"
    for name in ("capevolve.yaml", "PROJECT.md"):
        body = (proj / name).read_text(encoding="utf-8")
        assert "Acapo" not in body, f"{name} carries the pre-rebrand name"
        left = sorted(t for t in tokens if t in body)
        assert not left, f"{name} still carries unfilled template placeholders: {left}"
    project_md = (proj / "PROJECT.md").read_text(encoding="utf-8")
    assert "Honest limits" in project_md, "the reference must keep its honest-limits section"


def test_worked_reference_runs_end_to_end(tmp_path):
    """A real zero-API `cap-evolve run` on the reference, through to the sealed test."""
    import json
    import subprocess

    proj = _build_reference_project(tmp_path)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(CORE)
    env["CAPEVOLVE_SKILLS_DIR"] = str(REPO / "skills")

    proc = subprocess.run(
        [sys.executable, "-m", "cap_evolve.cli", "run",
         "--spec", str(proj / "capevolve.yaml"), "--project", str(proj), "--run-ts", "ref"],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"run failed:\n{proc.stdout}\n{proc.stderr}"
    # The run prints one or more JSON objects; the summary is the last top-level one.
    dec, objs, i = json.JSONDecoder(), [], 0
    while (i := proc.stdout.find("{", i)) != -1:
        try:
            obj, end = dec.raw_decode(proc.stdout, i)
        except json.JSONDecodeError:
            i += 1
            continue
        objs.append(obj)
        i = end
    summary = objs[-1]
    assert summary["baseline_val"] == 0.0
    assert summary["test_reward"] == 1.0, summary
    assert summary["test_delta"] == 1.0

    # The gate's honest caveat: a deterministic scorer gives SE(delta)=0, so the paired
    # gate takes its documented STRICT fallback. PROJECT.md claims exactly this; if the
    # gate stops warning, the claim is stale and this fails.
    events = [json.loads(l) for l in
              (tmp_path / ".capevolve" / "run_ref" / "events.jsonl").read_text().splitlines()]
    assert any(e.get("kind") == "gate_warning" for e in events), \
        "PROJECT.md documents an SE=0 STRICT fallback; no gate_warning was logged"
    accepted = [e for e in events if e.get("kind") == "step" and e.get("accept")]
    assert accepted and "STRICT fallback" in accepted[0]["reason"], accepted
