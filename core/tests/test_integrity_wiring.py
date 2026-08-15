"""Wiring proofs for the protected-path seal and the convergence signal.

``integrity`` / ``convergence`` are unit-tested elsewhere (test_integrity.py,
test_convergence.py). What is proved HERE is the wiring into the optimization loop:

* both knobs default OFF — a call with no new kwargs behaves identically;
* a candidate that edits a protected file is INDECISIVE, not rejected at 0.0:
  best_id unchanged, stall counter untouched, ``tamper_detected`` logged, and
  **no rollouts paid for** (the verify happens before ``evaluate_candidate``);
* a clean candidate under the same patterns still accepts normally;
* a plateaued run escalates, the advice reaches the optimizer instructions, and the
  signal is pure (a rebuilt observation list gives the identical verdict).
"""

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "toy_calc"

sys.path.insert(0, str(CORE))

PATTERNS = ("*gold*", "scorer.py")


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    yield
    os.environ.clear()
    os.environ.update(old)


def _toy_adapter():
    spec = importlib.util.spec_from_file_location("toy_calc_adapter", EXAMPLE / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Adapter()


class CountingAdapter:
    """Delegates to the toy adapter but counts every rollout, so a test can prove a
    tampered candidate never cost a single eval."""

    def __init__(self, inner):
        self._inner = inner
        self.rollouts = 0

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def run_target(self, task, ctx, *, seed: int = 0):
        self.rollouts += 1
        return self._inner.run_target(task, ctx, seed=seed)


def _seed_dir(tmp_path: Path, name="seed_capability") -> Path:
    """Toy capability + the two files we declare protected (the eval surface)."""
    seed = tmp_path / name
    shutil.copytree(EXAMPLE / "capability", seed)
    (seed / "gold.json").write_text('{"t1": "3"}\n', encoding="utf-8")
    (seed / "scorer.py").write_text("REWARD_FOR = 'exact match'\n", encoding="utf-8")
    return seed


def _fresh_run(tmp_path: Path, adapter, ts: str, **budget):
    from cap_evolve import Budget, RunDir, harness
    seed = _seed_dir(tmp_path / ts)
    rd = RunDir.create(tmp_path / ts / ".capevolve", ts=ts,
                       budget=Budget(**({"max_iterations": 5, "stall": 2} | budget)))
    harness.ensure_splits(adapter, rd, seed=0)
    base = harness.baseline(adapter, seed, run_dir=rd)
    return rd, base


def _fix_prompt(workdir: Path, instructions: str):
    """A GOOD optimizer: adds the marker the toy adapter needs. Touches nothing else."""
    p = workdir / "prompt.txt"
    p.write_text(p.read_text(encoding="utf-8") + "\n[CALC] Compute and output only the number.\n",
                 encoding="utf-8")


def _hack_gold(workdir: Path, instructions: str):
    """A REWARD HACKER: rewrites the gold answers instead of the capability.

    Deletes then rewrites, which is how editors (and ``git checkout``) write, and which
    succeeds even after ``set_readonly`` cleared the file's write bit — the chmod layer
    is explicitly best-effort, so this is the case the hash manifest exists to catch.
    """
    p = workdir / "gold.json"
    p.unlink(missing_ok=True)
    p.write_text('{"t1": "anything goes"}\n', encoding="utf-8")


def _events(run_dir, kind: str) -> list[dict]:
    path = run_dir.root / "events.jsonl"
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            if e.get("kind") == kind:
                out.append(e)
    return out


# --- default off ⇒ identical behavior --------------------------------------

def test_defaults_are_a_noop(tmp_path):
    """A loop run with no new kwargs and one with the knobs explicitly off produce the
    same accept/reject decisions and the same final numbers."""
    from cap_evolve import harness
    adapter = _toy_adapter()

    seq = iter(range(9))

    def summarize(**extra):
        rd, base = _fresh_run(tmp_path, adapter, f"ts{next(seq)}")
        res = harness.hill_climb_loop(
            adapter, run_dir=rd, optimizer=_fix_prompt, current_val=base,
            max_iterations=3, gate_kwargs={"mode": "significant", "k_se": 1.0}, **extra)
        return {
            "best_val": res["best_val"], "accepts": res["accepts"],
            "iterations": res["iterations"], "stop_reason": res["stop_reason"],
            "decisions": [(s["accepted"], s["decision"]["indecisive"]) for s in res["steps"]],
            "rewards": [s["candidate_val"]["reward"] for s in res["steps"]],
            "stall": rd.spent.stall,
        }

    assert summarize() == summarize(protected_patterns=None, convergence=False)
    # ...and the run really did the normal thing.
    assert summarize()["best_val"] == 1.0


def test_run_step_default_off_never_snapshots(tmp_path):
    """No protected_patterns ⇒ no manifest is written and a candidate is free to edit
    anything (today's behavior, unchanged)."""
    from cap_evolve import harness
    adapter = _toy_adapter()
    rd, base = _fresh_run(tmp_path, adapter, "off")
    step = harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                            optimizer=_hack_gold, instructions="x", current_val=base,
                            gate_kwargs={"mode": "significant", "k_se": 1.0})
    assert step["candidate_val"] is not None      # it WAS measured
    assert "tamper" not in step
    assert not list((rd.root / "work").glob("*.integrity.json"))
    assert _events(rd, "tamper_detected") == []


