"""Injecting the optimizer's read-context into a working dir (the FILE side of the seam).

Split out of ``harness.py`` (#115). ``optimizer_context.inject`` is the public entry
point every algorithm calls; these are the mechanics behind it — per-tag trajectory
copies, capability guidance + sources, the bench repo pointer, and the NATIVE per-agent
skill dirs / always-on instructions files (``.claude/skills/``, ``CLAUDE.md``, …).

Paired with ``optimizer_context.render_instructions`` (the PROMPT side). Keeping the two
sides in separate modules is what makes the "same context for every algorithm" invariant
#109 established checkable rather than aspirational.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .rundir import RunDir

def _copy_step_trajectories(adapter, run_dir: RunDir, workdir: Path, split: str,
                            tag: str | None = None) -> None:
    """Copy ONLY the current best/parent candidate's per-tag rollouts for ``split``
    into ``workdir/trajectories/`` — the single step the optimizer builds on.

    The run dir's ``rollouts/<split>/`` mixes the seed plus every accepted AND
    rejected candidate's trials, so copying it wholesale would make the optimizer
    analyze stale, irrelevant trajectories. We scope to the BEST candidate's tag
    (``rollouts/<split>/*__<best_id>__t*.json``) — the parent this iteration forks
    from. Fallbacks preserve the existing "always something to read" guarantee:
      1. per-tag rollout copy for the resolved best tag (preferred — scoped);
      2. if no best tag has rollouts yet, the ``seed`` tag;
      3. if neither exists on disk, the adapter's native trajectories dir (if any);
      4. as a last resort, the whole ``rollouts/<split>/`` dir.
    The per-tag copy is preferred even when the adapter returns a native dir, because
    the native dir generally cannot be scoped to one candidate.

    ``tag`` pins the eval tag explicitly instead of resolving the run's best candidate —
    GEPA needs the PARENT's minibatch traces (tag ``mb_p_NNNN``), which are the step it
    actually reflects on. The same fallback chain applies if that tag has no rollouts.
    """
    dst = workdir / "trajectories"

    def _copy_tag(tag: str) -> bool:
        vdir = run_dir.rollouts / split
        if not vdir.is_dir():
            return False
        files = sorted(vdir.glob(f"*__{tag}__t*.json"))
        if not files:
            return False
        try:
            if dst.exists():
                shutil.rmtree(dst)
            dst.mkdir(parents=True, exist_ok=True)
            for f in files:
                shutil.copyfile(f, dst / f.name)
            return True
        except Exception as e:  # noqa: BLE001
            run_dir.log_event("optimizer_context_warning",
                              what=f"trajectories/{tag}", error=str(e)[:300])
            return False

    # An explicit tag (GEPA's parent-minibatch eval) is a PIN, not a preference: the
    # prompt tells the optimizer these are that exact minibatch's rollouts verbatim.
    # A fully-cached minibatch writes no rollout files (the eval cache stores only
    # reward+feedback — see #111), so falling through here would hand the optimizer
    # ANOTHER iteration's traces while still claiming they are this one's. Omit
    # loudly instead: no trajectories/ dir, a warning event, and the prompt block
    # is made conditional on the dir existing at the call site.
    if tag:
        if _copy_tag(str(tag)):
            return
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        run_dir.log_event(
            "optimizer_context_warning", what=f"trajectories/{tag}",
            error="no rollouts persisted for the pinned eval tag (fully-cached "
                  "minibatch); trajectories/ OMITTED rather than substituting another "
                  "iteration's traces")
        return
    best_id = None
    try:
        best_id = run_dir.best_id
    except Exception:  # noqa: BLE001
        best_id = None

    if best_id and _copy_tag(str(best_id)):
        return
    if _copy_tag("seed"):
        return

    # Fallbacks: adapter native dir, then the whole rollouts/<split>/ — so there is
    # ALWAYS something for the optimizer to read.
    traj_src = None
    try:
        traj_src = adapter.trajectories(split)
    except Exception:  # noqa: BLE001 — never let optional context break a step
        traj_src = None
    if not traj_src:
        traj_src = run_dir.rollouts / split
    try:
        traj_src = Path(traj_src)
        if traj_src.is_dir() and any(traj_src.iterdir()):
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(traj_src, dst)
    except Exception as e:  # noqa: BLE001
        run_dir.log_event("optimizer_context_warning", what="trajectories", error=str(e)[:300])


def _inject_optimizer_context(adapter, run_dir: RunDir, workdir: Path, *, split: str,
                              capabilities=None, optimizer_name: str | None = None,
                              capability_sources=None, project_dir: Path | None = None,
                              tag: str | None = None) -> None:
    """Give the optimizer everything it needs to read, inside its own working dir.

    Call it through ``optimizer_context.inject`` (the shared seam every algorithm uses)
    rather than directly, so new injected artifacts reach hill-climb, GEPA and SkillOpt
    at once.

    Copies, VERBATIM and without parsing:
      - the CURRENT BEST/PARENT candidate's per-tag trajectories for the most recent
        ``split`` eval into ``workdir/trajectories/`` — ONLY the step the optimizer
        builds on, not the seed + every rejected candidate (see ``_copy_step_trajectories``);
      - the selected capability skill(s) into ``workdir/guidance/<cap>/`` so the
        optimizer can read the full edit-space guidance + examples without leaving
        its dir;
      - any ``capability_sources`` files (data models / types the tools import) into
        ``workdir/guidance/sources/<basename>`` so the optimizer can write correct code;
      - the diagnose phase skill into ``workdir/guidance/diagnose/`` (the
        failure-clustering method);
      - the resolved optimizer's features reference into
        ``workdir/guidance/optimizer/<optimizer_name>.md`` (parallel-subagent
        capabilities etc.), when ``optimizer_name`` is known and the file exists.
    No benchmark assumptions: the trajectory directory may be any structure / format.
    """
    # 1) trajectories (verbatim) — ONLY the current best/parent candidate's tag for
    # this split, so the optimizer analyzes the step it builds on (not seed + every
    # rejected candidate mixed together). Always preserves the "something to read"
    # guarantee via per-tag fallback then the native dir.
    _copy_step_trajectories(adapter, run_dir, workdir, split, tag=tag)

    # 2) capability skills as local guidance
    caps = [c for c in (capabilities or []) if c]
    if caps:
        skills_root = Path(__file__).resolve().parents[2] / "skills" / "capabilities"
        for c in caps:
            src = skills_root / c
            if not src.is_dir():
                continue
            try:
                shutil.copytree(
                    src, workdir / "guidance" / c,
                    ignore=shutil.ignore_patterns("__pycache__", "scripts", "*.pyc"),
                )
            except Exception as e:  # noqa: BLE001
                run_dir.log_event("optimizer_context_warning", what=f"guidance/{c}", error=str(e)[:300])

    # 2b) capability_sources — supporting source files (data models / types the tools
    # import) copied VERBATIM into ./guidance/sources/<basename> so the optimizer can
    # write correct code against them. Paths resolve relative to the project dir;
    # missing files are tolerated.
    sources = [s for s in (capability_sources or []) if s]
    if sources:
        sdst = workdir / "guidance" / "sources"
        for s in sources:
            try:
                sp = Path(s)
                if not sp.is_absolute() and project_dir is not None:
                    sp = Path(project_dir) / s
                if not sp.is_file():
                    continue
                sdst.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(sp, sdst / sp.name)
            except Exception as e:  # noqa: BLE001
                run_dir.log_event("optimizer_context_warning",
                                  what=f"guidance/sources/{s}", error=str(e)[:300])

    repo_root = Path(__file__).resolve().parents[2]

    # 3) the diagnose phase skill (the failure-clustering method) as local guidance.
    diag_src = repo_root / "skills" / "phases" / "diagnose"
    if diag_src.is_dir():
        try:
            dst = workdir / "guidance" / "diagnose"
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(
                diag_src, dst,
                ignore=shutil.ignore_patterns("__pycache__", "scripts", "*.pyc"),
            )
        except Exception as e:  # noqa: BLE001
            run_dir.log_event("optimizer_context_warning", what="guidance/diagnose", error=str(e)[:300])

    # 4) the resolved optimizer's features reference (parallel subagents etc.).
    if optimizer_name:
        ref_src = (repo_root / "skills" / "optimizers" / "run-optimizer"
                   / "references" / f"{optimizer_name}.md")
        if ref_src.is_file():
            try:
                dst_dir = workdir / "guidance" / "optimizer"
                dst_dir.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ref_src, dst_dir / f"{optimizer_name}.md")
            except Exception as e:  # noqa: BLE001
                run_dir.log_event("optimizer_context_warning",
                                  what=f"guidance/optimizer/{optimizer_name}", error=str(e)[:300])

    # 5) NATIVE per-agent skill injection. The capability + diagnose skills live under
    # ./guidance/ for every agent (above), but a headless coding-agent CLI loads skills
    # most reliably from the path it NATIVELY scans (e.g. claude-code .claude/skills/),
    # plus its always-on instructions file. Resolve the optimizer row and, when it
    # declares those paths, place the skills natively and write a pointer into the
    # instructions file. All best-effort: a missing registry / unknown agent just skips
    # native placement (./guidance/ still works).
    if optimizer_name:
        _inject_native_skills(run_dir, workdir, caps, repo_root, optimizer_name)


def _inject_native_skills(run_dir: RunDir, workdir: Path, caps, repo_root: Path,
                          optimizer_name: str) -> None:
    """Place capability + diagnose skills where ``optimizer_name`` natively discovers
    them, and write a pointer into its always-on instructions file.

    Reads ``skills/optimizers/registry.yaml`` for the per-row ``skills_dir`` /
    ``instructions_file`` fields. Wholly best-effort — any failure (missing registry,
    unknown agent, unreadable row) is logged and skipped so guidance/ remains the
    guaranteed channel.
    """
    try:
        reg_path = repo_root / "skills" / "optimizers" / "registry.yaml"
        if not reg_path.is_file():
            return
        try:
            from .specfile import read_yaml
            registry = read_yaml(reg_path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            return
        row = (registry.get(optimizer_name) or {}) if isinstance(registry, dict) else {}
        if not isinstance(row, dict):
            return
        skills_dir = str(row.get("skills_dir") or "").strip()
        instructions_file = str(row.get("instructions_file") or "").strip()

        cap_root = repo_root / "skills" / "capabilities"
        diag_src = repo_root / "skills" / "phases" / "diagnose"
        ignore = shutil.ignore_patterns("__pycache__", "scripts", "*.pyc")

        # Native skills dir: copy each chosen capability skill + the diagnose skill.
        if skills_dir:
            native_root = workdir / skills_dir
            for c in [x for x in (caps or []) if x]:
                src = cap_root / c
                if not src.is_dir():
                    continue
                try:
                    dst = native_root / c
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst, ignore=ignore)
                except Exception as e:  # noqa: BLE001
                    run_dir.log_event("optimizer_context_warning",
                                      what=f"{skills_dir}/{c}", error=str(e)[:300])
            if diag_src.is_dir():
                try:
                    dst = native_root / "diagnose"
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(diag_src, dst, ignore=ignore)
                except Exception as e:  # noqa: BLE001
                    run_dir.log_event("optimizer_context_warning",
                                      what=f"{skills_dir}/diagnose", error=str(e)[:300])

        # Always-on instructions file: write a short, generic, idempotent pointer block.
        if instructions_file:
            try:
                _write_instructions_pointer(workdir / instructions_file, skills_dir)
            except Exception as e:  # noqa: BLE001
                run_dir.log_event("optimizer_context_warning",
                                  what=f"instructions/{instructions_file}", error=str(e)[:300])
    except Exception as e:  # noqa: BLE001 — native placement must never break a step
        run_dir.log_event("optimizer_context_warning", what="native_skills", error=str(e)[:300])


_NATIVE_POINTER_MARK = "<!-- cap-evolve:native-skills -->"


def _write_instructions_pointer(path: Path, skills_dir: str) -> None:
    """Write (or append) a short generic pointer block into the agent's instructions
    file, idempotently (keyed on a marker comment so it is not duplicated)."""
    existing = ""
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            existing = ""
    if _NATIVE_POINTER_MARK in existing:
        return
    skills_note = (f"the optimization skills are available natively under `{skills_dir}/` and "
                   if skills_dir else "the optimization skills are available under ")
    block = (
        f"{_NATIVE_POINTER_MARK}\n"
        "## cap-evolve optimization task\n"
        "You are running as the edit proposer for a cap-evolve optimization iteration.\n"
        "Read `./INSTRUCTIONS.md` in this directory FIRST and follow it — it states the "
        "capability to improve, the failures to fix, and how your edit is judged.\n"
        f"For method/edit-space guidance, {skills_note}under `./guidance/` "
        "(capability skill(s) + the diagnose failure-clustering method).\n"
        "Cross-iteration files (clean ownership): `./LEDGER.md` (framework facts — every "
        "iteration's outcome + tasks broken/fixed), `./JOURNAL.md` (YOUR append-only "
        "handover across the whole run — append your entry below the marker), `./PROCESS.md` "
        "(YOUR required explainability for this iteration), and `./RUNMAP.md` + "
        "`./prior_iterations/<id>/` (every prior iteration's PROCESS.md + diff — read before "
        "proposing). Read all of these before you start.\n"
    )
    sep = "" if (not existing or existing.endswith("\n\n")) else ("\n" if existing.endswith("\n") else "\n\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(existing + sep + block, encoding="utf-8")
