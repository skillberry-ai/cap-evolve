"""The ``cap-evolve`` CLI — a thin sequencer over the skill ``run.py`` scripts.

``cap-evolve`` does NOT contain pipeline logic; it locates skills (via the registry
manifest) and runs their ``scripts/run.py`` in the order a ``capevolve.yaml`` spec
declares, threading the run dir between them. The honesty guarantees live in
``cap_evolve`` (splits/gate/seal); ``cap-evolve`` just orchestrates.

The subcommand list is ``COMMANDS`` and nothing else — `cap-evolve --help` renders it
from there plus each handler's docstring, and each handler owns its own ``--help``.
There is deliberately no second copy of the list here or in ``main()``: five parallel
branches adding subcommands all conflicted on that literal usage string (#137).

``intake``/``baseline``/``finalize``/``report`` are phase SKILLS, not subcommands —
run their ``scripts/run.py`` directly (``cap-evolve <phase>`` says so and exits 2, with
that script's real required flags — see ``_PHASE_SCRIPTS``).

Exit codes: 0 success (and ``--help``/``--version``), 1 a reported failure (a JSON error
object on stdout), 2 misuse — no args, unknown command, or an argparse error.

MERGE NOTE for #116/#118 (``cap-evolve tail``): the exit-code prose that used to live in
this docstring's literal subcommand list must be re-homed into ``_cmd_tail``'s own
docstring/epilog when that branch lands, not dropped. Verbatim, so it is not lost:

    exit 0 = run finished OR still working — do NOT branch on 0 to mean "finished";
    2 = not a possible run dir; 3 = --idle-timeout elapsed with no events and nothing
    provably dead; 4 = STALLED, 5 = CRASHED.

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


def _parser(cmd: str, description: str, examples: str):
    """An argparse parser wired for `cap-evolve <cmd> --help` with examples.

    Every subcommand builds its parser through here so `--help` is uniform and can
    never drift from the top-level listing (which reads the same docstrings).
    """
    import argparse
    return argparse.ArgumentParser(
        prog=f"cap-evolve {cmd}", description=description,
        epilog="examples:\n" + examples,
        formatter_class=argparse.RawDescriptionHelpFormatter)


def _cmd_version(argv):
    """Print the installed cap-evolve version as JSON."""
    _parser("version", _cmd_version.__doc__, "  cap-evolve version").parse_args(argv)
    print(json.dumps({"cap-evolve": __version__}))
    return 0


def _cmd_splits(argv):
    """Compute the seeded train/val/test split for a set of task ids."""
    from .__main__ import _cmd_splits as f
    return f(argv, prog="cap-evolve splits")


def _cmd_check(argv):
    """Verify a project's adapter is fully implemented and deterministic."""
    p = _parser("check", _cmd_check.__doc__,
                "  cap-evolve check\n  cap-evolve check path/to/.capevolve/project")
    p.add_argument("project", nargs="?", default=".capevolve/project",
                   help="project dir (default: .capevolve/project)")
    args = p.parse_args(argv)
    rep = run_check(Path(args.project))
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
    """Sequence the whole optimization run: baseline → algorithm → finalize → report.

    Prints a single JSON object on stdout (the final report); human progress goes to
    stderr, so `cap-evolve run > out.json` stays machine-readable.
    """
    import subprocess
    from .specfile import read_yaml

    p = _parser("run", _cmd_run.__doc__,
                "  cap-evolve run --spec .capevolve/project/capevolve.yaml\n"
                "  cap-evolve run --plan-only          # show the plan, spend nothing\n"
                "  cap-evolve run --dry-run            # pre-run cost estimate\n"
                "  cap-evolve run --resume --max-iterations 20")
    p.add_argument("--spec", default=".capevolve/project/capevolve.yaml",
                   help="run spec YAML (default: .capevolve/project/capevolve.yaml)")
    p.add_argument("--project", default=".capevolve/project",
                   help="project dir (default: .capevolve/project)")
    p.add_argument("--skills-dir", default=None,
                   help="skills dir (default: $CAPEVOLVE_SKILLS_DIR or auto-discovered)")
    p.add_argument("--plan-only", action="store_true", help="print the command plan, don't execute")
    p.add_argument("--dry-run", action="store_true",
                   help="print a pre-run cost estimate (call counts + $ range) and exit")
    p.add_argument("--run-ts", default=None,
                   help="run timestamp to create/reopen (default: now, or latest with --resume)")
    p.add_argument("--resume", action="store_true",
                   help="continue an interrupted run from its last completed state instead "
                        "of starting fresh: reopens the run dir (--run-ts, else the latest "
                        "under the base), skips the baseline if done, and picks the loop up "
                        "at iteration N+1 from the current best. Explicit budget flags extend it.")
    p.add_argument("--reuse-baseline", default=None,
                   help="prior run dir: reuse its baseline (split/baseline/seed/val-rollouts) "
                        "and skip the baseline eval")
    # Budget overrides — when set, take precedence over the spec's values. Defaults
    # are None so "not passed" is distinguishable from an explicit 0 (= unlimited).
    p.add_argument("--max-iterations", type=int, default=None,
                   help="override the spec's iteration cap (0 = unlimited)")
    p.add_argument("--max-metric-calls", type=int, default=None,
                   help="override the spec's metric-call cap (0 = unlimited)")
    p.add_argument("--max-usd", type=float, default=None,
                   help="override the spec's cumulative runner $ cap (0 = unlimited)")
    p.add_argument("--max-optimizer-usd", type=float, default=None,
                   help="override the spec's cumulative optimizer $ cap (0 = unlimited)")
    p.add_argument("--stall", type=int, default=None,
                   help="stop after N iterations with no accepted improvement (0 = off)")
    p.add_argument("--optimizer-max-turns", type=int, default=None,
                   help="per-iteration cap passed to the optimizer agent CLI (e.g. claude --max-turns)")
    p.add_argument("--dashboard", choices=("auto", "report-only", "off"), default=None,
                   help="live dashboard: auto (default, launch at run start), report-only, or off")
    p.add_argument("--dashboard-port", type=int, default=None, help="dashboard server port (default 7878)")
    args = p.parse_args(argv)
    # Validation before anything is spent: a negative budget is a typo, not "unlimited"
    # (0 means unlimited), and silently accepting it would make the cap never bind.
    for flag in ("max_iterations", "max_metric_calls", "max_usd", "max_optimizer_usd",
                 "stall", "optimizer_max_turns"):
        v = getattr(args, flag)
        if v is not None and v < 0:
            p.error(f"--{flag.replace('_', '-')} must be >= 0 (0 = unlimited), got {v}")
    # --dashboard-port is NOT a "0 = unlimited" flag: it's a TCP port, so it wants a
    # range check. Without it, a negative value reached `bind()` as an uncaught
    # OverflowError — and because maybe_launch() runs before the --plan-only early
    # return, even a spend-nothing preview crashed. Validating here (before any launch)
    # keeps --plan-only usable for a bad-port invocation. #137 review N2.
    if args.dashboard_port is not None and not 1 <= args.dashboard_port <= 65535:
        p.error(f"--dashboard-port must be 1-65535, got {args.dashboard_port}")

    skills_dir = Path(args.skills_dir) if args.skills_dir else _find_skills_dir()
    if not skills_dir:
        print(json.dumps({"error": "skills dir not found; set CAPEVOLVE_SKILLS_DIR or --skills-dir"}))
        return 1
    skills = _resolve_skills(skills_dir)
    spec = read_yaml(Path(args.spec).read_text())

    # CLI budget flags override the spec (None = "not passed", leave spec value).
    for flag, key in (("max_iterations", "max_iterations"), ("max_metric_calls", "max_metric_calls"),
                      ("max_usd", "max_usd"), ("max_optimizer_usd", "max_optimizer_usd"),
                      ("stall", "stall"), ("optimizer_max_turns", "optimizer_max_turns")):
        v = getattr(args, flag)
        if v is not None:
            spec[key] = v
    if args.reuse_baseline is not None:
        spec["reuse_baseline"] = args.reuse_baseline

    if args.dry_run:
        print(json.dumps(_estimate_core(spec, Path(args.project)), indent=2))
        return 0

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

    # Start the live dashboard at the very TOP of the run — before the check gate and
    # the phase sequence — so it is up first and the run is watchable from the start
    # (the server scans the base dir and shows the run as soon as baseline creates it).
    # Best-effort: never blocks or fails the run. (Absolute base: the subprocess
    # inherits THIS process's cwd, not workdir.)
    if dash_mode == "auto":
        status = dashboard_launch.maybe_launch(
            proj_abs.parent, mode=dash_mode, port=dash_port, open_browser=True)
        # STDERR: stdout is the machine-readable contract — exactly ONE JSON object (the
        # final report). This progress line used to go to stdout, so `cap-evolve run |
        # json.loads` raised "Extra data" whenever the dashboard was launched or skipped.
        print(json.dumps(status), file=sys.stderr)
    cap_path = spec.get("capability_path", "seed_capability")
    ratios = f"{spec.get('split_train',0.5)},{spec.get('split_val',0.25)},{spec.get('split_test',0.25)}"

    # Optimizer semantics: ``optimizer_skill`` is the optimizer NAME,
    # resolved by the single ``run-optimizer`` skill against optimizers/registry.yaml
    # (no per-CLI skill dir). Back-compat: an old name like ``claude-code`` is just
    # the registry row of the same name, so old specs keep working.
    optimizer_name = spec["optimizer_skill"]
    # --json switches on run-optimizer's cost capture (parses total_cost_usd from the
    # agent CLI's structured output) so optimizer spend counts against the budget and
    # shows in the dashboard. Rows without a json_flag (mock/offline) ignore it.
    opt_cmd = (f"{sys.executable} {skill_run('run-optimizer')} --name {optimizer_name} "
               f"--json --workdir {{workdir}} --prompt {{prompt}}")
    if spec.get("optimizer_model"):
        opt_cmd += f" --model {spec['optimizer_model']}"
    # Per-iteration optimizer cap: run-optimizer maps --budget to the registry row's
    # budget_flag_template (e.g. claude-code → --max-turns N), bounding each step's cost.
    if spec.get("optimizer_max_turns"):
        opt_cmd += f" --budget {int(spec['optimizer_max_turns'])}"
    # Per-iteration optimizer USD cap: run-optimizer maps --usd-budget to the row's
    # usd_budget_flag (e.g. claude-code → --max-budget-usd N), enforced by the optimizer
    # CLI itself. Rows without one (e.g. ibm-bob) ignore it — bound those via
    # optimizer_max_turns and/or the cumulative max_optimizer_usd instead.
    if spec.get("optimizer_usd_per_iter"):
        opt_cmd += f" --usd-budget {float(spec['optimizer_usd_per_iter'])}"

    # Algorithm semantics: the three hill-climb variants are one ``hill-climb``
    # skill selected by ``--focus``. Back-compat: translate the old skill names. An
    # explicit ``algorithm_focus`` in the spec overrides the name-derived default.
    algorithm_name, algorithm_focus = _resolve_algorithm(spec["algorithm_skill"])
    if spec.get("algorithm_focus") and algorithm_name == "hill-climb":
        algorithm_focus = str(spec["algorithm_focus"])
    # orchestration_mode: "deterministic" (cap-evolve sequences the loop, below) vs
    # "agent" (the coding agent drives the loop; cap-evolve run only does setup+baseline
    # then hands off — see the short-circuit after baseline).
    orchestration_mode = str(spec.get("orchestration_mode", "deterministic")).strip() or "deterministic"
    py = sys.executable

    def run(cmd):
        return subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))

    # The run sequence is built from the manifest + spec (orchestrate validates the
    # needs/provides DAG); it now includes intake + the check gate before baseline.
    # In agent mode `cap-evolve run` stops after baseline and hands the loop to the
    # coding agent, so the plan reflects only what this process actually runs.
    if orchestration_mode == "agent":
        sequence = ["intake", "implement-and-check", "baseline",
                    "<handoff: agent drives the loop, then `cap-evolve finalize`>"]
    else:
        sequence = ["intake", "implement-and-check", "baseline", algorithm_name, "finalize", "report"]

    if args.plan_only:
        print(json.dumps({"skills_dir": str(skills_dir), "workdir": str(workdir), "spec": spec,
                          "optimizer": optimizer_name, "optimizer_cmd": opt_cmd,
                          "algorithm": algorithm_name, "focus": algorithm_focus,
                          "target_model": spec.get("target_model", ""),
                          "orchestration_mode": orchestration_mode,
                          "gate_mode": spec.get("gate_mode", "auto (paired)"),
                          "budget": {"max_iterations": spec.get("max_iterations", 10),
                                     "stall": spec.get("stall", 0),
                                     "max_metric_calls": spec.get("max_metric_calls", 0),
                                     "max_usd": spec.get("max_usd", 0.0),
                                     "max_optimizer_usd": spec.get("max_optimizer_usd", 0.0),
                                     "optimizer_max_turns": spec.get("optimizer_max_turns", 0)},
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

    # Resume: reopen an existing run instead of creating a fresh one. Resolve which run
    # to reopen — the explicit --run-ts, else the latest run_* under the base — and feed
    # its ts to baseline so RunDir.create(exist_ok=True) reopens it in place.
    from .rundir import RunDir as _RunDir
    resume_ts = args.run_ts
    if args.resume and not resume_ts:
        try:
            latest = _RunDir.latest(proj_abs.parent)
            resume_ts = latest.root.name[len("run_"):]
        except FileNotFoundError:
            print(json.dumps({"step": "resume", "error": (
                f"--resume: no run_* found under {proj_abs.parent}; pass --run-ts to name one")}))
            return 1

    # 1) baseline (creates the run dir; capture its relative path)
    base_cmd = [py, skill_run("baseline"), "--base", base, "--project", project,
                "--capability", cap_path, "--seed", str(spec.get("split_seed", 0)),
                "--ratios", ratios, "--max-iterations", str(spec.get("max_iterations", 10)),
                "--stall", str(spec.get("stall", 0)), "--n-trials", str(spec.get("num_trials", 1)),
                "--max-metric-calls", str(spec.get("max_metric_calls", 0)),
                "--max-usd", str(spec.get("max_usd", 0.0)),
                "--max-optimizer-usd", str(spec.get("max_optimizer_usd", 0.0))]
    if spec.get("split_ids_file"):
        base_cmd += ["--split-ids", str(spec["split_ids_file"])]
    # reuse_baseline: copy a prior run's split/baseline/seed/val-rollouts and skip the
    # baseline eval (algorithm starts at iter 1 on the reused baseline).
    if spec.get("reuse_baseline"):
        base_cmd += ["--reuse-baseline", str(spec["reuse_baseline"])]
    if resume_ts:
        base_cmd += ["--run-ts", resume_ts]
    if args.resume:
        base_cmd += ["--resume"]
    proc = run(base_cmd)
    if proc.returncode != 0:
        print(json.dumps({"step": "baseline", "error": proc.stderr[-1500:]}))
        return 1
    run_dir = json.loads(proc.stdout)["run_dir"]

    # Resume: explicit budget flags EXTEND the reopened run (e.g. bump max_iterations to
    # keep climbing past the original cap). Without an override the frozen budget stands.
    if args.resume:
        overrides = {k: getattr(args, k) for k in
                     ("max_iterations", "max_metric_calls", "max_usd", "max_optimizer_usd", "stall")
                     if getattr(args, k) is not None}
        if overrides:
            _RunDir.open(workdir / run_dir).update_budget(**overrides)

    # Record the intake phase's spend + summary into the run, if the intake phase
    # wrote <project>/intake.json. Best-effort: a missing/malformed file is ignored so
    # it never breaks the run. (run_dir is workdir-relative; resolve under workdir.)
    try:
        intake_path = proj_abs / "intake.json"
        if intake_path.exists():
            data = json.loads(intake_path.read_text(encoding="utf-8")) or {}
            from .rundir import RunDir as _RunDir
            rd = _RunDir.open(workdir / run_dir)
            usd = float(data.get("usd") or 0.0)
            tokens = int(data.get("tokens") or 0)
            seconds = float(data.get("seconds") or 0.0)
            rd.update_spent(intake_usd=usd, intake_tokens=tokens, intake_seconds=seconds)
            rd.log_event("intake", usd=usd, seconds=seconds, tokens=tokens,
                         output_summary=str(data.get("output_summary") or ""),
                         implemented=list(data.get("implemented") or []))
    except Exception:  # noqa: BLE001 — intake tracking is best-effort
        pass

    # Agent mode: the coding agent drives the optimization loop itself (reading the
    # algorithm's "Agent-mode loop"), writing run-dir artifacts via cap-evolve
    # primitives, and sealing with `cap-evolve finalize`. cap-evolve run does
    # setup+baseline, then hands off here — no algorithm subprocess, no auto-finalize.
    if orchestration_mode == "agent":
        print(json.dumps({"mode": "agent", "run_dir": run_dir, "algorithm": algorithm_name,
                          "stop_condition": str(spec.get("stop_condition", "")),
                          "next": "drive via the orchestrate Agent-mode loop; "
                                  "seal with `cap-evolve finalize`"}))
        return 0

    # 2) algorithm (hill-climb variants select their schedule via --focus)
    alg_cmd = [py, skill_run(algorithm_name), "--run-dir", run_dir, "--project", project,
               "--optimizer", opt_cmd, "--max-iterations", str(spec.get("max_iterations", 10)),
               "--n-trials", str(spec.get("num_trials", 1)),
               "--gate-mode", str(spec.get("gate_mode", "auto")),
               "--k-se", str(spec.get("gate_k_se", 1.0)),
               "--store", str(spec.get("store", "git"))]
    # Resume: every deterministic algorithm accepts --resume (continue from the current
    # best in the run dir instead of re-reading baseline.json). agent mode already
    # short-circuited above, so we never reach here for it.
    if args.resume:
        alg_cmd += ["--resume"]
    if algorithm_focus is not None:
        alg_cmd += ["--focus", algorithm_focus]
    # Surface the selected capability skills to the optimizer prompt so it knows the
    # allowed edit space (e.g. tools → may add composite tools). hill-climb consumes
    # --capabilities; algorithms without the flag ignore the extra arg via argparse error,
    # so only pass it to those that accept it.
    caps = spec.get("capabilities") or []
    if isinstance(caps, str):
        caps = [c.strip() for c in caps.split(",") if c.strip()]
    if caps and algorithm_name == "hill-climb":
        alg_cmd += ["--capabilities", ",".join(str(c) for c in caps)]
    # Thread the resolved optimizer NAME so the harness can copy that optimizer's
    # features reference (parallel-subagent capabilities etc.) into each iteration's
    # workdir. Only hill-climb accepts the flag; other algorithms ignore it.
    if algorithm_name == "hill-climb":
        alg_cmd += ["--optimizer-name", str(optimizer_name)]
    # Optimizer-instructions template (intake-authored, per benchmark) + benchmark repo
    # as read-only optimizer context. Both are resolved project-relative if not absolute.
    # The instructions file defaults to the scaffolded project/optimizer/INSTRUCTIONS.md.
    if algorithm_name == "hill-climb":
        instr = spec.get("optimizer_instructions_file") or "optimizer/INSTRUCTIONS.md"
        instr_p = Path(instr)
        if not instr_p.is_absolute() and not instr_p.exists():
            instr_p = Path(project) / instr
        if instr_p.exists():
            alg_cmd += ["--instructions-file", str(instr_p)]
        repo = spec.get("runner_repo_path")
        if repo:
            repo_p = Path(str(repo))
            if not repo_p.is_absolute() and not repo_p.exists():
                repo_p = Path(project) / str(repo)
            alg_cmd += ["--bench-repo", str(repo_p)]
        # Supporting source files (data models / types the tools import) copied verbatim
        # into the optimizer's ./guidance/sources/ so it can write correct code. Resolved
        # project-relative by the harness; we pass them through as given.
        csrc = spec.get("capability_sources") or []
        if isinstance(csrc, str):
            csrc = [c.strip() for c in csrc.split(",") if c.strip()]
        if csrc:
            alg_cmd += ["--capability-sources", ",".join(str(c) for c in csrc)]
        # Consuming/runtime LLM the capabilities are optimized FOR (distinct from the
        # optimizer model). A model id or a tier keyword; steers the optimizer prompt.
        if spec.get("target_model"):
            alg_cmd += ["--target-model", str(spec["target_model"])]
        tpf = spec.get("target_profile_file")
        if tpf:
            tpf_p = Path(str(tpf))
            if not tpf_p.is_absolute() and not tpf_p.exists():
                tpf_p = Path(project) / str(tpf)
            alg_cmd += ["--target-profile-file", str(tpf_p)]
    # gepa treats metric-calls as its PRIMARY budget; forward it explicitly (hill-climb
    # has no such flag and enforces the same cap via run_dir.budget_exhausted()).
    if algorithm_name == "gepa" and spec.get("max_metric_calls"):
        alg_cmd += ["--max-metric-calls", str(spec["max_metric_calls"])]
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
    # Resume seal guard: if a prior finalize already burned the test seal, re-running
    # finalize would raise TestSealError. Skip it and just regenerate the report so the
    # honest test number stays scored exactly once.
    steps = [("finalize", ["--n-trials", str(spec.get("num_trials", 1))]), ("report", report_extra)]
    if args.resume:
        try:
            if _RunDir.open(workdir / run_dir).read_splits().test_used:
                steps = [("report", report_extra)]
        except (FileNotFoundError, KeyError):
            pass
    for step, extra in steps:
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
    from . import dashboard_launch

    p = _parser("dashboard", _cmd_dashboard.__doc__,
                "  cap-evolve dashboard\n"
                "  cap-evolve dashboard --base .capevolve --port 7879 --no-open")
    p.add_argument("--base", default=".capevolve", help="dir containing run_* dirs")
    p.add_argument("--port", type=int, default=dashboard_launch.DEFAULT_PORT,
                   help=f"server port (default: {dashboard_launch.DEFAULT_PORT})")
    p.add_argument("--no-open", action="store_true", help="don't open a browser")
    args = p.parse_args(argv)

    status = dashboard_launch.maybe_launch(
        args.base, mode="auto", port=args.port, open_browser=not args.no_open
    )
    print(json.dumps(status))
    return 0 if status.get("dashboard") not in (None, "error", "skipped") else 1


def _val_size(spec: dict, project: Path) -> int | None:
    """Number of val tasks the run will score each iteration (best-effort).

    Prefers an explicit split-ids file; otherwise loads the adapter and applies the
    spec's seed/ratios via the same ``make_splits`` the run uses. Returns ``None`` if
    the task set can't be resolved (e.g. adapter deps missing) — the estimate then
    reports the formula with an unknown val size instead of failing.
    """
    ids_file = spec.get("split_ids_file")
    if ids_file:
        # Resolve as given (absolute/cwd-relative) else relative to the project dir,
        # matching how baseline resolves it — so the preview reflects the real split.
        p = Path(ids_file)
        if not p.exists():
            cand = Path(project) / ids_file
            if cand.exists():
                p = cand
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                return len(d.get("val") or [])
            except Exception:  # noqa: BLE001
                pass
    try:
        from .check import load_adapter
        from .splits import make_splits
        adapter = load_adapter(project)
        ratios = (float(spec.get("split_train", 0.5)), float(spec.get("split_val", 0.25)),
                  float(spec.get("split_test", 0.25)))
        sp = make_splits([t.id for t in adapter.tasks("all")],
                         seed=int(spec.get("split_seed", 0)), ratios=ratios)
        return len(sp.val)
    except Exception:  # noqa: BLE001
        return None


def _calibrate(project: Path) -> dict | None:
    """Observed $/metric-call and $/optimizer-call from prior runs' actual spend.

    The most accurate source: the agent CLI's own reported ``total_cost_usd`` summed
    in each ``run_*/state.json``. Returns ``None`` if no priced runs exist yet.
    """
    base = project.parent  # .capevolve/
    runs = sorted(base.glob("run_*")) if base.is_dir() else []
    tot_mc = tot_runner = tot_iters = tot_opt = 0.0
    for r in runs:
        sj = r / "state.json"
        if not sj.exists():
            continue
        try:
            sp = (json.loads(sj.read_text(encoding="utf-8")).get("spent")) or {}
        except Exception:  # noqa: BLE001
            continue
        tot_mc += float(sp.get("metric_calls") or 0)
        tot_runner += float(sp.get("usd") or 0.0)
        tot_iters += float(sp.get("iterations") or 0)
        tot_opt += float(sp.get("optimizer_usd") or 0.0)
    out: dict = {}
    if tot_mc > 0 and tot_runner > 0:
        out["usd_per_metric_call"] = tot_runner / tot_mc
    if tot_iters > 0 and tot_opt > 0:
        out["usd_per_optimizer_call"] = tot_opt / tot_iters
    return out or None


def _estimate_core(spec: dict, project: Path, price_in: float | None = None,
                   price_out: float | None = None) -> dict:
    """Pre-run cost estimate: call counts + a $ range (most-accurate source first)."""
    from . import pricing as _pricing

    val = _val_size(spec, project)
    trials = int(spec.get("num_trials", 1) or 1)
    iters = int(spec.get("max_iterations", 10) or 10)
    metric_calls = (val * trials * iters) if val is not None else None
    cap = int(spec.get("max_metric_calls", 0) or 0)
    if metric_calls is not None and cap:
        metric_calls = min(metric_calls, cap)
    opt_calls = iters
    opt_model = spec.get("optimizer_model")
    run_model = spec.get("runner_model") or spec.get("model")

    out: dict = {
        "spec_summary": {"val_tasks": val, "num_trials": trials, "max_iterations": iters,
                         "optimizer_model": opt_model, "runner_model": run_model},
        "calls": {"metric_calls": metric_calls, "optimizer_calls": opt_calls},
        "budget": {k: spec.get(k) for k in ("max_usd", "max_optimizer_usd", "max_metric_calls")},
        "dominant_cost_knob": "max_iterations (× val × trials drives runner calls)",
    }

    # 1) calibrate from real runs (the agent CLI's own reported cost).
    cal = _calibrate(project)
    runner_usd = opt_usd = None
    source = None
    if cal:
        source = "calibrated from prior runs"
        if metric_calls is not None and "usd_per_metric_call" in cal:
            runner_usd = metric_calls * cal["usd_per_metric_call"]
        if "usd_per_optimizer_call" in cal:
            opt_usd = opt_calls * cal["usd_per_optimizer_call"]
        out["calibration"] = {k: round(v, 6) for k, v in cal.items()}
    # 2) user-supplied $/MTok (flags), applied via assumed tokens/call.
    if runner_usd is None and price_in is not None and price_out is not None:
        source = "user-supplied $/MTok"
        rt = _pricing.ASSUMED_TOKENS["runner"]; ot = _pricing.ASSUMED_TOKENS["optimizer"]
        per_run = (rt[0] * price_in + rt[1] * price_out) / 1e6
        per_opt = (ot[0] * price_in + ot[1] * price_out) / 1e6
        runner_usd = metric_calls * per_run if metric_calls is not None else None
        opt_usd = opt_calls * per_opt
    # 3) bundled approximate table (per-model), last resort.
    if runner_usd is None:
        pr = _pricing.call_cost(run_model, "runner")
        if pr is not None and metric_calls is not None:
            runner_usd = metric_calls * pr
            source = source or "bundled price table (approximate)"
    if opt_usd is None:
        po = _pricing.call_cost(opt_model, "optimizer")
        if po is not None:
            opt_usd = opt_calls * po
            source = source or "bundled price table (approximate)"

    if runner_usd is None and opt_usd is None:
        out["cost_usd"] = None
        out["note"] = ("no pricing available — showing call counts only. Pass --price-in/"
                       "--price-out (your model's $/MTok), or run once so future estimates "
                       "calibrate from real spend.")
        return out

    expected = (runner_usd or 0.0) + (opt_usd or 0.0)
    out["cost_usd"] = {
        "source": source,
        "runner_usd": round(runner_usd, 4) if runner_usd is not None else None,
        "optimizer_usd": round(opt_usd, 4) if opt_usd is not None else None,
        "expected": round(expected, 2),
        "low": round(expected * 0.5, 2),     # rough ±: runs vary with caching/length
        "high": round(expected * 2.0, 2),
    }
    return out


def _cmd_estimate(argv):
    """Pre-run cost estimate without spending anything."""
    from .specfile import read_yaml

    p = _parser("estimate", _cmd_estimate.__doc__,
                "  cap-evolve estimate\n"
                "  cap-evolve estimate --price-in 3 --price-out 15")
    p.add_argument("--spec", default=".capevolve/project/capevolve.yaml",
                   help="run spec YAML (default: .capevolve/project/capevolve.yaml)")
    p.add_argument("--project", default=".capevolve/project",
                   help="project dir (default: .capevolve/project)")
    p.add_argument("--price-in", type=float, default=None, help="optimizer/runner input $/MTok")
    p.add_argument("--price-out", type=float, default=None, help="optimizer/runner output $/MTok")
    args = p.parse_args(argv)
    spec = read_yaml(Path(args.spec).read_text())
    print(json.dumps(_estimate_core(spec, Path(args.project), args.price_in, args.price_out), indent=2))
    return 0


COMMANDS = {
    "version": _cmd_version,
    "splits": _cmd_splits,
    "check": _cmd_check,
    "run": _cmd_run,
    "estimate": _cmd_estimate,
    "dashboard": _cmd_dashboard,
}

# Phase steps that are NOT cap-evolve subcommands: they are skill scripts run via
# `python <skills>/phases/<name>/scripts/run.py`. Docs and five algorithm SKILL.mds used
# to say `cap-evolve finalize` (issue #203); typing it now gets the real command back
# instead of a bare "unknown command".
# The value is the script's REQUIRED argparse flags. A fixed `--run-dir <dir>` template
# was wrong for 5 of the 8 (#137 review B1): `finalize` also needs `--project`, and
# `intake`/`implement-and-check`/`gate` reject `--run-dir` outright. A confidently WRONG
# remediation at the SEAL step is worse than a bare "unknown command" — the agent runs
# it, fails differently, and stops trusting the tool after the budget is spent.
# `test_phase_redirect_commands_are_runnable` executes every rendered command against a
# real run dir, so these cannot drift from the scripts' own argparse.
_PHASE_SCRIPTS = {
    "intake": "",
    "implement-and-check": "",
    "baseline": "--project <project> --capability <seed_capability>",
    "diagnose": "--run-dir <dir>",
    "evaluate": "--run-dir <dir> --project <project> --candidate <id>",
    "gate": "--current <val> --candidate <val>",
    "finalize": "--run-dir <dir> --project <project>",
    "report": "--run-dir <dir>",
}


def _did_you_mean(name: str) -> str:
    """The 'unknown command' body: closest subcommand, or the real phase-script path."""
    import difflib

    if name in _PHASE_SCRIPTS:
        script = f"python $CAPEVOLVE_SKILLS_DIR/phases/{name}/scripts/run.py"
        flags = _PHASE_SCRIPTS[name]
        return (f"{name!r} is a phase SKILL, not a cap-evolve subcommand — run it as\n"
                f"  {script}{' ' + flags if flags else ''}\n"
                f"  ({script} --help for all flags; phases/{name}/SKILL.md for context)")
    near = difflib.get_close_matches(name, COMMANDS, n=3, cutoff=0.6)
    hint = f"did you mean: {', '.join(near)}?\n" if near else ""
    return hint + f"available commands: {', '.join(COMMANDS)}"


def _usage() -> str:
    """Top-level help, generated from each subcommand's own docstring (can't drift)."""
    width = max(len(c) for c in COMMANDS)
    lines = [f"usage: cap-evolve {{{'|'.join(COMMANDS)}}} [args]", "",
             "commands:"]
    for name, fn in COMMANDS.items():
        # A handler that only delegates (e.g. `doctor` → doctor._main) has no docstring
        # of its own; the fallback keeps the listing from showing a blank row, so a new
        # subcommand can be registered with one COMMANDS line and still read well.
        # `next(iter(...))` not `[0]`: a whitespace-only docstring is truthy but strips
        # to "" whose splitlines() is empty, so indexing raised IndexError and took down
        # EVERY invocation including --help (only on <3.13, where __doc__ keeps the
        # whitespace). requires-python is >=3.10, so that's a real crash. #137 review N1.
        one_line = next(iter((fn.__doc__ or "").strip().splitlines()),
                        f"see `cap-evolve {name} --help`")
        lines.append(f"  {name:<{width}}  {one_line}")
    lines += ["", "run `cap-evolve <command> --help` for a command's flags and examples."]
    return "\n".join(lines)


def _harden_utf8() -> None:
    """Make **stdout** survive a non-UTF-8 locale (LC_ALL=C, PYTHONIOENCODING=ascii).

    stdout is opened ``strict``, so a bad write there DOES raise: the generated help
    listing carries ``→`` from ``_cmd_run``'s docstring, and reports carry ✓/Δ/CJK task
    text, all of which would kill a run that had already spent money. Reconfigure to
    UTF-8 where possible, else fall back to replacing the unencodable glyph — a mangled
    arrow is strictly better than a crash.

    **stderr is deliberately left alone.** CPython already opens it
    ``errors="backslashreplace"`` so it can never raise, and #144's TUI ladder owns it:
    ``eventstream._encodable()`` pre-checks ``stderr.encoding`` to decide whether to
    transliterate (``±`` → ``+/-``). Reconfiguring it here would make that check see
    "utf-8" under an ASCII terminal, skip the transliteration, and ship raw mojibake
    (#215 / #137 review B2). ponytail: CLI-level guard only, stdout only.
    """
    for stream in (sys.stdout,):
        enc = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if enc in ("utf8", "utf8mb4") or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:  # noqa: BLE001 — a non-reconfigurable stream (pytest capture)
            try:
                stream.reconfigure(errors="backslashreplace")
            except Exception:  # noqa: BLE001
                pass


def main(argv=None) -> int:
    _harden_utf8()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        # No args is a usage ERROR (exit 2); an explicit --help is a successful request.
        print(_usage(), file=sys.stderr if not argv else sys.stdout)
        return 2 if not argv else 0
    if argv[0] in ("-V", "--version"):
        return _cmd_version([])
    fn = COMMANDS.get(argv[0])
    if fn is None:
        print(f"cap-evolve: unknown command {argv[0]!r}\n{_did_you_mean(argv[0])}",
              file=sys.stderr)
        return 2
    return fn(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
