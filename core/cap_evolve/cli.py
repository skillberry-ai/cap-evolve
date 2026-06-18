"""The ``cap-evolve`` CLI — a thin sequencer over the skill ``run.py`` scripts.

``cap-evolve`` does NOT contain pipeline logic; it locates skills (via the registry
manifest) and runs their ``scripts/run.py`` in the order a ``capevolve.yaml`` spec
declares, threading the run dir between them. The honesty guarantees live in
``cap_evolve`` (splits/gate/seal); ``cap-evolve`` just orchestrates.

Subcommands:
    cap-evolve version
    cap-evolve splits  --ids ... [--seed N] [--ratios a,b,c]
    cap-evolve check   [project_dir]
    cap-evolve run     --spec .capevolve/project/capevolve.yaml   (sequences phase skills)

``run`` is intentionally minimal in Phase 0 and grows as phase skills land; it
already resolves the manifest and validates the spec so the wiring is testable.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import __version__
from .check import run_check


def _find_skills_dir() -> Path | None:
    for cand in [
        os.environ.get("CAPEVOLVE_SKILLS_DIR"),
        "./.claude/skills",
        os.path.expanduser("~/.claude/skills"),
        os.path.expanduser("~/.capevolve/skills"),
    ]:
        if cand and Path(cand).is_dir():
            return Path(cand)
    # fall back to the repo's own skills/ if running from source
    here = Path(__file__).resolve()
    for parent in here.parents:
        s = parent / "skills"
        if s.is_dir():
            return s
    return None


def _cmd_version(argv):
    print(json.dumps({"cap-evolve": __version__}))
    return 0


def _cmd_splits(argv):
    from .__main__ import _cmd_splits as f
    return f(argv)


def _cmd_check(argv):
    project = Path(argv[0]) if argv else Path(".capevolve/project")
    rep = run_check(project)
    print(json.dumps(rep.to_dict(), indent=2))
    return 0 if rep.ok else 1


# Old hill-climb skill names → (skill, focus). The three byte-identical clones are
# now one ``hill-climb`` skill parameterized by ``--focus``.
_ALGO_FOCUS_ALIASES = {
    "all-at-once": ("hill-climb", "all"),
    "cyclic": ("hill-climb", "cyclic"),
    "hardest-first": ("hill-climb", "hardest-first"),
}


def _resolve_algorithm(name: str) -> tuple[str, str | None]:
    """Map a spec ``algorithm_skill`` to (skill_name, focus).

    ``hill-climb`` may be given directly (focus defaults to ``all``); the legacy
    names ``all-at-once``/``cyclic``/``hardest-first`` translate to it with the
    right focus. Any other algorithm (e.g. ``gepa`` / ``skillopt``) passes through
    with no focus.
    """
    if name in _ALGO_FOCUS_ALIASES:
        return _ALGO_FOCUS_ALIASES[name]
    if name == "hill-climb":
        return "hill-climb", "all"
    return name, None


def _resolve_skills(skills_dir: Path) -> dict:
    manifest = skills_dir / "_registry" / "manifest.json"
    if not manifest.exists():
        raise FileNotFoundError(
            "no manifest — run install.sh or skills/_registry/build_manifest.py first")
    return json.loads(manifest.read_text()).get("skills", {})


def _cmd_run(argv):
    import argparse
    import subprocess
    from .specfile import read_yaml

    p = argparse.ArgumentParser(prog="cap-evolve run")
    p.add_argument("--spec", default=".capevolve/project/capevolve.yaml")
    p.add_argument("--project", default=".capevolve/project")
    p.add_argument("--skills-dir", default=None)
    p.add_argument("--plan-only", action="store_true", help="print the command plan, don't execute")
    p.add_argument("--run-ts", default=None)
    p.add_argument("--dashboard", choices=("auto", "report-only", "off"), default=None,
                   help="live dashboard: auto (default, launch at run start), report-only, or off")
    p.add_argument("--dashboard-port", type=int, default=None, help="dashboard server port (default 7878)")
    args = p.parse_args(argv)

    skills_dir = Path(args.skills_dir) if args.skills_dir else _find_skills_dir()
    if not skills_dir:
        print(json.dumps({"error": "skills dir not found; set CAPEVOLVE_SKILLS_DIR or --skills-dir"}))
        return 1
    skills = _resolve_skills(skills_dir)
    spec = read_yaml(Path(args.spec).read_text())

    from . import dashboard_launch
    dash_mode = dashboard_launch.resolve_mode(args.dashboard, spec.get("dashboard"))
    dash_port = args.dashboard_port or int(spec.get("dashboard_port") or dashboard_launch.DEFAULT_PORT)

    def skill_run(name: str) -> str:
        s = skills.get(name)
        if not s:
            raise KeyError(f"skill {name!r} not in manifest")
        return str(skills_dir / s["path"] / s["entry"])

    # All steps run in ONE consistent working directory: the dir that contains
    # .capevolve/ (i.e. project's grandparent). Paths are kept relative to it so the
    # run_dir baseline prints ("..capevolve/run_X") resolves identically in every
    # subprocess regardless of where `cap-evolve run` was invoked from.
    proj_abs = Path(args.project).resolve()
    workdir = proj_abs.parent.parent
    project = str(proj_abs.relative_to(workdir))      # ".capevolve/project"
    base = str(proj_abs.parent.relative_to(workdir))  # ".capevolve"
    cap_path = spec.get("capability_path", "seed_capability")
    ratios = f"{spec.get('split_train',0.5)},{spec.get('split_val',0.25)},{spec.get('split_test',0.25)}"

    # Optimizer semantics: ``optimizer_skill`` is the optimizer NAME,
    # resolved by the single ``run-optimizer`` skill against optimizers/registry.yaml
    # (no per-CLI skill dir). Back-compat: an old name like ``claude-code`` is just
    # the registry row of the same name, so old specs keep working.
    optimizer_name = spec["optimizer_skill"]
    opt_cmd = (f"{sys.executable} {skill_run('run-optimizer')} --name {optimizer_name} "
               f"--workdir {{workdir}} --prompt {{prompt}}")
    if spec.get("optimizer_model"):
        opt_cmd += f" --model {spec['optimizer_model']}"

    # Algorithm semantics: the three hill-climb variants are one ``hill-climb``
    # skill selected by ``--focus``. Back-compat: translate the old skill names. An
    # explicit ``algorithm_focus`` in the spec overrides the name-derived default.
    algorithm_name, algorithm_focus = _resolve_algorithm(spec["algorithm_skill"])
    if spec.get("algorithm_focus") and algorithm_name == "hill-climb":
        algorithm_focus = str(spec["algorithm_focus"])
    py = sys.executable

    def run(cmd):
        return subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))

    # The run sequence is built from the manifest + spec (orchestrate validates the
    # needs/provides DAG); it now includes intake + the check gate before baseline.
    sequence = ["intake", "implement-and-check", "baseline", algorithm_name, "finalize", "report"]

    if args.plan_only:
        print(json.dumps({"skills_dir": str(skills_dir), "workdir": str(workdir), "spec": spec,
                          "optimizer": optimizer_name, "optimizer_cmd": opt_cmd,
                          "algorithm": algorithm_name, "focus": algorithm_focus,
                          "gate_mode": spec.get("gate_mode", "auto (paired)"),
                          "budget": {"max_iterations": spec.get("max_iterations", 10),
                                     "stall": spec.get("stall", 0)},
                          "sequence": sequence}, indent=2))
        return 0

    # Hard gate: cap-evolve check must pass before any budget is spent (intake is the
    # user's job before `run`; here we enforce the check half of implement-and-check).
    from .check import run_check as _run_check
    chk = _run_check(proj_abs)
    if not chk.ok:
        print(json.dumps({"step": "implement-and-check", "error": "check failed",
                          "report": chk.to_dict()}))
        return 1

    # 1) baseline (creates the run dir; capture its relative path)
    base_cmd = [py, skill_run("baseline"), "--base", base, "--project", project,
                "--capability", cap_path, "--seed", str(spec.get("split_seed", 0)),
                "--ratios", ratios, "--max-iterations", str(spec.get("max_iterations", 10)),
                "--stall", str(spec.get("stall", 0)), "--n-trials", str(spec.get("num_trials", 1))]
    if spec.get("split_ids_file"):
        base_cmd += ["--split-ids", str(spec["split_ids_file"])]
    if args.run_ts:
        base_cmd += ["--run-ts", args.run_ts]
    proc = run(base_cmd)
    if proc.returncode != 0:
        print(json.dumps({"step": "baseline", "error": proc.stderr[-1500:]}))
        return 1
    run_dir = json.loads(proc.stdout)["run_dir"]

    # Auto-start the live dashboard now (the run dir exists) so the whole
    # evolution is watchable. Best-effort: never blocks or fails the run.
    if dash_mode == "auto":
        # Absolute base: the dashboard subprocess inherits THIS process's cwd
        # (not workdir), so a relative ".capevolve" would resolve wrongly when
        # `cap-evolve run` is invoked from outside workdir.
        status = dashboard_launch.maybe_launch(
            proj_abs.parent, mode=dash_mode, port=dash_port, open_browser=True)
        print(json.dumps(status))

    # 2) algorithm (hill-climb variants select their schedule via --focus)
    alg_cmd = [py, skill_run(algorithm_name), "--run-dir", run_dir, "--project", project,
               "--optimizer", opt_cmd, "--max-iterations", str(spec.get("max_iterations", 10)),
               "--n-trials", str(spec.get("num_trials", 1)),
               "--gate-mode", str(spec.get("gate_mode", "auto")),
               "--k-se", str(spec.get("gate_k_se", 1.0)),
               "--store", str(spec.get("store", "git"))]
    if algorithm_focus is not None:
        alg_cmd += ["--focus", algorithm_focus]
    if spec.get("store_commit_cmd"):
        alg_cmd += ["--store-commit-cmd", str(spec["store_commit_cmd"])]
    # Algorithm-specific knobs without hardcoding per-algorithm: a spec may set
    # `algorithm_args` (string) to pass extra flags straight through to the
    # algorithm run.py — e.g. "--epochs 6 --lr-schedule cosine" for skillopt,
    # "--max-metric-calls 200 --minibatch-size 5" for gepa.
    if spec.get("algorithm_args"):
        import shlex as _shlex
        alg_cmd += _shlex.split(str(spec["algorithm_args"]))
    proc = run(alg_cmd)
    if proc.returncode != 0:
        print(json.dumps({"step": "algorithm", "error": proc.stderr[-1500:]}))
        return 1

    # 3) finalize  4) report
    last = proc.stdout
    report_extra = ["--dashboard-mode", dash_mode, "--dashboard-port", str(dash_port)]
    for step, extra in (("finalize", ["--n-trials", str(spec.get("num_trials", 1))]),
                        ("report", report_extra)):
        cmd = [py, skill_run(step), "--run-dir", run_dir]
        if step == "finalize":
            cmd += ["--project", project]
        cmd += extra
        proc = run(cmd)
        if proc.returncode != 0:
            print(json.dumps({"step": step, "error": proc.stderr[-1500:]}))
            return 1
        last = proc.stdout

    print(last)
    return 0


def _cmd_dashboard(argv):
    """Launch (or focus) the live dashboard server over a base dir of runs."""
    import argparse
    from . import dashboard_launch

    p = argparse.ArgumentParser(prog="cap-evolve dashboard")
    p.add_argument("--base", default=".capevolve", help="dir containing run_* dirs")
    p.add_argument("--port", type=int, default=dashboard_launch.DEFAULT_PORT)
    p.add_argument("--no-open", action="store_true", help="don't open a browser")
    args = p.parse_args(argv)

    status = dashboard_launch.maybe_launch(
        args.base, mode="auto", port=args.port, open_browser=not args.no_open
    )
    print(json.dumps(status))
    return 0 if status.get("dashboard") not in (None, "error", "skipped") else 1


COMMANDS = {
    "version": _cmd_version,
    "splits": _cmd_splits,
    "check": _cmd_check,
    "run": _cmd_run,
    "dashboard": _cmd_dashboard,
}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: cap-evolve {version|splits|check|run|dashboard} [args]", file=sys.stderr)
        return 0 if argv else 2
    fn = COMMANDS.get(argv[0])
    if fn is None:
        print(f"unknown command: {argv[0]}", file=sys.stderr)
        return 2
    return fn(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
