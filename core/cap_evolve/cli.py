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
    p.add_argument("--dry-run", action="store_true",
                   help="print a pre-run cost estimate (call counts + $ range) and exit")
    p.add_argument("--run-ts", default=None)
    p.add_argument("--reuse-baseline", default=None,
                   help="prior run dir: reuse its baseline (split/baseline/seed/val-rollouts) "
                        "and skip the baseline eval")
    # Budget overrides — when set, take precedence over the spec's values. Defaults
    # are None so "not passed" is distinguishable from an explicit 0 (= unlimited).
    p.add_argument("--max-iterations", type=int, default=None)
    p.add_argument("--max-metric-calls", type=int, default=None)
    p.add_argument("--max-usd", type=float, default=None)
    p.add_argument("--max-optimizer-usd", type=float, default=None)
    p.add_argument("--stall", type=int, default=None)
    p.add_argument("--optimizer-max-turns", type=int, default=None,
                   help="per-iteration cap passed to the optimizer agent CLI (e.g. claude --max-turns)")
    p.add_argument("--dashboard", choices=("auto", "report-only", "off"), default=None,
                   help="live dashboard: auto (default, launch at run start), report-only, or off")
    p.add_argument("--dashboard-port", type=int, default=None, help="dashboard server port (default 7878)")
    p.add_argument("--telemetry", default=None,
                   help="comma-separated telemetry exporters to enable: mlflow,otel")
    args = p.parse_args(argv)

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
    from .telemetry import resolve_telemetry_config
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
        print(json.dumps(status))
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
                          "telemetry": resolve_telemetry_config(
                              spec, cli_telemetry=args.telemetry, project_dir=proj_abs, run_ts=args.run_ts
                          ),
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
    if args.run_ts:
        base_cmd += ["--run-ts", args.run_ts]
    proc = run(base_cmd)
    if proc.returncode != 0:
        print(json.dumps({"step": "baseline", "error": proc.stderr[-1500:]}))
        return 1
    run_dir = json.loads(proc.stdout)["run_dir"]

    telemetry_cfg = resolve_telemetry_config(
        spec, cli_telemetry=args.telemetry, project_dir=proj_abs, run_ts=args.run_ts or Path(run_dir).name
    )
    if telemetry_cfg.get("enabled"):
        try:
            from .telemetry import Telemetry
            tel = Telemetry(workdir / run_dir, telemetry_cfg)
            tel.save()
            tel.log_run_start(run_dir=workdir / run_dir, spec=spec)
        except Exception:  # noqa: BLE001
            pass

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

    # 2) algorithm (hill-climb variants select their schedule via --focus)
    alg_cmd = [py, skill_run(algorithm_name), "--run-dir", run_dir, "--project", project,
               "--optimizer", opt_cmd, "--max-iterations", str(spec.get("max_iterations", 10)),
               "--n-trials", str(spec.get("num_trials", 1)),
               "--gate-mode", str(spec.get("gate_mode", "auto")),
               "--k-se", str(spec.get("gate_k_se", 1.0)),
               "--store", str(spec.get("store", "git"))]
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
    import argparse
    from .specfile import read_yaml

    p = argparse.ArgumentParser(prog="cap-evolve estimate")
    p.add_argument("--spec", default=".capevolve/project/capevolve.yaml")
    p.add_argument("--project", default=".capevolve/project")
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


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: cap-evolve {version|splits|check|run|estimate|dashboard} [args]", file=sys.stderr)
        return 0 if argv else 2
    fn = COMMANDS.get(argv[0])
    if fn is None:
        print(f"unknown command: {argv[0]}", file=sys.stderr)
        return 2
    return fn(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