# --- the catch ---------------------------------------------------------------

def test_tampered_candidate_is_indecisive_and_costs_nothing(tmp_path):
    from cap_evolve import harness
    adapter = CountingAdapter(_toy_adapter())
    rd, base = _fresh_run(tmp_path, adapter, "tamper")
    best_before, stall_before = rd.best_id, rd.spent.stall
    rollouts_after_baseline = adapter.rollouts

    step = harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                            optimizer=_hack_gold, instructions="improve val",
                            current_val=base, protected_patterns=PATTERNS,
                            gate_kwargs={"mode": "significant", "k_se": 1.0})

    # 1. indecisive, NOT a rejection at 0.0 — there is no reward at all.
    assert step["candidate_val"] is None
    assert step["decision"]["indecisive"] is True
    assert step["accepted"] is False
    assert "gold.json" in step["tamper"]["modified"]

    # 2. the best candidate is untouched...
    assert rd.best_id == best_before
    # 3. ...and so is the stall counter (an unjudged candidate is not a "no-accept").
    assert rd.spent.stall == stall_before
    # 4. the iteration is still counted as spent.
    assert rd.spent.iterations == 1
    # 5. NO rollouts were paid for: verify runs before evaluate_candidate.
    assert adapter.rollouts == rollouts_after_baseline

    # 6. auditable.
    ev = _events(rd, "tamper_detected")
    assert len(ev) == 1 and "gold.json" in ev[0]["report"]["modified"]
    assert "TAMPERED" in ev[0]["reason"]
    assert len(_events(rd, "step_indecisive")) == 1
    # forensics snapshot of what the optimizer actually did
    assert (rd.candidate_dir(step["candidate_id"]) / "gold.json").exists()


def test_added_and_removed_protected_files_are_caught(tmp_path):
    from cap_evolve import harness
    adapter = _toy_adapter()
    for name, opt in (("add", lambda w, i: (w / "gold_extra.json").write_text("{}")),
                      ("del", lambda w, i: (w / "gold.json").unlink())):
        rd, base = _fresh_run(tmp_path, adapter, f"t_{name}")
        step = harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                                optimizer=opt, instructions="x", current_val=base,
                                protected_patterns=PATTERNS,
                                gate_kwargs={"mode": "significant", "k_se": 1.0})
        assert step["candidate_val"] is None and step["decision"]["indecisive"] is True


