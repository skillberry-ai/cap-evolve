"""Wiring proofs for the helper gate: every algorithm refuses a bad helper before paying for a rollout.

``helper_gate`` itself is tested in test_helper_gate.py. What is proved HERE is that each loop calls it:
hill-climb and skillopt (``harness.run_step``), GEPA (its own loop), HC-2 (its proposal rounds) and the
run start (the baseline phase). agent-optimize's two paths are covered in test_helper_gate.py and
test_ao2_act_and_constraints.py.

For each algorithm, on the zero-API toy benchmark, with helpers on:

* a candidate whose helper branches on the task id (a cheat the lint catches) is refused;
* a candidate whose helper does not import (the smoke catches it) is refused;
* the refused candidate is never measured: no reward, no rollout of it, ``helper_gate_refused`` logged,
  the run's best unchanged;
* with the gate switched off the same candidate is measured, and the run says the gate was off.

If one of these tests fails after a change, an algorithm has started skipping the gate.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "benchmarks" / "toy" / "examples" / "calc"

sys.path.insert(0, str(CORE))

CHEAT = 'def answer(task_id):\n    if task_id == "t1":\n        return 42\n    return None\n'
BROKEN = "import nonexistent_module_xyz\n"
CLEAN = "def f(x):\n    return x\n"
GATE = {"mode": "significant", "k_se": 1.0}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_CORE", str(CORE))
    monkeypatch.setenv("CAPEVOLVE_TOY_DATA", str(EXAMPLE))
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    monkeypatch.delenv("CAPEVOLVE_HELPER_GATE", raising=False)


def _toy_adapter():
    spec = importlib.util.spec_from_file_location("toy_calc_adapter_gate", EXAMPLE / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Adapter()


class CountingAdapter:
    """The toy adapter, counting every rollout so a test can prove a refused candidate cost none."""

    def __init__(self, inner):
        self._inner = inner
        self.rollouts = 0
        self.dirs = []

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def run_target(self, task, ctx, *, seed: int = 0):
        self.rollouts += 1
        self.dirs.append(Path(ctx).name)
        return self._inner.run_target(task, ctx, seed=seed)


def _fresh_run(tmp_path: Path, adapter, *, spec_text: str | None = None, max_iterations=3):
    from cap_evolve import Budget, RunDir, harness
    seed = tmp_path / "seed_capability"
    shutil.copytree(EXAMPLE / "capability", seed)
    rd = RunDir.create(tmp_path / ".capevolve", ts="gate",
                       budget=Budget(max_iterations=max_iterations, stall=5))
    if spec_text is not None:
        spec = tmp_path / "capevolve.yaml"
        spec.write_text(spec_text, encoding="utf-8")
        rd.log_event("spec_resolved", spec=str(spec), project=str(tmp_path))
    harness.ensure_splits(adapter, rd, seed=0)
    base = harness.baseline(adapter, seed, run_dir=rd)
    return rd, base


def _with_helper(script: str):
    """An optimizer that makes the GOOD prompt fix and also ships ``script`` as a helper."""
    def opt(workdir, instructions):
        workdir = Path(workdir)
        p = workdir / "prompt.txt"
        p.write_text(p.read_text(encoding="utf-8") + "\n[CALC] Compute and output only the number.\n",
                     encoding="utf-8")
        d = workdir / "skills" / "calc" / "scripts"
        d.mkdir(parents=True, exist_ok=True)
        (workdir / "skills" / "calc" / "SKILL.md").write_text("---\nname: calc\ndescription: d\n---\n")
        (d / "h.py").write_text(script, encoding="utf-8")
    return opt


def _events(rd, kind: str) -> list[dict]:
    out = []
    for line in (rd.root / "events.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            if e.get("kind") == kind:
                out.append(e)
    return out


# ---- hill-climb and skillopt: harness.run_step -------------------------------------------------------

@pytest.mark.parametrize("script,check", [(CHEAT, "helper_lint"), (BROKEN, "helper_smoke")])
def test_run_step_refuses_a_bad_helper_without_a_rollout(tmp_path, script, check):
    from cap_evolve import harness
    adapter = CountingAdapter(_toy_adapter())
    rd, base = _fresh_run(tmp_path, adapter)
    before = adapter.rollouts
    step = harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                            optimizer=_with_helper(script), instructions="x", current_val=base,
                            gate_kwargs=GATE)
    assert step["candidate_val"] is None and step["decision"]["indecisive"] is True
    assert check in step["helper_gate"]["failure"]
    assert adapter.rollouts == before, "a refused candidate must not cost a rollout"
    assert rd.best_id == "seed"
    refused = _events(rd, "helper_gate_refused")
    assert len(refused) == 1 and refused[0]["candidate"] == step["candidate_id"]


def test_run_step_measures_a_clean_helper(tmp_path):
    from cap_evolve import harness
    adapter = CountingAdapter(_toy_adapter())
    rd, base = _fresh_run(tmp_path, adapter)
    before = adapter.rollouts
    step = harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                            optimizer=_with_helper(CLEAN), instructions="x", current_val=base,
                            gate_kwargs=GATE)
    assert step["candidate_val"] is not None and adapter.rollouts > before
    assert _events(rd, "helper_gate_refused") == []
    assert [e["ok"] for e in _events(rd, "helper_gate")] == [True]


def test_the_refusal_reason_reaches_the_next_proposer(tmp_path):
    from cap_evolve import harness
    from cap_evolve.memory import RejectedMemory
    adapter = _toy_adapter()
    rd, base = _fresh_run(tmp_path, adapter)
    rejected = RejectedMemory(rd.rejected_path)
    harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                     optimizer=_with_helper(CHEAT), instructions="x", current_val=base,
                     gate_kwargs=GATE, rejected=rejected)
    assert "helper gate" in Path(rd.rejected_path).read_text(encoding="utf-8")


def test_hill_climb_never_accepts_a_cheating_helper(tmp_path):
    from cap_evolve import harness
    adapter = _toy_adapter()
    rd, base = _fresh_run(tmp_path, adapter)
    res = harness.hill_climb_loop(adapter, run_dir=rd, optimizer=_with_helper(CHEAT), current_val=base,
                                  max_iterations=2, gate_kwargs=GATE)
    assert res["accepts"] == 0 and rd.best_id == "seed"
    assert all(s["candidate_val"] is None for s in res["steps"])
    assert len(_events(rd, "helper_gate_refused")) == len(res["steps"]) >= 1


def test_skillopt_never_accepts_a_cheating_helper(tmp_path):
    from cap_evolve import skillopt
    adapter = _toy_adapter()
    rd, base = _fresh_run(tmp_path, adapter)
    skillopt.skillopt_loop(adapter, run_dir=rd, optimizer=_with_helper(CHEAT), current_val=base,
                           epochs=1, batch_size=2, slow_update=False, gate_kwargs=GATE)
    assert rd.best_id == "seed"
    assert _events(rd, "helper_gate_refused"), "skillopt must run every proposal through the gate"


def test_with_the_gate_off_the_candidate_is_measured_and_the_run_says_so(tmp_path):
    from cap_evolve import harness
    adapter = CountingAdapter(_toy_adapter())
    rd, base = _fresh_run(tmp_path, adapter, spec_text="helpers:\n  enabled: true\n  gate: false\n")
    before = adapter.rollouts
    step = harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                            optimizer=_with_helper(CHEAT), instructions="x", current_val=base,
                            gate_kwargs=GATE)
    assert step["candidate_val"] is not None and adapter.rollouts > before
    off = _events(rd, "helper_gate_off")
    assert len(off) == 1 and off[0]["reason"] == "helpers.gate: false"


def test_the_env_switch_turns_the_gate_off_too(tmp_path, monkeypatch):
    from cap_evolve import harness
    monkeypatch.setenv("CAPEVOLVE_HELPER_GATE", "0")
    adapter = _toy_adapter()
    rd, base = _fresh_run(tmp_path, adapter)
    step = harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                            optimizer=_with_helper(CHEAT), instructions="x", current_val=base,
                            gate_kwargs=GATE)
    assert step["candidate_val"] is not None
    assert _events(rd, "helper_gate_off")[0]["reason"] == "CAPEVOLVE_HELPER_GATE=0"


def test_with_helpers_off_nothing_changes(tmp_path, monkeypatch):
    from cap_evolve import harness
    monkeypatch.delenv("CAPEVOLVE_HELPERS", raising=False)
    adapter = _toy_adapter()
    rd, base = _fresh_run(tmp_path, adapter)
    step = harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                            optimizer=_with_helper(CHEAT), instructions="x", current_val=base,
                            gate_kwargs=GATE)
    assert step["candidate_val"] is not None
    assert _events(rd, "helper_gate") == [] and _events(rd, "helper_gate_off") == []


def test_a_run_without_helpers_never_resolves_its_helpers_table(tmp_path, monkeypatch):
    # every run before the gate: helpers off, and a disabled helpers table that helpers.resolve would refuse
    # (an unknown key) must not start failing in run_step
    from cap_evolve import harness
    monkeypatch.delenv("CAPEVOLVE_HELPERS", raising=False)
    adapter = _toy_adapter()
    rd, base = _fresh_run(tmp_path, adapter, spec_text="helpers:\n  enabled: false\n  no_such_key: 1\n")
    step = harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                            optimizer=_with_helper(CHEAT), instructions="x", current_val=base,
                            gate_kwargs=GATE)
    assert step["candidate_val"] is not None
    assert _events(rd, "helper_gate") == [] and _events(rd, "helper_gate_off") == []


def test_a_gate_that_cannot_run_stops_run_step(tmp_path):
    from cap_evolve import harness, helper_gate
    adapter = _toy_adapter()
    rd, base = _fresh_run(tmp_path, adapter,
                          spec_text=f"helpers:\n  enabled: true\n  ids_file: {tmp_path / 'missing.txt'}\n")
    with pytest.raises(helper_gate.GateConfigError, match="ids_file"):
        harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                         optimizer=_with_helper(CLEAN), instructions="x", current_val=base,
                         gate_kwargs=GATE)


# ---- GEPA: its own loop ------------------------------------------------------------------------------

@pytest.mark.parametrize("script", [CHEAT, BROKEN])
def test_gepa_refuses_a_bad_helper_before_the_child_minibatch(tmp_path, script):
    from cap_evolve import gepa
    adapter = CountingAdapter(_toy_adapter())
    rd, base = _fresh_run(tmp_path, adapter)
    res = gepa.gepa_loop(adapter, run_dir=rd, optimizer=_with_helper(script), seed_val=base,
                         max_iterations=2, minibatch_size=2, max_merges=0, seed=0, gate_kwargs=GATE)
    refused = {e["candidate"] for e in _events(rd, "helper_gate_refused")}
    assert refused and res["accepts"] == 0 and rd.best_id == "seed"
    # the child minibatch is the first rollout of a child: a refused child never reaches it
    gated = {e["candidate"] for e in _events(rd, "gepa_local_gate")}
    assert not (refused & gated)
    assert not (refused & set(adapter.dirs)), "a refused child's own dir was rolled out"


# ---- HC-2: its proposal rounds ------------------------------------------------------------------------

def test_hc2_drops_a_bad_helper_before_its_round(tmp_path):
    from p2_fakes import make_run
    from cap_evolve import evaluator, harness as h, hc2, promotion
    adapter, rd = make_run(tmp_path, n_train=24, n_val=24, default=0.4, max_metric_calls=3000)
    h.baseline_pooled(adapter, tmp_path / "seed", run_dir=rd, n_trials=2)
    params = promotion.P2Params.from_spec({"promotion_rule": "P2", "p2_conf_n": 96, "p2_ctrl_m": 4})
    ev = evaluator.P2Evaluator(adapter, rd, params)
    seen = []

    def opt(workdir, instructions):
        seen.append(Path(workdir).name)
        cfg = json.loads((Path(workdir) / "cfg.json").read_text())
        cfg.update(default=0.85, salt=len(seen))          # would win the round if it were measured
        (Path(workdir) / "cfg.json").write_text(json.dumps(cfg, indent=1))
        d = Path(workdir) / "skills" / "s" / "scripts"
        d.mkdir(parents=True, exist_ok=True)
        (Path(workdir) / "skills" / "s" / "SKILL.md").write_text("s\n")
        (d / "h.py").write_text(CHEAT)

    out = hc2.hc2_loop(adapter, run_dir=rd, optimizer=opt, evaluator=ev,
                       params=hc2.HC2Params(k=3, per_cluster=2), ctx=h.OptimizerContext(),
                       max_iterations=1, workers=2)
    refused = {e["candidate"] for e in _events(rd, "helper_gate_refused")}
    rounds = _events(rd, "hc2_round")
    assert refused, "the helper gate must see the proposals that pass the diversity gate"
    assert out["accepts"] == 0 and rd.best_id == "seed" and rounds[0]["champion"] is None
    # every proposal is dropped before the round: by the helper gate, or (near-duplicates) by the diversity gate
    # that runs first; none of them is measured
    assert set(rounds[0]["dropped"]) == set(seen) and refused <= set(seen)
    assert _events(rd, "p2_round_open") == [], "with every proposal dropped, no P2 round may be opened"


# ---- the run start: the baseline phase ---------------------------------------------------------------

def _baseline_phase(tmp_path, spec_text: str):
    project = tmp_path / "project"
    (project / "adapters").mkdir(parents=True)
    shutil.copy(EXAMPLE / "adapter.py", project / "adapters" / "adapter.py")   # where load_adapter looks
    shutil.copytree(EXAMPLE / "capability", project / "capability")
    (project / "capevolve.yaml").write_text(spec_text, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(REPO / "skills" / "phases" / "baseline" / "scripts" / "run.py"),
         "--base", str(tmp_path / ".capevolve"), "--project", str(project),
         "--capability", str(project / "capability"), "--max-iterations", "1"],
        capture_output=True, text=True, cwd=tmp_path, timeout=300)


def test_a_gate_that_cannot_run_stops_the_run_before_the_baseline(tmp_path):
    r = _baseline_phase(tmp_path, f"helpers:\n  enabled: true\n  ids_file: {tmp_path / 'missing.txt'}\n")
    assert r.returncode != 0
    assert "GateConfigError" in r.stderr and "ids_file" in r.stderr
    assert not list((tmp_path / ".capevolve").glob("run_*/rollouts/*/*.json")), "no rollout may have run"


def test_the_baseline_phase_warns_when_the_gate_is_off(tmp_path):
    r = _baseline_phase(tmp_path, "helpers:\n  enabled: true\n  gate: false\n")
    assert "helper gate is off" in r.stderr
    events = [json.loads(ln) for f in (tmp_path / ".capevolve").glob("run_*/events.jsonl")
              for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert any(e.get("kind") == "helper_gate_off" for e in events)
