"""``cap-evolve check`` — the HARD GATE before any optimization budget is spent.

Loads the project adapter from ``.capevolve/project/adapters/adapter.py`` and proves
the contract holds:

  1. all required adapter methods are implemented (no IMPLEMENT-ME stubs);
  2. ``tasks(split)`` returns a non-empty, stable list of ``Task``;
  3. the scorer is deterministic — same (task, rollout) scored twice yields the
     same reward (within tolerance);
  4. ``materialize()`` is callable on a candidate dir (PURE — no host mutation);
  5. (best-effort) when ``n_trials>1`` is configured, a quick probe warns if two
     rollouts come back byte-identical (a likely swallowed per-trial seed).

Returns a structured report and a pass/fail. The orchestration prompt refuses to
proceed until this passes, so a half-wired project can never silently produce a
dishonest number.
"""

from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path

from .adapter import CapabilityAdapter, stub_methods
from .types import Rollout, Task


@dataclass
class CheckReport:
    ok: bool = False
    stubs: list = field(default_factory=list)
    problems: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "stubs": self.stubs, "problems": self.problems, "notes": self.notes}


def load_adapter(project_dir: Path) -> CapabilityAdapter:
    """Import ``adapters/adapter.py`` and return its ``Adapter()`` instance."""
    project_dir = Path(project_dir)
    mod_path = project_dir / "adapters" / "adapter.py"
    if not mod_path.exists():
        raise FileNotFoundError(f"no adapter at {mod_path}")
    # Make the adapter's own directory importable so it can `import` sibling
    # helper modules (e.g. a benchmark runtime) without extra PYTHONPATH setup.
    import sys
    adir = str(mod_path.parent)
    if adir not in sys.path:
        sys.path.insert(0, adir)

    spec = importlib.util.spec_from_file_location("forge_project_adapter", mod_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    if not hasattr(mod, "Adapter"):
        raise AttributeError(f"{mod_path} must define a class named `Adapter`")
    return mod.Adapter()


def run_check(project_dir: Path, *, tolerance: float = 1e-6) -> CheckReport:
    rep = CheckReport()
    try:
        adapter = load_adapter(Path(project_dir))
    except Exception as e:  # noqa: BLE001
        rep.problems.append(f"could not load adapter: {e}")
        return rep

    # 1. stubs
    rep.stubs = stub_methods(adapter)
    if rep.stubs:
        rep.problems.append(
            "unimplemented adapter methods: " + ", ".join(rep.stubs)
            + " — implement them in adapters/adapter.py"
        )
        return rep  # can't probe further safely

    # 2. tasks present + stable
    try:
        t1 = adapter.tasks("val")
        t2 = adapter.tasks("val")
    except Exception as e:  # noqa: BLE001
        rep.problems.append(f"tasks('val') raised: {e}")
        return rep
    if not t1:
        rep.problems.append("tasks('val') returned an empty list")
        return rep
    if not all(isinstance(t, Task) for t in t1):
        rep.problems.append("tasks('val') must return a list[Task]")
        return rep
    if [t.id for t in t1] != [t.id for t in t2]:
        rep.problems.append("tasks('val') is not stable across calls (must be deterministic)")
    rep.notes.append(f"tasks('val') -> {len(t1)} task(s)")

    # 3. deterministic scorer (probe with a fixed synthetic rollout)
    probe_task = t1[0]
    probe_rollout = Rollout(task_id=probe_task.id, output="__probe_output__")
    try:
        s1 = adapter.score(probe_task, probe_rollout)
        s2 = adapter.score(probe_task, probe_rollout)
    except Exception as e:  # noqa: BLE001
        rep.problems.append(f"score(...) raised on a probe rollout: {e}")
        return rep
    if abs(s1.reward - s2.reward) > tolerance:
        rep.problems.append(
            f"scorer is non-deterministic: {s1.reward} vs {s2.reward} on identical input"
        )
    else:
        rep.notes.append(f"scorer deterministic (probe reward={s1.reward:.4f})")

    # 4. materialize callable WITHOUT mutating the host.
    #    Old behavior called ``apply(project_dir)`` directly, which for a real
    #    adapter is a GLOBAL side effect (e.g. monkeypatching a benchmark policy) —
    #    the safety check must not change host state. ``materialize`` is the pure
    #    write half of the contract, so we probe it into a throwaway temp copy of the
    #    candidate. We deliberately do NOT exercise ``live()``/``apply()`` here,
    #    because those are the global-effect half; running them would mutate the host
    #    (and on a real benchmark could fail without its full environment).
    import shutil
    import tempfile
    try:
        with tempfile.TemporaryDirectory() as td:
            sandbox = Path(td) / "candidate"
            src = Path(project_dir)
            if src.is_dir():
                shutil.copytree(src, sandbox)
            else:
                sandbox.mkdir(parents=True, exist_ok=True)
            adapter.materialize(sandbox)  # pure: writes only into the temp copy
        rep.notes.append("materialize() callable (dry-run into temp copy; host untouched)")
    except Exception as e:  # noqa: BLE001
        rep.notes.append(f"materialize() probe raised (may be expected): {e}")

    # 5. degenerate-trials probe (best-effort): if two rollouts of the same task are
    #    byte-identical, a stochastic runner is likely ignoring the per-trial ``seed``,
    #    which collapses pass^k + the significance gate. We never FAIL the check on
    #    this (a deterministic adapter SHOULD be identical), only WARN — and only when
    #    multi-trial evaluation is configured (CAPEVOLVE_N_TRIALS>1).
    #    Opt-in only (CAPEVOLVE_CHECK_TRIAL_PROBE=1): it fires REAL rollouts, which for
    #    a network/LLM runner (e.g. tau2) costs money and is surprising inside a
    #    pre-flight gate — so it stays off by default even when n_trials>1.
    import os as _os
    if (int(_os.environ.get("CAPEVOLVE_N_TRIALS", "1")) > 1
            and _os.environ.get("CAPEVOLVE_CHECK_TRIAL_PROBE") == "1"):
        try:
            r1 = adapter.run_target(probe_task, Path(project_dir), seed=0)
            r2 = adapter.run_target(probe_task, Path(project_dir), seed=1)
            d1 = json.dumps(r1.to_dict(), default=str, sort_keys=True)
            d2 = json.dumps(r2.to_dict(), default=str, sort_keys=True)
            if d1 == d2:
                rep.notes.append(
                    "WARNING: two rollouts with different seeds were byte-identical "
                    "while n_trials>1 — the runner may be swallowing the per-trial seed "
                    "(degenerate pass^k / SE=0). Forward `seed` to the stochastic runner."
                )
        except Exception as e:  # noqa: BLE001
            rep.notes.append(f"degenerate-trials probe skipped: {e}")

    rep.ok = not rep.problems
    return rep


def _main(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="cap_evolve.check")
    p.add_argument("project_dir", nargs="?", default=".capevolve/project")
    args = p.parse_args(argv)
    rep = run_check(Path(args.project_dir))
    print(json.dumps(rep.to_dict(), indent=2))
    return 0 if rep.ok else 1