def test_clean_candidate_still_accepts_under_the_same_patterns(tmp_path):
    """The seal must not block a legitimate edit."""
    from cap_evolve import harness
    from cap_evolve.loop import SplitResult
    adapter = _toy_adapter()
    rd, base = _fresh_run(tmp_path, adapter, "clean")
    step = harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                            optimizer=_fix_prompt, instructions="improve val",
                            current_val=base, protected_patterns=PATTERNS,
                            gate_kwargs={"mode": "significant", "k_se": 1.0})
    assert step["accepted"] is True
    assert SplitResult.from_dict(step["candidate_val"]).reward == 1.0
    assert rd.best_id == step["candidate_id"]
    assert _events(rd, "tamper_detected") == []


def test_hill_climb_loop_threads_the_patterns(tmp_path):
    """The loop (not just run_step) enforces the seal, and a tampered iteration never
    becomes best."""
    from cap_evolve import harness
    adapter = CountingAdapter(_toy_adapter())
    rd, base = _fresh_run(tmp_path, adapter, "loop")
    before = adapter.rollouts
    res = harness.hill_climb_loop(adapter, run_dir=rd, optimizer=_hack_gold,
                                  current_val=base, max_iterations=3,
                                  protected_patterns=PATTERNS,
                                  gate_kwargs={"mode": "significant", "k_se": 1.0})
    assert res["accepts"] == 0
    assert res["best_id"] == "seed"
    assert res["best_val"] == base.reward
    assert all(s["candidate_val"] is None for s in res["steps"])
    assert adapter.rollouts == before, "a tampered loop must not spend on rollouts"
    assert len(_events(rd, "tamper_detected")) == len(res["steps"])
    # stall never advanced, so the run was NOT killed by a fake plateau
    assert rd.spent.stall == 0


def test_gepa_seals_before_its_minibatch_spend(tmp_path):
    """GEPA runs the optimizer itself (not via run_step), so it carries its own seal:
    a tampered child never reaches even the CHEAP minibatch eval."""
    from cap_evolve import Budget, RunDir, gepa, harness
    adapter = CountingAdapter(_toy_adapter())
    seed = _seed_dir(tmp_path / "g", "seed_g")
    rd = RunDir.create(tmp_path / "g" / ".capevolve", ts="g",
                       budget=Budget(max_iterations=2, max_metric_calls=500))
    harness.ensure_splits(adapter, rd, seed=0)
    base = harness.baseline(adapter, seed, run_dir=rd)
    res = gepa.gepa_loop(adapter, run_dir=rd, optimizer=_hack_gold, seed_val=base,
                         max_iterations=2, protected_patterns=PATTERNS, store=None)

    assert res["accepts"] == 0 and res["best_id"] == "seed"
    assert all(s["candidate_val"] is None for s in res["steps"])
    assert all("tamper" in s for s in res["steps"])
    # The parent's minibatch eval happens BEFORE the optimizer runs (unavoidable), but
    # nothing was spent on the CHILD: no ``mb_c`` (child minibatch) rollouts exist.
    written = [p.name for p in (rd.root / "rollouts").rglob("*.json")]
    assert not [n for n in written if "mb_c" in n], written
    assert rd.spent.stall == 0
    assert len(_events(rd, "tamper_detected")) == len(res["steps"])


def test_parse_protected_paths():
    from cap_evolve import harness, integrity
    assert harness.parse_protected_paths("") is None
    assert harness.parse_protected_paths(None) is None
    assert harness.parse_protected_paths([]) is None
    assert harness.parse_protected_paths("a,b") == ("a", "b")
    assert harness.parse_protected_paths(["a", " b "]) == ("a", "b")
    assert harness.parse_protected_paths("default") == tuple(integrity.DEFAULT_PATTERNS)


# --- convergence wiring -----------------------------------------------------

def _plateau_optimizer(workdir: Path, instructions: str):
    """A useless optimizer: it records the prompt it was given and changes nothing, so
    every iteration measures the baseline again — a genuine plateau."""
    _plateau_optimizer.prompts.append(instructions)
    return None


