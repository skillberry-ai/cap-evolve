"""The ``cap-evolve`` CLI — a thin sequencer over the skill ``run.py`` scripts.

``cap-evolve`` does NOT contain pipeline logic; it locates skills (via the registry
manifest) and runs their ``scripts/run.py`` in the order a ``capevolve.yaml`` spec
declares, threading the run dir between them. The honesty guarantees live in
``cap_evolve`` (splits/gate/seal); ``cap-evolve`` just orchestrates.

Human surface: :mod:`cap_evolve.branding` owns the brand headline, the no-args home
screen, the command catalog (one summary + copy-paste examples per command) and the
algorithm chooser; :mod:`cap_evolve.diffview` owns ``cap-evolve diff``. Both are pure
render functions, so every screen is testable without a terminal. All human chrome goes
to **stderr** — stdout stays the machine-readable contract every command advertises.

Subcommands:
    cap-evolve                        branded home screen (golden path + commands)
    cap-evolve help    [command]      full help + runnable examples for one command
    cap-evolve init    [--algorithm N --optimizer N]  scaffold a project + spec
    cap-evolve doctor                 readiness check: what's missing + the fix
    cap-evolve algorithms [name]      the five algorithms and how to select each
    cap-evolve diff    <cand> [--vs X|--best] [--stat|--files] [--unified N]
                       what a candidate actually changed, from its snapshot
    cap-evolve version
    cap-evolve splits  --ids ... [--seed N] [--ratios a,b,c]
    cap-evolve check   [project_dir | --project DIR]
    cap-evolve run     [--spec FILE]  (defaults to <project>/capevolve.yaml)
                       [--resume [--run-ts TS]]  resume an interrupted run in place
                       [--follow]  print live progress while the run works
    cap-evolve tail    [run_dir] [--base .capevolve]  attach to an ongoing run's
                       events.jsonl and print human-readable progress
                       (exit 0 = run finished, 2 = not a possible run dir,
                        3 = --idle-timeout elapsed with no events)
    cap-evolve watch   [run_dir] [--base .capevolve] [--diff]  the same stream as a
                       live full-screen view (same exit codes as tail)
    cap-evolve replay  <run_dir>|--demo [--speed N] [--diff]  re-feed a recorded
                       events.jsonl through the live view; --demo needs no API key

``run`` is intentionally minimal in Phase 0 and grows as phase skills land; it
already resolves the manifest and validates the spec so the wiring is testable.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import sys
import textwrap
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
    """The hard gate. Takes the project dir positionally OR as ``--project`` (the flag
    every other subcommand uses), because the alternative was worse than a usage error:
    ``Path(argv[0])`` turned ``--project X`` into the literal path ``--project`` and the
    gate reported "no adapter" for a project whose adapter was right there.
    """
    argv = list(argv)
    project = None
    while argv:
        a = argv.pop(0)
        if a in ("--project", "-p"):
            if not argv:
                print("check: --project needs a path", file=sys.stderr)
                return 2
            project = Path(argv.pop(0))
        elif a.startswith("--project="):
            project = Path(a.split("=", 1)[1])
        elif a.startswith("-"):
            print(f"check: unknown option {a!r}  (usage: cap-evolve check [project_dir])",
                  file=sys.stderr)
            return 2
        elif project is None:
            project = Path(a)
        else:
            print(f"check: unexpected extra argument {a!r}", file=sys.stderr)
            return 2
    rep = run_check(project or Path(".capevolve/project"))
    print(json.dumps(rep.to_dict(), indent=2))
    return 0 if rep.ok else 1


def _events_path(base: Path, run_ts: str | None, seen: set[str] | None) -> Path | None:
    """Locate the run's ``events.jsonl``, or ``None`` if no run dir exists yet.

    With ``run_ts`` the path is known up front. Otherwise pick the newest ``run_*``
    that is NOT in ``seen`` (the dirs that existed before this run started), so a
    follower attaches to *this* run and not a previous one.
    """
    if run_ts:
        return base / f"run_{run_ts}" / "events.jsonl"
    runs = sorted(p for p in base.glob("run_*") if p.is_dir() and p.name not in (seen or set()))
    return (runs[-1] / "events.jsonl") if runs else None


def _stderr_is_usable() -> bool:
    """True only if progress can safely be written to a real, distinct stderr.

    Under ``2>&-`` CPython either sets ``sys.stderr`` to ``None`` or hands fd 2 to the
    next ``open()``, so writes would land *interleaved in stdout* and break the
    machine-readable JSON contract ``--follow`` advertises. Following silently off is
    strictly better than corrupt stdout.
    """
    err = sys.stderr
    if err is None or getattr(err, "closed", False):
        return False
    try:
        efd = err.fileno()
    except Exception:  # noqa: BLE001 — a captured StringIO has no fd; safe to write to
        return True
    # fd 2 closed and reused by the next open() → that fd is not stderr any more.
    # (`>f 2>&1` keeps fd 2 == 2 pointing at the same file, which is legitimate.)
    return efd == 2


def _spawn_follower(base: Path, run_ts: str | None, seen: set[str] | None,
                    offset: int = 0, tui_mode: bool = False, show_diff: bool = False):
    """Print live progress from ``events.jsonl`` on a daemon thread.

    Returns ``(stop_event, thread)`` — or ``(None, None)`` when stderr is unusable, in
    which case following is disabled rather than corrupting stdout. Set the event when
    the run finishes. Reads the same typed event stream the dashboard's SSE route
    serves (``cap_evolve.eventstream``), so terminal and web can't disagree. Never
    raises into the run — but never dies *quietly* either: if the follower stops, it
    says so on stderr, because silence mistaken for progress is the bug #116 fixes.
    """
    import threading
    from . import eventstream

    if not _stderr_is_usable():
        return None, None

    stop = threading.Event()
    err = sys.stderr  # bind now: don't follow a stream reassigned mid-run
    color = eventstream.use_color(err)

    def worker():
        # Progress goes to STDERR: stdout stays the machine-readable JSON contract that
        # scripts parse, so `cap-evolve run --follow > out.json` keeps working.
        try:
            path = None
            while path is None and not stop.is_set():
                path = _events_path(base, run_ts, seen)
                if path is None:
                    stop.wait(0.5)
            if path is None:
                return
            if tui_mode:
                # Same event stream, same stderr, full-screen instead of one line each.
                from . import tui
                tui.watch(path.parent, stream=err, color=color, show_diff=show_diff,
                          should_stop=lambda _last: stop.is_set())
                return
            totals: dict = {}
            for ev in eventstream.follow_events(
                    path, offset=offset, poll=0.5,
                    should_stop=lambda _last: stop.is_set()):
                line = eventstream.render_line(ev, totals, color=color)
                if line:
                    print(line, file=err, flush=True)
        except Exception as e:  # noqa: BLE001 — observability must never break the run
            # ...but it must never go dark in silence either. #144: this is the hook for
            # the forensic crash log; the user-visible line below is the minimum.
            try:
                print(f"[follow] live progress stopped: {e!r} — the run continues; "
                      f"use `cap-evolve tail` or the dashboard to watch it",
                      file=err, flush=True)
            except Exception:  # noqa: BLE001 — stderr died too; nothing left to do
                pass

    t = threading.Thread(target=worker, name="cap-evolve-follow", daemon=True)
    t.start()
    return stop, t


def _cmd_tail(argv):
    """Attach to an existing/ongoing run dir and print its event stream."""
    import argparse
    from . import eventstream

    p = argparse.ArgumentParser(
        prog="cap-evolve tail",
        description="tail a run's events.jsonl as human-readable progress lines",
        epilog=_epilog("tail"),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir", nargs="?", default=None,
                   help="run dir (default: newest run_* under --base)")
    p.add_argument("--base", default=".capevolve", help="dir containing run_* dirs")
    p.add_argument("--from-start", action="store_true",
                   help="replay the whole log first (default: only new events)")
    p.add_argument("--idle-timeout", type=float, default=300.0,
                   help="give up after N seconds of silence (0 = wait forever)")
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args(argv)
    if args.idle_timeout < 0:  # a negative timeout used to trip the check immediately
        p.error("--idle-timeout must be >= 0 (0 = wait forever)")

    if args.run_dir:
        root = Path(args.run_dir)
    else:
        runs = sorted(q for q in Path(args.base).glob("run_*") if q.is_dir())
        if not runs:
            print(f"no run_* dirs under {args.base}", file=sys.stderr)
            return 1
        root = runs[-1]
    events = root / "events.jsonl"
    # A named run dir need NOT exist yet: attaching before `cap-evolve run` creates it
    # is the whole point. But a path whose PARENT doesn't exist can never become a run
    # dir, so a typo fails fast with a distinct code instead of pretend-waiting 5 min.
    if not root.exists() and not root.parent.is_dir():
        print(f"no such run dir: {root}", file=sys.stderr)
        return 2
    if not events.exists():
        print(f"waiting for {events} …", file=sys.stderr, flush=True)

    color = not args.no_color and eventstream.use_color(sys.stdout)
    offset = 0 if args.from_start or not events.exists() else events.stat().st_size
    totals: dict = {}
    shown, reason = 0, None
    try:
        for ev in eventstream.follow_events(
                events, offset=offset, poll=0.5,
                idle_timeout=(args.idle_timeout or None)):
            if ev.get("kind") == eventstream.FOLLOW_END:
                reason = ev.get("reason")
                continue
            line = eventstream.render_line(ev, totals, color=color)
            if line:
                print(line, flush=True)
                shown += 1
    except KeyboardInterrupt:
        return 130
    if reason == "idle" and not shown:
        # Distinct from "the run finished": scripts can tell a timeout from a result.
        print(f"timed out after {args.idle_timeout:g}s with no events from {events}",
              file=sys.stderr)
        return 3
    return 0


def _resolve_run_dir(run_dir: str | None, base: str):
    """(root, exit_code) — the run dir to attach to. Mirrors ``_cmd_tail``'s rules:
    explicit path wins, else the newest ``run_*`` under ``--base``; exit 1 when the
    base has no runs, 2 when the named path can never become a run dir."""
    if run_dir:
        root = Path(run_dir)
        if not root.exists() and not root.parent.is_dir():
            print(f"no such run dir: {root}", file=sys.stderr)
            return None, 2
        return root, 0
    runs = sorted(q for q in Path(base).glob("run_*") if q.is_dir())
    if not runs:
        print(f"no run_* dirs under {base}", file=sys.stderr)
        return None, 1
    return runs[-1], 0


def _cmd_watch(argv):
    """Live full-screen view of a run. Same exit codes as ``tail``."""
    import argparse
    from . import tui

    p = argparse.ArgumentParser(
        prog="cap-evolve watch",
        description="live full-screen view of a running or finished run",
        epilog=_epilog("watch"),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir", nargs="?", default=None,
                   help="run dir (default: newest run_* under --base)")
    p.add_argument("--base", default=".capevolve", help="dir containing run_* dirs")
    p.add_argument("--idle-timeout", type=float, default=300.0,
                   help="give up after N seconds of silence (0 = wait forever)")
    p.add_argument("--diff", action="store_true",
                   help="add a panel showing what the newest accepted candidate changed")
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args(argv)
    if args.idle_timeout < 0:
        p.error("--idle-timeout must be >= 0 (0 = wait forever)")

    root, code = _resolve_run_dir(args.run_dir, args.base)
    if root is None:
        return code
    events = root / "events.jsonl"
    if not events.exists():
        print(f"waiting for {events} …", file=sys.stderr, flush=True)
    # The view goes to stderr so stdout stays the machine-readable contract.
    color = None if not args.no_color else False
    reason = tui.watch(root, stream=sys.stderr, color=color, show_diff=args.diff,
                       idle_timeout=(args.idle_timeout or None))
    if reason == "interrupt":
        return 130
    if reason == "idle":
        print(f"timed out after {args.idle_timeout:g}s with no events from {events}",
              file=sys.stderr)
        return 3
    return 0


def _cmd_replay(argv):
    """Re-feed a recorded events.jsonl through the live view."""
    import argparse
    from . import tui

    p = argparse.ArgumentParser(
        prog="cap-evolve replay",
        description="replay a recorded run through the live view (no API key needed)",
        epilog=_epilog("replay"),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir", nargs="?", default=None, help="run dir to replay")
    p.add_argument("--demo", action="store_true",
                   help=f"replay the bundled demo session. {tui.DEMO_BANNER}")
    p.add_argument("--speed", type=float, default=1.0, help="playback speed multiplier")
    p.add_argument("--max-gap", type=float, default=1.0,
                   help="cap the sleep between events (seconds)")
    p.add_argument("--diff", action="store_true",
                   help="add a panel showing what the newest accepted candidate changed")
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args(argv)
    if args.speed <= 0:
        p.error("--speed must be > 0")
    if bool(args.demo) == bool(args.run_dir):
        p.error("pass exactly one of run_dir or --demo")

    src = tui.DEMO_DIR if args.demo else Path(args.run_dir)
    if not (src / "events.jsonl").exists():
        print(f"no events.jsonl under {src}", file=sys.stderr)
        return 2
    try:
        tui.replay(src, stream=sys.stderr, color=(False if args.no_color else None),
                   speed=args.speed, max_gap=args.max_gap, show_diff=args.diff,
                   banner=(tui.DEMO_BANNER if args.demo else None))
    except KeyboardInterrupt:
        return 130
    return 0


# Old hill-climb skill names → (skill, focus). The three byte-identical clones are
# now one ``hill-climb`` skill parameterized by ``--focus``.
_ALGO_FOCUS_ALIASES = {
    "all-at-once": ("hill-climb", "all"),
    "cyclic": ("hill-climb", "cyclic"),
    "hardest-first": ("hill-climb", "hardest-first"),
}

#: Algorithms whose ``run.py`` accepts ``--convergence`` (the graded stall signal in
#: ``cap_evolve.convergence``). gepa stops on its own ``gepa_stop`` and skillopt on its
#: epoch schedule, so the spec key is inert for them — and we say so rather than drop it.
CONVERGENCE_ALGORITHMS = frozenset({"hill-climb"})

#: Algorithms whose ``run.py`` declares the optimizer-context flags (via
#: ``harness.OptimizerContext.add_arguments``) and can therefore be handed the full
#: read-context: capability skills, the instructions template, the benchmark repo, the
#: optimizer name, the capability sources, and the target-reader profile. These flags used
#: to be gated to hill-climb alone, which silently handed gepa and skillopt a strictly
#: thinner prompt and made any cross-algorithm comparison meaningless.
OPTIMIZER_CONTEXT_ALGORITHMS = frozenset({"hill-climb", "gepa", "skillopt"})


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


def _step_failure(step: str, proc) -> dict:
    """Build the failure record for a step that exited non-zero.

    Steps run under ``capture_output``, so this record is the ONLY evidence of what
    happened. A stderr tail alone is not enough: when a step is killed by a signal
    (the OOM killer, most often) it leaves no Python traceback at all, so the tail is
    whatever harmless warnings happened to be last and the record reads as if nothing
    went wrong. The returncode — and, for a signal, its name — is what distinguishes
    "raised" from "was killed".
    """
    rec: dict = {"step": step, "returncode": proc.returncode}
    if proc.returncode < 0:
        sig = -proc.returncode
        try:
            name = signal.Signals(sig).name
        except ValueError:
            name = f"signal {sig}"
        rec["signal"] = name
        # Signal-specific, because the remedy differs and a wrong hint sends the reader
        # to the wrong place: SIGKILL is usually the OOM killer, but SIGSEGV is a native
        # crash in a C extension and dmesg will say nothing useful about it.
        if name == "SIGSEGV":
            rec["hint"] = (
                f"{step} died in NATIVE code (SIGSEGV), not a Python exception — most likely a "
                "C extension the adapter pulls in (numpy/pandas in a scorer, a client library). "
                "cap_evolve enables faulthandler, so look for a 'Fatal Python error' block with "
                "a native traceback in this record's error field."
            )
        else:
            rec["hint"] = (
                f"{step} was killed by {name}, not a Python exception — there is no Python "
                "traceback to find. SIGKILL is usually the OOM killer; check dmesg/journalctl -k."
            )
    # Head AND tail. A tail alone loses the crash: a chatty scoring phase can emit tens of
    # kilobytes AFTER the interesting output, so the window shows routine per-rollout noise
    # and the record reads as if nothing went wrong (exactly what masked run 30608405812's
    # SIGSEGV). faulthandler's native traceback lands at the very end, so keep more tail
    # than head.
    rec["error"] = _clip(proc.stderr, head=4000, tail=12000)
    if proc.stdout:
        rec["stdout_tail"] = proc.stdout[-2000:]
    return rec


def _clip(text: str | None, *, head: int, tail: int) -> str:
    """Keep the first ``head`` and last ``tail`` characters, marking what was dropped."""
    text = text or ""
    if len(text) <= head + tail:
        return text
    dropped = len(text) - head - tail
    return f"{text[:head]}\n\n... [{dropped} chars omitted] ...\n\n{text[-tail:]}"


def _resolve_spec(spec: str | None, project: str) -> tuple[Path | None, dict | None]:
    """``(spec_path, error)`` — the spec that belongs to ``--project``.

    ``--spec`` used to default to the literal ``.capevolve/project/capevolve.yaml``
    *relative to the cwd*, so ``cap-evolve run --project OTHER`` silently optimized a
    DIFFERENT project's spec: the run started, the baseline scored, events streamed —
    everything looked healthy while the wrong capability was measured against the wrong
    adapter. On a paid run that is real money spent on a meaningless result, and nothing
    in the run dir would ever have revealed the mismatch. So:

    * the default is now resolved **relative to ``--project``**;
    * an explicit ``--spec`` that points OUTSIDE the project dir is refused, naming both
      paths, instead of being run;
    * the resolved path is echoed at startup and logged into the run dir
      (``run_config``), so a finished run is self-describing.
    """
    proj = Path(project).resolve()
    path = (proj / "capevolve.yaml") if not spec else Path(spec).resolve()
    if not path.exists():
        return None, {"step": "spec", "error": f"no spec at {path}",
                      "project": str(proj),
                      "fix": (f"cap-evolve init --project {project}"
                              if not spec else
                              f"cap-evolve run --project {project}   "
                              "# omit --spec to use the project's own capevolve.yaml")}
    try:
        inside = path.is_relative_to(proj)
    except AttributeError:  # pragma: no cover — Python < 3.9
        inside = str(path).startswith(str(proj))
    if not inside:
        return None, {
            "step": "spec",
            "error": ("--spec is outside --project: refusing to optimize one project's "
                      "capability against another's spec"),
            "spec": str(path), "project": str(proj),
            "fix": f"cap-evolve run --project {path.parent}   # or pass the project's own spec",
        }
    return path, None


def _json_payload(text: str) -> dict:
    """Extract a phase subprocess's JSON payload from its captured stdout.

    Phases are *supposed* to print nothing but their JSON object; the harness
    redirects adapter output to stderr to keep that true. This is the second line of
    defense: one stray ``print`` anywhere under an adapter used to take down the whole
    run with ``JSONDecodeError: Expecting value: line 1 column 1`` — after the
    expensive part had already succeeded and been written to disk. Losing an 11-minute
    baseline to a log line is not a reasonable failure mode.

    A phase prints its payload LAST, so candidate object starts are tried newest-first
    and the first one that decodes wins. Raises ``json.JSONDecodeError`` when stdout
    holds no JSON object at all, so a genuinely broken phase still fails loudly.
    """
    text = text or ""
    with contextlib.suppress(json.JSONDecodeError):
        return json.loads(text)

    decoder = json.JSONDecoder()
    # Candidate starts: every line that begins a JSON object, newest first. Matching on
    # line starts (not every "{" in the buffer) keeps this linear and avoids decoding
    # from inside a nested object, which would return a fragment of the real payload.
    starts, offset = [], 0
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("{"):
            starts.append(offset + (len(line) - len(line.lstrip())))
        offset += len(line)
    for start in reversed(starts):
        try:
            obj, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise json.JSONDecodeError("no JSON object found in phase stdout", text, 0)


def _cmd_run(argv):
    import argparse
    import subprocess
    from .specfile import read_yaml

    p = argparse.ArgumentParser(prog="cap-evolve run",
        description=_summary("run"),
        epilog=_epilog("run"),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spec", default=None,
                   help="run spec (default: <project>/capevolve.yaml — resolved relative "
                        "to --project, never to the cwd)")
    p.add_argument("--project", default=".capevolve/project")
    p.add_argument("--skills-dir", default=None)
    p.add_argument("--plan-only", action="store_true", help="print the command plan, don't execute")
    p.add_argument("--dry-run", action="store_true",
                   help="print a pre-run cost estimate (call counts + $ range) and exit")
    p.add_argument("--run-ts", default=None)
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
    p.add_argument("--max-iterations", type=int, default=None)
    p.add_argument("--max-metric-calls", type=int, default=None)
    p.add_argument("--max-usd", type=float, default=None)
    p.add_argument("--max-optimizer-usd", type=float, default=None)
    p.add_argument("--stall", type=int, default=None)
    p.add_argument("--optimizer-max-turns", type=int, default=None,
                   help="per-iteration cap passed to the optimizer agent CLI (e.g. claude --max-turns)")
    p.add_argument("--follow", action="store_true",
                   help="print live progress (stage/candidate/accept-reject/cost) to stderr "
                        "as the run writes events.jsonl; stdout stays the final JSON")
    p.add_argument("--tui", action="store_true",
                   help="like --follow, but a live full-screen view (stderr) instead of "
                        "one line per event; stdout stays the final JSON")
    p.add_argument("--diff", action="store_true",
                   help="with --tui: add a panel showing what each accepted candidate "
                        "changed (the diff comes from the candidate snapshots)")
    p.add_argument("--dashboard", choices=("auto", "report-only", "off"), default=None,
                   help="live dashboard: auto (default, launch at run start), report-only, or off")
    p.add_argument("--dashboard-port", type=int, default=None, help="dashboard server port (default 7878)")
    args = p.parse_args(argv)

    skills_dir = Path(args.skills_dir) if args.skills_dir else _find_skills_dir()
    if not skills_dir:
        print(json.dumps({"error": "skills dir not found; set CAPEVOLVE_SKILLS_DIR or --skills-dir"}))
        return 1
    skills = _resolve_skills(skills_dir)
    spec_path, spec_err = _resolve_spec(args.spec, args.project)
    if spec_err is not None:
        print(json.dumps(spec_err))
        print(f"{spec_err['error']}\n  → {spec_err['fix']}", file=sys.stderr)
        return 1
    spec = read_yaml(spec_path.read_text(encoding="utf-8"))

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
    # Which spec this run is actually using, echoed up front. Guarded by
    # _stderr_is_usable(): under `2>&-` a write to "stderr" would land in stdout and
    # break the JSON contract, and provenance is not worth corrupting the payload.
    if _stderr_is_usable():
        print(f"spec: {spec_path}", file=sys.stderr, flush=True)
    dash_url = ""
    if dash_mode == "auto":
        status = dashboard_launch.maybe_launch(
            proj_abs.parent, mode=dash_mode, port=dash_port, open_browser=True)
        u = status.get("dashboard")
        if isinstance(u, str) and u.startswith("http"):
            dash_url = u
        # stderr, not stdout: this is a URL for a human to click, and the machine-readable
        # summary already carries it as ``dashboard_server``. On stdout it made a finished
        # run print TWO json documents, so `cap-evolve run | jq` could not parse it.
        if _stderr_is_usable():
            print(json.dumps(status), file=sys.stderr, flush=True)
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
        print(json.dumps({"skills_dir": str(skills_dir), "workdir": str(workdir),
                          "spec_path": str(spec_path), "spec": spec,
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

    # --follow: start tailing events.jsonl now, BEFORE baseline creates the run dir, so
    # the very first events (splits/baseline) are seen. `seen` freezes the pre-existing
    # run dirs so an unpinned --run-ts follower attaches to this run, not the last one.
    follow_stop = follow_thread = None
    if args.follow or args.tui:
        base_abs = proj_abs.parent
        seen = {p.name for p in base_abs.glob("run_*") if p.is_dir()} if not resume_ts else None
        # On --resume, skip the prior log (10k old events are not "live progress"):
        # start at the current end of file, the way `cap-evolve tail` does.
        prior = base_abs / f"run_{resume_ts}" / "events.jsonl" if resume_ts else None
        off = prior.stat().st_size if prior and prior.exists() else 0
        follow_stop, follow_thread = _spawn_follower(base_abs, resume_ts, seen, off,
                                                     tui_mode=args.tui,
                                                     show_diff=args.diff)

    def done(code: int) -> int:
        """Drain + stop the follower thread, then return ``code``. Used at every exit."""
        if follow_stop is not None:
            follow_stop.set()
            follow_thread.join(timeout=3.0)
        return code

    # 1) baseline (creates the run dir; capture its relative path)
    base_cmd = [py, skill_run("baseline"), "--base", base, "--project", project,
                "--capability", cap_path, "--seed", str(spec.get("split_seed", 0)),
                "--ratios", ratios, "--max-iterations", str(spec.get("max_iterations", 10)),
                "--stall", str(spec.get("stall", 0)), "--n-trials", str(spec.get("num_trials", 1)),
                "--max-metric-calls", str(spec.get("max_metric_calls", 0)),
                "--max-usd", str(spec.get("max_usd", 0.0)),
                "--max-optimizer-usd", str(spec.get("max_optimizer_usd", 0.0)),
                "--spec", str(spec_path)]
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
    run_dir = _json_payload(proc.stdout)["run_dir"]

    # Make the run self-describing: which spec/project/algorithm produced it. Without
    # this, a run started against the wrong spec leaves no artifact that says so.
    try:
        _RunDir.open(workdir / run_dir).log_event(
            "run_config", spec=str(spec_path), project=str(proj_abs),
            algorithm=algorithm_name, optimizer=str(optimizer_name),
            orchestration_mode=orchestration_mode)
    except Exception:  # noqa: BLE001 — provenance is best-effort, never fatal
        pass

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
                          "spec_path": str(spec_path), "dashboard": dash_url or "off",
                          "stop_condition": str(spec.get("stop_condition", "")),
                          "next": "drive via the orchestrate Agent-mode loop; "
                                  "seal with `cap-evolve finalize`"}))
        return done(0)

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
    # allowed edit space (e.g. tools → may add composite tools). Passed to every
    # algorithm that declares the optimizer-context flags, so each one prompts from the
    # same read-context.
    caps = spec.get("capabilities") or []
    if isinstance(caps, str):
        caps = [c.strip() for c in caps.split(",") if c.strip()]
    if caps and algorithm_name in OPTIMIZER_CONTEXT_ALGORITHMS:
        alg_cmd += ["--capabilities", ",".join(str(c) for c in caps)]
    # Thread the resolved optimizer NAME so the harness can copy that optimizer's
    # features reference (parallel-subagent capabilities etc.) into each iteration's
    # workdir and place the skills where that agent natively finds them.
    if algorithm_name in OPTIMIZER_CONTEXT_ALGORITHMS:
        alg_cmd += ["--optimizer-name", str(optimizer_name)]
    # Optimizer-instructions template (intake-authored, per benchmark) + benchmark repo
    # as read-only optimizer context. Both are resolved project-relative if not absolute.
    # The instructions file defaults to the scaffolded project/optimizer/INSTRUCTIONS.md.
    if algorithm_name in OPTIMIZER_CONTEXT_ALGORITHMS:
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
    # Protected-path seal + graded convergence signal. Both are OPT-IN: absent keys
    # add no flags at all, so an existing spec runs byte-identically.
    if algorithm_name in ("hill-climb", "skillopt", "gepa"):
        pp = spec.get("protected_paths") or []
        if isinstance(pp, str):
            pp = [p.strip() for p in pp.split(",") if p.strip()]
        if pp:
            alg_cmd += ["--protected-paths", ",".join(str(p) for p in pp)]
    if spec.get("convergence"):
        if algorithm_name in CONVERGENCE_ALGORITHMS:
            alg_cmd += ["--convergence"]
        else:
            # Say so. Silently dropping the key reads as "convergence is on" for the
            # whole run; gepa and skillopt stop on their own signals (gepa_stop, the
            # epoch schedule) and have no --convergence to forward it to.
            print(f"warn: spec sets convergence: true, but {algorithm_name} does not "
                  f"support the graded convergence signal (only "
                  f"{', '.join(sorted(CONVERGENCE_ALGORITHMS))}). Ignoring it; "
                  f"{algorithm_name} uses its own stop condition.", file=sys.stderr)
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
        print(json.dumps(_step_failure("algorithm", proc)))
        return 1

    # 3) finalize  4) report
    last = proc.stdout
    report_extra = ["--dashboard-mode", dash_mode, "--dashboard-port", str(dash_port)]
    # The server this run ALREADY started. Without this the report phase calls
    # maybe_launch() again, _free_port() steps past the port our own server holds, and
    # every run leaks a second dashboard process on a second port — then reports that
    # second URL, contradicting the one printed at the top.
    if dash_url:
        report_extra += ["--dashboard-url", dash_url]
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
            print(json.dumps(_step_failure(step, proc)))
            return 1
        last = proc.stdout

    print(last)
    return done(0)


def _cmd_dashboard(argv):
    """Launch (or focus) the live dashboard server over a base dir of runs."""
    import argparse
    from . import dashboard_launch

    p = argparse.ArgumentParser(prog="cap-evolve dashboard",
        description=_summary("dashboard"),
        epilog=_epilog("dashboard"),
        formatter_class=argparse.RawDescriptionHelpFormatter)
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

    p = argparse.ArgumentParser(prog="cap-evolve estimate",
        description=_summary("estimate"),
        epilog=_epilog("estimate"),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spec", default=None,
                   help="run spec (default: <project>/capevolve.yaml)")
    p.add_argument("--project", default=".capevolve/project")
    p.add_argument("--price-in", type=float, default=None, help="optimizer/runner input $/MTok")
    p.add_argument("--price-out", type=float, default=None, help="optimizer/runner output $/MTok")
    args = p.parse_args(argv)
    spec_path, spec_err = _resolve_spec(args.spec, args.project)
    if spec_err is not None:
        print(json.dumps(spec_err, indent=2))
        print(f"{spec_err['error']}\n  → {spec_err['fix']}", file=sys.stderr)
        return 1
    spec = read_yaml(spec_path.read_text(encoding="utf-8"))
    out = _estimate_core(spec, Path(args.project), args.price_in, args.price_out)
    out["spec_path"] = str(spec_path)
    print(json.dumps(out, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Human surface: home screen, help, algorithms, doctor, init, diff
# ---------------------------------------------------------------------------

def _screen(lines, *, stream=None) -> None:
    """Print a rendered screen to STDERR — human chrome never touches stdout."""
    print("\n".join(lines), file=(stream or sys.stderr), flush=True)


def _size(stream=None) -> int:
    from .dashboard import _term_width
    return _term_width(100)


def _rows(default: int = 24) -> int:
    """Terminal height, for screens that must FIT rather than scroll. The home screen
    overshooting by a row scrolls the capybara and the golden path off the top."""
    import shutil
    try:
        return max(4, shutil.get_terminal_size((80, default)).lines)
    except OSError:
        return default


def _wants_color(stream=None, argv=()) -> bool:
    """TTY + ``NO_COLOR`` decision, with an explicit ``--no-color`` override."""
    from . import eventstream
    if "--no-color" in tuple(argv):
        return False
    return eventstream.use_color(stream or sys.stderr)


def _cmd_home(argv) -> int:
    from . import branding
    _screen(branding.home(_size(), color=_wants_color(argv=argv), version=__version__,
                          rows=_rows()))
    return 0


def _cmd_help(argv) -> int:
    from . import branding
    name = next((a for a in argv if not a.startswith("-")), None)
    if name is None and not argv:
        return _cmd_home(argv)
    _screen(branding.help_for(name, _size(), color=_wants_color(argv=argv)))
    return 0


def _cmd_algorithms(argv) -> int:
    from . import branding
    if "--json" in argv:
        print(json.dumps(branding.ALGORITHMS, indent=2))
        return 0
    name = next((a for a in argv if not a.startswith("-")), None)
    _screen(branding.algorithms_screen(name, _size(), color=_wants_color(argv=argv)))
    return 0


#: doctor verdicts, worst-first. ``fail`` blocks a run; ``warn`` never does.
_MARK = {"ok": ("ok  ", "\033[32m"), "warn": ("warn", "\033[33m"),
         "fail": ("FAIL", "\033[31m"), "skip": ("--  ", "\033[90m")}


def _optimizer_row(name: str, skills_dir: Path | None) -> dict:
    """The registry row for an optimizer name, or ``{}``. Never raises."""
    if not skills_dir:
        return {}
    reg = Path(skills_dir) / "optimizers" / "registry.yaml"
    if not reg.exists():
        return {}
    try:
        from .specfile import read_yaml
        row = (read_yaml(reg.read_text(encoding="utf-8")) or {}).get(name)
    except Exception:  # noqa: BLE001 — doctor must never crash on a bad registry
        return {}
    return row if isinstance(row, dict) else {}


def _doctor_checks(project: Path) -> list[dict]:
    """``[{name, status, detail, fix}]`` — every precondition a run needs.

    Each row names what is missing AND the exact command that fixes it, because a
    readiness check that only says "not ready" makes the user guess.
    """
    import shutil as _shutil
    from .specfile import read_yaml

    project = Path(project)
    rows: list[dict] = []

    def add(name, status, detail, fix=""):
        rows.append({"name": name, "status": status, "detail": detail, "fix": fix})

    spec_path = project / "capevolve.yaml"
    if not spec_path.exists():
        add("spec", "fail", f"no {spec_path}", f"cap-evolve init --project {project}")
        return rows
    try:
        spec = read_yaml(spec_path.read_text(encoding="utf-8")) or {}
    except Exception as e:  # noqa: BLE001
        add("spec", "fail", f"{spec_path} is unreadable: {e!r}",
            f"fix the YAML, then: cap-evolve doctor --project {project}")
        return rows
    add("spec", "ok", str(spec_path))

    algo = str(spec.get("algorithm_skill") or "")
    mode = str(spec.get("orchestration_mode") or "deterministic")
    from . import branding
    meta = branding.ALGORITHMS.get(algo)
    if meta is None:
        add("algorithm", "fail", f"unknown algorithm_skill: {algo or '(unset)'}",
            "cap-evolve algorithms")
    elif meta["mode"] == "agent" and mode != "agent":
        add("algorithm", "fail",
            f"{algo} is agent-driven but orchestration_mode is {mode!r}",
            f"set orchestration_mode: agent in {spec_path}")
    else:
        add("algorithm", "ok", f"{algo} ({mode})")

    # An inert spec key is worse than a missing one: the reader believes it is on.
    if spec.get("convergence") and _resolve_algorithm(algo)[0] not in CONVERGENCE_ALGORITHMS:
        add("convergence", "warn",
            f"convergence: true is ignored by {algo} (its own stop condition applies)",
            f"remove the key, or set algorithm_skill to one of "
            f"{', '.join(sorted(CONVERGENCE_ALGORITHMS))}")

    adapter = project / "adapters" / "adapter.py"
    if not adapter.exists():
        add("adapter", "fail", f"no {adapter}",
            f"cap-evolve init --project {project}  (then implement the 4 methods)")
    else:
        rep = run_check(project)
        if rep.ok:
            add("adapter", "ok", "contract holds (tasks stable, scorer deterministic)")
        else:
            add("adapter", "fail", "; ".join(rep.problems)[:400] or "check failed",
                f"cap-evolve check {project}")

    cap = str(spec.get("capability_path") or "seed_capability")
    workdir = project.resolve().parent.parent
    cap_p = Path(cap) if Path(cap).is_absolute() else workdir / cap
    if cap_p.is_dir() and any(cap_p.iterdir()):
        add("capability", "ok", f"{cap} ({len(list(cap_p.rglob('*')))} files)")
    elif cap_p.is_dir():
        add("capability", "fail", f"{cap_p} is empty — nothing to optimize",
            f"put the artifact to optimize in {cap_p}")
    else:
        add("capability", "fail", f"no capability dir at {cap_p}",
            f"mkdir -p {cap_p} and put the artifact to optimize there")

    skills_dir = _find_skills_dir()
    if skills_dir is None:
        add("skills", "fail", "no skills dir found",
            "bash install.sh   # or set CAPEVOLVE_SKILLS_DIR")
    elif not (skills_dir / "_registry" / "manifest.json").exists():
        add("skills", "fail", f"{skills_dir} has no _registry/manifest.json",
            "python3 skills/_registry/build_manifest.py")
    else:
        add("skills", "ok", str(skills_dir))

    opt = str(spec.get("optimizer_skill") or "")
    row = _optimizer_row(opt, skills_dir)
    # Distinguish "the registry has no such name" from "there is no registry" — they have
    # OPPOSITE fixes, and conflating them tells the user to edit a spec that is already correct.
    reg_path = (Path(skills_dir) / "optimizers" / "registry.yaml") if skills_dir else None
    reg_missing = reg_path is None or not reg_path.exists()
    if opt == "mock":
        add("optimizer", "ok", "mock (deterministic, zero-API)")
    elif reg_missing:
        where = str(reg_path) if reg_path else "(no skills dir)"
        add("optimizer", "warn",
            f"cannot verify {opt or '(unset)'}: no optimizer registry at {where}",
            "bash install.sh   # or set CAPEVOLVE_SKILLS_DIR to a tree that has "
            "optimizers/registry.yaml")
    elif not row:
        add("optimizer", "warn", f"{opt or '(unset)'} is not in optimizers/registry.yaml",
            "cap-evolve algorithms   # then pick a registered optimizer_skill")
    else:
        tmpl = str(row.get("command_template") or "")
        argv0 = next((t for t in tmpl.split() if not t.startswith("{")), "")
        binary = Path(argv0).name
        if binary and binary not in ("python3", "python") and not _shutil.which(binary):
            add("optimizer", "fail", f"{opt}: `{binary}` is not on PATH",
                str(row.get("install_url") or f"install {binary}"))
        else:
            add("optimizer", "ok", f"{opt} ({binary or 'in-process'})")
        keys = [k.strip() for k in str(row.get("env_keys") or "").split(",") if k.strip()]
        # In agent mode the coding agent IS the optimizer and no optimizer process is spawned, so
        # its credentials are irrelevant. Warning about them there sends the user to configure a
        # key that will never be read, and a readiness check that cries wolf gets skimmed.
        if str(spec.get("orchestration_mode") or "").strip() == "agent":
            add("credentials", "ok",
                "not required: orchestration_mode agent (the driving agent is the optimizer)")
            keys = []
        if keys:
            present = [k for k in keys if os.environ.get(k)]
            if present:
                add("credentials", "ok", f"{', '.join(present)} set")
            else:
                add("credentials", "warn",
                    f"none of {', '.join(keys)} is set — {row.get('auth_notes') or ''}".strip(),
                    f"export {keys[0]}=…   # or use the CLI's own login")

    ids_file = str(spec.get("split_ids_file") or "")
    if ids_file:
        p = Path(ids_file)
        if not p.exists() and (project / ids_file).exists():
            p = project / ids_file
        if p.exists():
            add("splits", "ok", f"pinned by {p}")
        else:
            add("splits", "fail", f"split_ids_file {ids_file} not found",
                f"write {ids_file} as {{\"train\":[…],\"val\":[…],\"test\":[…]}}, "
                "or clear split_ids_file to use ratios")
    else:
        r = (spec.get("split_train"), spec.get("split_val"), spec.get("split_test"))
        add("splits", "ok", f"ratios {r[0]}/{r[1]}/{r[2]} seed {spec.get('split_seed')}")

    it = int(spec.get("max_iterations") or 0)
    if it <= 0 and not (spec.get("max_metric_calls") or spec.get("max_usd")):
        add("budget", "warn", "no cap set (max_iterations/max_metric_calls/max_usd all 0)",
            "cap-evolve estimate   # then set a cap you are willing to spend")
    else:
        add("budget", "ok", f"max_iterations {it}, max_usd {spec.get('max_usd') or 0}, "
                            f"stall {spec.get('stall') or 0}")
    return rows


def _cmd_doctor(argv) -> int:
    """Readiness check. Exit 0 when nothing FAILs, 1 otherwise."""
    import argparse
    from . import branding

    p = argparse.ArgumentParser(
        prog="cap-evolve doctor", description=branding.COMMANDS["doctor"]["summary"],
        epilog=_epilog("doctor"), formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", default=".capevolve/project")
    p.add_argument("--json", action="store_true", help="machine-readable rows on stdout")
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args(argv)

    rows = _doctor_checks(Path(args.project))
    if args.json:
        print(json.dumps({"ok": not any(r["status"] == "fail" for r in rows),
                          "checks": rows}, indent=2))
        return 0 if not any(r["status"] == "fail" for r in rows) else 1

    color = _wants_color(argv=argv)
    width = _size()
    out = branding.banner(width, color=color, lines=("", "readiness check",))
    out.append("")
    # Wrap to the terminal, with a hanging indent under the detail column. A doctor row
    # carries absolute paths and full shell commands, so unwrapped it hard-wraps at column
    # 0 mid-word and destroys the alignment that makes the table readable -- on the one
    # surface whose whole job is to be followed literally.
    def _rows(text: str, first: str, cont: str, code: str | None) -> list[str]:
        avail = max(20, width - len(cont))
        parts = textwrap.wrap(text, avail, break_long_words=False,
                              break_on_hyphens=False) or [""]
        wrapped = []
        for i, part in enumerate(parts):
            body = f"{code}{part}\033[0m" if (color and code) else part
            wrapped.append((first if i == 0 else cont) + body)
        return wrapped

    for r in rows:
        label, code = _MARK.get(r["status"], _MARK["skip"])
        mark = f"{code}{label}\033[0m" if color else label
        head = f"  {mark}  {r['name'].ljust(12)}"
        out += _rows(str(r["detail"]), head, " " * 20, None)
        if r["fix"]:
            out += _rows(str(r["fix"]), f"{'':20}→ ", " " * 22, "\033[36m")
    fails = [r for r in rows if r["status"] == "fail"]
    out.append("")
    if fails:
        out.append(f"  {len(fails)} blocking problem(s). Fix the arrows above, then "
                   "re-run `cap-evolve doctor`.")
    else:
        warns = sum(1 for r in rows if r["status"] == "warn")
        out.append(f"  ready to run{f' ({warns} warning(s))' if warns else ''}  →  "
                   "cap-evolve estimate   then   cap-evolve run --tui")
    _screen(out)
    return 1 if fails else 0


def _cmd_init(argv) -> int:
    """Scaffold ``.capevolve/project`` from ``templates/project`` and write the spec.

    Deliberately NOT a re-implementation of the ``intake`` skill: that one interviews
    you about the capability and implements the adapter. This writes the files that
    interview needs to exist, and patches the handful of spec keys that decide the run.
    """
    import argparse
    import shutil as _shutil
    from . import branding

    p = argparse.ArgumentParser(
        prog="cap-evolve init", description=branding.COMMANDS["init"]["summary"],
        epilog=_epilog("init"), formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", default=".capevolve/project")
    p.add_argument("--algorithm", default=None, choices=sorted(branding.ALGORITHMS))
    p.add_argument("--optimizer", default=None, help="optimizer name (mock for zero-API)")
    p.add_argument("--capability-path", default=None, help="dir holding the artifact to optimize")
    p.add_argument("--yes", "-y", action="store_true", help="accept defaults, ask nothing")
    p.add_argument("--force", action="store_true", help="overwrite an existing spec")
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args(argv)

    here = Path(__file__).resolve()
    template = next((q / "templates" / "project" for q in here.parents
                     if (q / "templates" / "project").is_dir()), None)
    project = Path(args.project)
    spec_path = project / "capevolve.yaml"
    color = _wants_color(argv=argv)
    out = branding.banner(_size(), color=color, lines=("", "new project",))
    _screen(out + [""])

    if spec_path.exists() and not args.force:
        _screen([f"  {spec_path} already exists — nothing written.",
                 "  → cap-evolve doctor        check it over",
                 "  → cap-evolve init --force  start from the template again"])
        return 1
    if template is None:
        _screen(["  could not find templates/project next to this install.",
                 "  → clone the repo, or copy templates/project/ by hand"])
        return 1

    def ask(prompt: str, default: str, choices=()) -> str:
        if args.yes or not sys.stdin.isatty():
            return default
        hint = f" [{'/'.join(choices)}]" if choices else ""
        try:
            got = input(f"  {prompt}{hint} ({default}): ").strip()
        except EOFError:
            return default
        if got and choices and got not in choices:
            print(f"  not one of {', '.join(choices)} — keeping {default}", file=sys.stderr)
            return default
        return got or default

    algorithm = args.algorithm or ask("algorithm", "hill-climb", tuple(branding.ALGORITHMS))
    optimizer = args.optimizer or ask("optimizer (mock = zero-API)", "mock")
    cap_path = args.capability_path or ask("capability dir (the artifact to optimize)",
                                           "seed_capability")

    project.mkdir(parents=True, exist_ok=True)
    for item in sorted(template.iterdir()):
        dst = project / item.name
        if dst.exists() and not args.force:
            continue
        if item.is_dir():
            _shutil.copytree(item, dst, dirs_exist_ok=True)
        else:
            _shutil.copy2(item, dst)

    mode = branding.ALGORITHMS[algorithm]["mode"] if algorithm in branding.ALGORITHMS \
        else "deterministic"
    text = spec_path.read_text(encoding="utf-8")
    for key, value in (("algorithm_skill", algorithm), ("optimizer_skill", optimizer),
                       ("capability_path", cap_path), ("orchestration_mode", mode)):
        text = _set_spec_key(text, key, value)
    spec_path.write_text(text, encoding="utf-8")

    workdir = project.resolve().parent.parent
    cap_dir = Path(cap_path) if Path(cap_path).is_absolute() else workdir / cap_path
    cap_dir.mkdir(parents=True, exist_ok=True)

    lines = [f"  wrote {spec_path}",
             f"        algorithm_skill: {algorithm} ({mode})",
             f"        optimizer_skill: {optimizer}",
             f"        capability_path: {cap_path}",
             f"  ready {cap_dir}/  (put the artifact to optimize here)", "",
             "  next", f"    1  edit {project / 'adapters' / 'adapter.py'}  "
                       "(4 methods: tasks, run, score, materialize)",
             "    2  cap-evolve doctor", "    3  cap-evolve run --tui"]
    _screen(lines)
    return 0


def _set_spec_key(text: str, key: str, value: str) -> str:
    """Replace ``key: …`` in a spec, preserving its trailing ``# comment``.

    Line-oriented on purpose: the spec is a hand-commented template and a YAML
    round-trip would throw every comment away. Appends the key if it is absent.
    """
    out, done = [], False
    for line in text.splitlines():
        stripped = line.lstrip()
        if not done and stripped.startswith(f"{key}:") and not stripped.startswith("#"):
            indent = line[: len(line) - len(stripped)]
            comment = ""
            body = stripped[len(key) + 1:]
            if "#" in body:
                comment = "  " + body[body.index("#"):]
            out.append(f"{indent}{key}: {value}{comment}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{key}: {value}")
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _cmd_diff(argv) -> int:
    """Show what a candidate actually changed, from its committed snapshot."""
    import argparse
    from . import branding, diffview

    p = argparse.ArgumentParser(
        prog="cap-evolve diff", description=branding.COMMANDS["diff"]["summary"],
        epilog=_epilog("diff"), formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("candidate", nargs="?", default=None,
                   help="candidate id (e.g. cand_0003); omit with --best")
    p.add_argument("--vs", default=None, metavar="OTHER",
                   help="compare against OTHER instead of the candidate's parent")
    p.add_argument("--best", action="store_true", help="seed → the winning candidate")
    p.add_argument("--run-dir", default=None, help="run dir (default: newest under --base)")
    p.add_argument("--base", default=".capevolve", help="dir containing run_* dirs")
    p.add_argument("--stat", action="store_true", help="per-file counts only")
    p.add_argument("--files", action="store_true", help="changed paths only")
    p.add_argument("--unified", type=int, default=None, metavar="N",
                   help="force unified diff with N context lines (default 3, auto layout)")
    p.add_argument("--side-by-side", action="store_true", help="force two columns")
    p.add_argument("--max-lines", type=int, default=400, help="truncate after N lines")
    p.add_argument("--color", action="store_true", help="force ANSI even when piped")
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args(argv)

    root, code = _resolve_run_dir(args.run_dir, args.base)
    if root is None:
        return code
    if not args.best and not args.candidate:
        cands = sorted(q.name for q in (root / "candidates").glob("*") if q.is_dir())
        print("name a candidate, or pass --best", file=sys.stderr)
        if cands:
            print(f"  candidates in {root}: {' '.join(cands)}", file=sys.stderr)
        print("  → cap-evolve diff --best", file=sys.stderr)
        return 2
    try:
        a_id, b_id, how = diffview.resolve_pair(root, args.candidate, vs=args.vs,
                                                best=args.best)
    except LookupError as e:
        print(str(e), file=sys.stderr)
        print("  → cap-evolve diff <candidate>   (see `cap-evolve help diff`)",
              file=sys.stderr)
        return 2

    a_dir, b_dir = root / "candidates" / a_id, root / "candidates" / b_id
    missing = [str(d) for d in (a_dir, b_dir) if not d.is_dir()]
    if missing:
        print(f"no snapshot for: {', '.join(missing)}", file=sys.stderr)
        print("  a run only has snapshots when `store` kept them "
              "(synthetic/demo logs have none)", file=sys.stderr)
        print(f"  → cap-evolve watch {root}   to see what this run did record",
              file=sys.stderr)
        return 2

    a, b = diffview.read_tree(a_dir), diffview.read_tree(b_dir)
    color = True if args.color else _wants_color(sys.stdout, argv)
    width = _size()
    head = [f"{how}   {diffview.summary_line(a, b)}", ""]
    if args.stat:
        body = diffview.render_stat(a, b, width=width, color=color)
    elif args.files:
        body = diffview.render_files(a, b, color=color)
    else:
        body = diffview.render(
            a, b, width=width, color=color,
            context=(3 if args.unified is None else max(0, args.unified)),
            side_by_side=(True if args.side_by_side
                          else (False if args.unified is not None else None)),
            max_lines=max(1, args.max_lines), labels=(a_id, b_id))
    # The diff itself is the OUTPUT of this command (redirectable), so it goes to stdout;
    # only the "which two snapshots" header is chrome.
    _screen(head)
    print("\n".join(body), flush=True)
    return 0


def _summary(name: str) -> str:
    """The one-line description for a subcommand, from the one catalog."""
    from . import branding
    return str((branding.COMMANDS.get(name) or {}).get("summary") or "")


def _epilog(name: str) -> str:
    """``examples:`` block for a subcommand's ``--help``, from the one catalog."""
    from . import branding
    meta = branding.COMMANDS.get(name) or {}
    ex = meta.get("examples") or []
    if not ex:
        return ""
    return "examples:\n" + "\n".join(f"  {e}" for e in ex)


