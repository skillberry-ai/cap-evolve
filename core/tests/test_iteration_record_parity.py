"""Every algorithm writes the SAME iteration record + run-level JOURNAL (#216, #224).

The bug this locks down: an algorithm can only be seen by its consumers if it routes
through the one step that records an iteration. GEPA has its own loop and bypassed
``harness.run_step`` by design, so it charged iterations against the budget while
writing NO ``step`` event and NEVER reconciling the run-level ``JOURNAL.md`` — its
``LEDGER.md`` / ``RUNMAP.md`` / ``prior_iterations/`` stayed empty for the whole run
while the optimizer prompt told it to read them, and every handover entry its
optimizer wrote was silently discarded by the next iteration's ``_seed_journal``.

The fix is a shared seam, ``harness.record_iteration``. This file checks it two ways:

  * the parametrized tests run each algorithm that HAS a runnable loop today and assert
    the record + journal it produces. They enumerate — a sixth algorithm is invisible to
    them until someone adds it here, which is the same forgetting this PR exists to stop;
  * ``test_exactly_one_place_charges_an_iteration`` closes that gap by asserting on the
    SOURCE that only ``record_iteration`` charges an iteration at all. That one holds for
    an algorithm nobody has written yet.

Offline, deterministic, zero API — the mock optimizer skill over toy_calc.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "toy_calc"
MOCK_RUN = REPO / "skills" / "optimizers" / "run-optimizer" / "scripts" / "run.py"
AGENT_COMMIT = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts" / "commit.py"

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


def _setup(tmp_path, ts):
    from cap_evolve import Budget, RunDir, harness
    adapter = _toy_adapter()
    seed = tmp_path / f"seed_{ts}"
    shutil.copytree(EXAMPLE / "capability", seed)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts=ts,
                            budget=Budget(max_iterations=6, max_metric_calls=400, stall=6))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)
    return adapter, run_dir, base, seed


def _mock_optimizer():
    from cap_evolve import harness
    return harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock",
         "--workdir", "{workdir}", "--prompt", "{prompt}"])


GATE = {"mode": "significant", "k_se": 1.0}


# --- one runner per algorithm ----------------------------------------------

def _run_hill_climb(tmp_path):
    from cap_evolve import harness
    adapter, run_dir, base, _ = _setup(tmp_path, "hc")
    harness.hill_climb_loop(adapter, run_dir=run_dir, optimizer=_mock_optimizer(),
                            current_val=base, max_iterations=3, gate_kwargs=dict(GATE))
    return run_dir


def _run_gepa(tmp_path):
    from cap_evolve import gepa
    adapter, run_dir, base, _ = _setup(tmp_path, "gp")
    gepa.gepa_loop(adapter, run_dir=run_dir, optimizer=_mock_optimizer(), seed_val=base,
                   max_iterations=3, max_metric_calls=300, minibatch_size=3,
                   max_merges=0, seed=0, gate_kwargs=dict(GATE))
    return run_dir


def _run_skillopt(tmp_path):
    from cap_evolve import skillopt
    adapter, run_dir, base, _ = _setup(tmp_path, "so")
    skillopt.skillopt_loop(adapter, run_dir=run_dir, optimizer=_mock_optimizer(),
                           current_val=base, epochs=1, batch_size=2, slow_update=False,
                           gate_kwargs=dict(GATE))
    return run_dir


def _run_agent_optimize(tmp_path):
    """agent-optimize / evograph are AGENT-mode: the loop is the coding agent, and its
    end-of-iteration is ``agent-optimize/scripts/commit.py`` (evograph's SKILL.md points
    at the same seam). Drive that script exactly as the agent would."""
    _adapter, run_dir, _base, seed = _setup(tmp_path, "ao")
    work = tmp_path / "cand_r1"
    shutil.copytree(seed, work)
    (work / "prompt.txt").write_text("[CALC] answer the arithmetic.\n", encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(CORE))
    for cid, decision, val in (("cand_r1", "accept", "1.0"), ("cand_r2", "reject", "0.5")):
        out = subprocess.run(
            [sys.executable, str(AGENT_COMMIT), "--run-dir", str(run_dir.root),
             "--candidate-id", cid, "--from-dir", str(work), "--decision", decision,
             "--val", val, "--note", f"{decision} via commit.py"],
            capture_output=True, text=True, env=env, cwd=str(AGENT_COMMIT.parent))
        assert out.returncode == 0, out.stdout + out.stderr
    return run_dir


ALGORITHMS = {
    "hill-climb": _run_hill_climb,
    "gepa": _run_gepa,
    "skillopt": _run_skillopt,
    "agent-optimize": _run_agent_optimize,
}


def _events(run_dir, kind):
    return [json.loads(ln) for ln in
            run_dir.events_path.read_text(encoding="utf-8").splitlines() if ln.strip()
            if json.loads(ln).get("kind") == kind]


@pytest.mark.parametrize("algorithm", sorted(ALGORITHMS))
def test_every_algorithm_writes_the_iteration_record_and_journal(algorithm, tmp_path):
    run_dir = ALGORITHMS[algorithm](tmp_path)

    steps = _events(run_dir, "step")
    assert steps, f"{algorithm} recorded NO iteration — it bypasses harness.record_iteration"

    # One record per iteration charged. This single assertion is what caught #109/#216:
    # gepa charged 3 iterations and wrote 1 gepa_val_gate (and no `step` at all).
    assert len(steps) == run_dir.spent.iterations, (
        f"{algorithm}: {len(steps)} iteration records for "
        f"{run_dir.spent.iterations} charged iterations")

    # ...and exactly one per candidate: skillopt used to log `step` AND `skillopt_step`
    # for the same candidate, so consumers counted the iteration twice.
    cids = [s.get("candidate") for s in steps]
    assert all(cids) and len(set(cids)) == len(cids), f"{algorithm}: duplicate records {cids}"

    # Every record carries the lineage edge `_parent_map` / LEDGER / RUNMAP read.
    for s in steps:
        assert s.get("parent"), f"{algorithm}: record {s.get('candidate')} has no parent"
        assert "accept" in s, f"{algorithm}: record {s.get('candidate')} has no verdict"

    # The run-level append-only JOURNAL — the whole of #216.
    journal = run_dir.root / "JOURNAL.md"
    assert journal.exists(), f"{algorithm} wrote no run-level JOURNAL.md"
    text = journal.read_text(encoding="utf-8")
    assert text.strip(), f"{algorithm}: JOURNAL.md is empty"
    for s in steps:
        assert s["candidate"] in text, \
            f"{algorithm}: {s['candidate']} missing from JOURNAL.md"


@pytest.mark.parametrize("algorithm", sorted(ALGORITHMS))
def test_no_consumer_is_left_empty(algorithm, tmp_path):
    """The optimizer-facing files rebuilt from the iteration record must be populated.

    #109's symptom: gepa's LEDGER said "(baseline only)" and "Current best: seed" for a
    run with real accepted candidates, because both are rebuilt from ``step`` events.
    """
    from cap_evolve import harness
    run_dir = ALGORITHMS[algorithm](tmp_path)
    steps = _events(run_dir, "step")

    assert harness._parent_map(run_dir), f"{algorithm}: empty parent map"

    wd = tmp_path / f"ledger_{algorithm}"
    wd.mkdir()
    harness._build_ledger(wd, run_dir)
    harness._build_runmap(wd, run_dir)
    ledger = (wd / "LEDGER.md").read_text(encoding="utf-8")
    runmap = (wd / "RUNMAP.md").read_text(encoding="utf-8")
    assert "(baseline only)" not in ledger, f"{algorithm}: LEDGER shows no iterations"
    assert "(no prior iterations yet)" not in runmap, f"{algorithm}: RUNMAP shows none"
    for s in steps:
        assert s["candidate"] in ledger, f"{algorithm}: {s['candidate']} missing from LEDGER"


# --- the invariant itself, asserted on the SOURCE ---------------------------

def _iteration_charge_sites():
    """Every ``update_spent(iterations=...)`` call in the tree, as (file, line, enclosing
    function). Parsed with ``ast`` — no import side effects, and it sees algorithms this
    test file has never heard of, which a parametrized list of known algorithms cannot."""
    import ast
    roots = [REPO / "core" / "cap_evolve", REPO / "skills"]
    sites = []
    for root in roots:
        for py in sorted(root.rglob("*.py")):
            if "build/lib" in py.as_posix():  # stale build artifact
                continue
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            # enclosing function for every node, resolved by walking down from each def
            for fn in [n for n in ast.walk(tree)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
                for node in ast.walk(fn):
                    if (isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Attribute)
                            and node.func.attr == "update_spent"
                            and any(kw.arg == "iterations" for kw in node.keywords)):
                        sites.append((py.relative_to(REPO).as_posix(), node.lineno, fn.name))
    return sites


def test_exactly_one_place_charges_an_iteration():
    """The invariant behind this whole PR, enforced instead of asserted in prose.

    An algorithm becomes visible to LEDGER/RUNMAP/JOURNAL/the dashboard only by routing
    through ``harness.record_iteration``. The only way to make that unforgettable is to
    make charging an iteration and recording it the SAME call — so there must be exactly
    one ``update_spent(iterations=...)`` call site in the tree, inside
    ``record_iteration``.

    Unlike the parametrized tests above (which can only cover algorithms someone
    remembered to list), this holds for an algorithm that does not exist yet: add a sixth
    loop that charges its own iterations and this fails, naming the file and line.
    """
    sites = _iteration_charge_sites()
    assert len(sites) == 1, (
        "an iteration must be charged in exactly ONE place — "
        "harness.record_iteration, which also writes the `step` record and reconciles "
        f"JOURNAL.md. Found {len(sites)}: {sites}. If one of these is a new algorithm's "
        "loop, call harness.record_iteration instead of update_spent(iterations=...)."
    )
    path, _line, func = sites[0]
    assert path == "core/cap_evolve/harness.py", f"unexpected charge site: {path}"
    assert func == "record_iteration", f"charge site moved out of the seam into {func}()"
