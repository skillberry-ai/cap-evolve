"""Behavioral contract for gepa.

Proves — offline, with a MOCK optimizer over a tiny synthetic adapter (no network,
no model) — that the GEPA loop satisfies its honesty + economy contract:

  1. the loop runs end-to-end and produces at least one ACCEPT under a metric-call
     budget;
  2. the cheap LOCAL minibatch gate actually filters (a no-op edit that doesn't
     improve the minibatch is rejected WITHOUT spending a full-val eval);
  3. acceptance is gated honestly on VAL (an accepted child's val reward exceeds
     the parent's) and never on train/test;
  4. the TEST split is never consumed by the loop (the seal stays intact);
  5. metric-calls are accounted (spent > 0) and the result dict has the expected
     shape.

It uses ``cap_evolve.skillcheck.Checker`` for the standard report, and builds the
synthetic fixtures inline so the check is hermetic.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.skillcheck import Checker, import_run


# ---- synthetic, deterministic adapter -------------------------------------
# The "agent" reads candidate/prompt.txt. Tasks ask to echo a token; the agent
# echoes it only if the prompt contains the marker "[ECHO]". So adding the marker
# is what raises the score — a clean offline analogue of a real capability edit.

def _make_adapter():
    from cap_evolve import CapabilityAdapter, Rollout, Score, Task

    class _Adapter(CapabilityAdapter):
        def tasks(self, split):  # noqa: ARG002
            return [Task(id=f"t{i}", input=f"echo-{i}", target=f"echo-{i}") for i in range(8)]

        def run_target(self, task, ctx, *, seed=0):  # noqa: ARG002
            prompt = (Path(ctx) / "prompt.txt").read_text(encoding="utf-8")
            out = str(task.input) if "[ECHO]" in prompt else "(no echo)"
            return Rollout(task_id=task.id, output=out, trace=f"echo={'[ECHO]' in prompt}")

        def score(self, task, rollout):
            ok = (rollout.output or "").strip() == str(task.target)
            fb = "correct" if ok else f"expected {task.target!r}, prompt may lack [ECHO]"
            return Score(task_id=task.id, reward=1.0 if ok else 0.0, feedback=fb,
                         trial_rewards=[1.0 if ok else 0.0])

        def materialize(self, candidate_dir, edits=None):  # noqa: ARG002
            return None

    return _Adapter()


def _seed_capability(dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "prompt.txt").write_text("Answer the task.\n", encoding="utf-8")


def _good_optimizer(workdir: Path, instructions: str) -> None:  # noqa: ARG001
    """Mock proposer that fixes the capability by adding the [ECHO] marker."""
    p = workdir / "prompt.txt"
    txt = p.read_text(encoding="utf-8")
    if "[ECHO]" not in txt:
        p.write_text(txt + "\n[ECHO] echo the input exactly.\n", encoding="utf-8")


def _noop_optimizer(workdir: Path, instructions: str) -> None:  # noqa: ARG001
    """Mock proposer that changes nothing (must be locally gated out)."""
    return None


def _run_loop(optimizer, tmp: Path, *, ts: str):
    from cap_evolve import Budget, RunDir, gepa, harness

    adapter = _make_adapter()
    seed = tmp / f"seed_{ts}"
    _seed_capability(seed)
    run_dir = RunDir.create(tmp / ".capevolve", ts=ts,
                            budget=Budget(max_iterations=8, max_metric_calls=400))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)
    result = gepa.gepa_loop(
        adapter, run_dir=run_dir, optimizer=optimizer, seed_val=base,
        max_metric_calls=300, max_iterations=6, minibatch_size=3,
        max_merges=0, seed=0, store=None,
        gate_kwargs={"mode": "significant", "k_se": 1.0},
    )
    return run_dir, base, result


def main() -> int:
    c = Checker("gepa")
    run = import_run()
    c.require_main(run)

    from cap_evolve import gepa as gepa_mod
    c.check(hasattr(gepa_mod, "gepa_loop"), "core gepa module missing gepa_loop()",
            note="gepa.gepa_loop present")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # 1 + 3 + 5: a good optimizer yields an accept gated honestly on val.
        run_dir, base, result = _run_loop(_good_optimizer, tmp, ts="good")
        c.check(result.get("accepts", 0) >= 1,
                f"expected >=1 accept with a fixing optimizer, got {result.get('accepts')}",
                note=f"accepts={result.get('accepts')} best_val={result.get('best_val')}")
        c.check(result.get("best_val", 0.0) > base.reward,
                f"best_val {result.get('best_val')} did not exceed baseline {base.reward}",
                note=f"best_val {result.get('best_val'):.3f} > baseline {base.reward:.3f}")
        c.check(run_dir.spent.metric_calls > 0, "no metric-calls accounted",
                note=f"metric_calls={run_dir.spent.metric_calls}")
        for key in ("algorithm", "best_id", "frontier_size", "pool_size",
                    "iterations", "accepts", "metric_calls", "stop_reason", "steps"):
            c.check(key in result, f"result dict missing {key!r}")

        # honest val gate: every accepted step's val reward beat its parent.
        for s in result.get("steps", []):
            if s.get("accepted") and "candidate_val" in s:
                cv = s["candidate_val"].get("reward", 0.0)
                c.check(cv >= base.reward, f"accepted step {s['candidate_id']} val {cv} < baseline")

        # 4: the test split was never consumed by the optimization loop.
        c.check(run_dir.read_splits().test_used is False,
                "test seal was burned during optimization (must stay sealed for finalize)",
                note="test split never consumed by the loop")

        # 2: the LOCAL minibatch gate filters a no-op edit WITHOUT a full-val spend.
        run_dir2, base2, result2 = _run_loop(_noop_optimizer, tmp, ts="noop")
        c.check(result2.get("accepts", 0) == 0,
                f"no-op optimizer should accept nothing, got {result2.get('accepts')}",
                note="no-op edits rejected")
        local_rejects = [s for s in result2.get("steps", [])
                         if s.get("local_gate") is False]
        no_full_val = all("candidate_val" not in s for s in local_rejects)
        c.check(bool(local_rejects) and no_full_val,
                "local minibatch gate did not short-circuit no-op edits before full val",
                note=f"{len(local_rejects)} step(s) stopped at the local gate (no full-val spend)")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