COMMANDS = {
    "help": _cmd_help,
    "init": _cmd_init,
    "doctor": _cmd_doctor,
    "algorithms": _cmd_algorithms,
    "diff": _cmd_diff,
    "version": _cmd_version,
    "splits": _cmd_splits,
    "check": _cmd_check,
    "run": _cmd_run,
    "estimate": _cmd_estimate,
    "dashboard": _cmd_dashboard,
    "tail": _cmd_tail,
    "watch": _cmd_watch,
    "replay": _cmd_replay,
}


#: Commands with no argparse of their own — ``--help`` is served from the catalog so
#: EVERY command answers ``--help`` with the same shape.
_NO_ARGPARSE = ("version", "check", "splits", "help", "algorithms")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return _cmd_home(argv)          # branded home screen, not a one-line usage
    if argv[0] in ("-h", "--help", "help"):
        return _cmd_help(argv[1:])
    if argv[0] in ("-V", "--version"):
        return _cmd_version(argv[1:])
    fn = COMMANDS.get(argv[0])
    if fn is None:
        from . import branding
        _screen(branding.help_for(argv[0], _size(), color=_wants_color(argv=argv)))
        return 2
    if argv[0] in _NO_ARGPARSE and any(a in ("-h", "--help") for a in argv[1:]):
        return _cmd_help([argv[0]])
    return fn(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