def test_convergence_escalates_injects_advice_and_stops(tmp_path):
    from cap_evolve import harness
    adapter = _toy_adapter()
    rd, base = _fresh_run(tmp_path, adapter, "conv", max_iterations=20, stall=0)
    _plateau_optimizer.prompts = []

    res = harness.hill_climb_loop(adapter, run_dir=rd, optimizer=_plateau_optimizer,
                                  current_val=base, max_iterations=20, convergence=True,
                                  gate_kwargs={"mode": "significant", "k_se": 1.0})

    levels = [e["level"] for e in _events(rd, "convergence")]
    assert "warn" in levels and "paradigm_shift" in levels and "stop" in levels
    assert levels == sorted(levels, key=["warn", "paradigm_shift", "stop"].index), \
        "escalation must be monotonic"
    # it BROKE the loop early rather than burning all 20 iterations
    assert res["iterations"] < 20
    assert res["stop_reason"] == "converged"
    # the advice reached the optimizer verbatim
    joined = "\n".join(_plateau_optimizer.prompts)
    assert "PLATEAU WARNING" in joined
    assert "PARADIGM SHIFT REQUIRED" in joined
    # the last prompt sent is the escalated one, not a stale 'ok' prompt
    assert "PARADIGM SHIFT REQUIRED" in _plateau_optimizer.prompts[-1]


def test_convergence_off_by_default_runs_the_full_budget(tmp_path):
    from cap_evolve import harness
    adapter = _toy_adapter()
    rd, base = _fresh_run(tmp_path, adapter, "noconv", max_iterations=12, stall=0)
    _plateau_optimizer.prompts = []
    res = harness.hill_climb_loop(adapter, run_dir=rd, optimizer=_plateau_optimizer,
                                  current_val=base, max_iterations=12,
                                  gate_kwargs={"mode": "significant", "k_se": 1.0})
    assert res["iterations"] == 12          # nothing escalated, nothing broke early
    assert res["stop_reason"].startswith("max_iterations")
    assert _events(rd, "convergence") == []
    assert "PLATEAU WARNING" not in "\n".join(_plateau_optimizer.prompts)


def test_signal_is_pure_across_a_rebuild(tmp_path):
    """Resume-safety: rebuilding the observation list from the recorded steps (as a
    resumed run would) yields the identical signal."""
    from cap_evolve import convergence, harness
    adapter = _toy_adapter()
    rd, base = _fresh_run(tmp_path, adapter, "pure", max_iterations=12, stall=0)
    res = harness.hill_climb_loop(adapter, run_dir=rd, optimizer=_plateau_optimizer,
                                  current_val=base, max_iterations=12, convergence=True,
                                  gate_kwargs={"mode": "significant", "k_se": 1.0})

    obs = harness._convergence_observations(res["steps"])
    first = convergence.assess(obs, baseline=base.reward)
    # rebuilt from scratch, from a round-tripped copy of the same steps
    rebuilt = harness._convergence_observations(json.loads(json.dumps(res["steps"])))
    assert convergence.assess(rebuilt, baseline=base.reward).to_dict() == first.to_dict()
    assert first.level in ("paradigm_shift", "stop")


def test_tampered_steps_do_not_pollute_the_trend(tmp_path):
    """A tampered step has no reward, so it must be SKIPPED when building the trend —
    counting it (as a 0.0) would fake a plateau."""
    from cap_evolve import harness
    steps = [{"candidate_id": "a", "accepted": True,
              "candidate_val": {"reward": 0.5, "stderr": 0.01}},
             {"candidate_id": "b", "accepted": False, "candidate_val": None,
              "tamper": {"ok": False}},
             {"candidate_id": "c", "accepted": True,
              "candidate_val": {"reward": 0.9, "stderr": 0.01}}]
    obs = harness._convergence_observations(steps)
    assert [o.id for o in obs] == ["a", "c"]
    assert [o.reward for o in obs] == [0.5, 0.9]
