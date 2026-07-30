"""One source of truth for reading a run's ``events.jsonl`` stream.

``events.jsonl`` is the run's append-only audit log (see :mod:`cap_evolve.rundir`).
Every live view of a run — the dashboard's SSE route, ``cap-evolve run --follow``,
``cap-evolve tail`` — reads it through this module, so the terminal and the web UI
can never disagree about what happened.

Public API (stdlib only, no deps):

``read_new_events(path, offset) -> (events, new_offset)``
    One incremental, byte-offset read. Cheap (seeks to ``offset``); leaves a
    partial trailing line unconsumed so a half-written record is never parsed.

``follow_events(path, *, offset=0, poll=0.5, stop_kinds=("finalize",),
                idle_timeout=None, should_stop=None) -> Iterator[dict]``
    Blocking generator that yields event dicts as they are appended. Stops after
    an event whose ``kind`` is in ``stop_kinds``, after ``idle_timeout`` seconds
    with no new events, or when ``should_stop(last_event)`` returns true. The LAST
    record yielded is always a ``{"kind": "_follow_end", "reason": ...}`` sentinel
    naming *which* exit fired ("stop_kind" / "idle" / "should_stop"), so a consumer
    can tell "the run finished" from "the run went quiet" (see ``FOLLOW_END``).

``format_event(ev, totals=None, *, skip_kinds=BOOKKEEPING_KINDS) -> str | None``
    One human-readable line for an event, or ``None`` for events with nothing
    worth showing. ``totals`` is an optional caller-owned dict used to accumulate
    the live cost/token meter across events (see :func:`accrue_totals`). Pass
    ``skip_kinds=()`` to render *every* kind, including the bookkeeping ones.

``accrue_totals(ev, totals) -> None``
    Add one event's spend to ``totals``, counting each dollar exactly once (runner
    cost from ``evaluate``, optimizer cost from ``step``-likes, intake from
    ``intake``). Public so every live spend readout uses one arithmetic.

``sanitize(text) -> str``
    Strip control characters / ESC sequences and collapse newlines.

``render_line(ev, totals=None, *, color=False, **kw) -> str | None``
    :func:`format_event` plus optional ANSI styling. Styling only — text safety lives
    in :func:`format_event`, so neither entry point can return an unsafe line.

``use_color(stream) -> bool``
    The single TTY / ``NO_COLOR`` decision. ``stream`` is required.

Terminal safety: :func:`format_event` is the ONLY place event text is made
terminal-safe (see :func:`sanitize`). Event values are model/subprocess-controlled
(``optimizer_error.error`` is the optimizer CLI's own stderr), so every renderer
must go through it rather than formatting raw fields itself.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Callable, Iterator

__all__ = ["read_new_events", "follow_events", "format_event", "render_line",
           "colorize", "use_color", "sanitize", "accrue_totals",
           "liveness_facts", "classify", "describe_status",
           "FOLLOW_END", "BOOKKEEPING_KINDS", "STALL_FLOOR_SECONDS", "STALL_SLACK"]

#: ``kind`` of the sentinel :func:`follow_events` yields last. Its ``reason`` is one
#: of ``"stop_kind"`` / ``"idle"`` / ``"should_stop"``. #118 keys stall detection off
#: ``reason == "idle"``; ``format_event`` renders it as ``None`` (nothing to show).
FOLLOW_END = "_follow_end"

#: Kinds :func:`format_event` skips by default (the dashboard shows them, the
#: terminal shouldn't). Pass ``skip_kinds=()`` to see every kind — #138 needs the
#: bookkeeping ones for phase detection.
BOOKKEEPING_KINDS = ("minibatch", "optimizer_context_warning", "target_profile",
                     "seed_dir_created", "splits_warning", "gepa_resume",
                     "gepa_merge_skip", "gepa_merge_local", "skillopt_slow_eval",
                     "skillopt_slow_update")

# The one-iteration-finished events, each carrying the optimizer's own spend.
_STEP_KINDS = ("step", "gepa_val_gate", "skillopt_step")


def read_new_events(path: Path, offset: int) -> tuple[list[dict], int]:
    """Return (new events, new byte offset). A partial trailing line (no newline)
    is left unconsumed so the next read picks it up once complete.

    Only JSON *objects* are returned: a bare ``42``/``null``/``[1,2]`` record parses
    fine but every consumer (CLI renderer, dashboard SSE route) treats events as
    dicts, so non-dicts are dropped at the source rather than at each caller.
    """
    p = Path(path)
    if not p.exists():
        return [], offset
    size = p.stat().st_size
    if size < offset:
        offset = 0  # file shrank (truncate/rewrite/rotation) → re-read from the top
    if offset >= size:
        return [], offset
    # Seek-and-read so each poll costs O(new bytes), not O(file size) — callers poll
    # a growing events.jsonl twice a second, per client.
    with p.open("rb") as fh:
        fh.seek(offset)
        chunk = fh.read()
    last_nl = chunk.rfind(b"\n")
    if last_nl == -1:
        return [], offset  # only a partial line so far
    complete = chunk[: last_nl + 1]
    events, dropped = [], 0
    for line in complete.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            dropped += 1
            continue
        if isinstance(obj, dict):
            events.append(obj)
        else:
            dropped += 1  # a bare 42/null/[1,2] is not an event
    if dropped:
        # Don't silently lose audit-log records: surface the count as an event so both
        # the terminal and the dashboard see that the log has damage.
        events.append({"kind": "log_corruption", "dropped": dropped})
    return events, offset + last_nl + 1


def follow_events(
    path: Path,
    *,
    offset: int = 0,
    poll: float = 0.5,
    stop_kinds: tuple[str, ...] = ("finalize",),
    idle_timeout: float | None = None,
    should_stop: Callable[[dict | None], bool] | None = None,
) -> Iterator[dict]:
    """Yield events from ``path`` as they are appended (blocking generator).

    ``offset=0`` replays the whole file first, then follows. Waits for the file to
    appear, so a follower can attach before the run creates it.

    The final record yielded is ALWAYS a ``{"kind": FOLLOW_END, "reason": r}``
    sentinel where ``r`` is:

    ``"stop_kind"``   an event whose ``kind`` is in ``stop_kinds`` arrived (run ended)
    ``"idle"``        ``idle_timeout`` seconds passed with no new event (possible stall)
    ``"should_stop"`` the caller's ``should_stop`` returned true

    so a consumer can distinguish "done" from "quiet" (#118). ``should_stop`` is
    called with the last event seen (``None`` before any), so a stall rule can look
    at its ``t`` without running a second poller. ``idle_timeout=None`` (the default)
    means wait forever — each caller owns its own threshold; there is deliberately no
    module-level default, because a shared one would pre-decide #118's configurable
    stall threshold for every consumer.
    """
    idle_start = time.monotonic()
    last: dict | None = None
    while True:
        events, offset = read_new_events(path, offset)
        for ev in events:
            last = ev
            yield ev
            if ev.get("kind") in stop_kinds:
                yield {"kind": FOLLOW_END, "reason": "stop_kind", "last_kind": ev.get("kind")}
                return
        if events:
            idle_start = time.monotonic()
        elif idle_timeout is not None and time.monotonic() - idle_start >= idle_timeout:
            yield {"kind": FOLLOW_END, "reason": "idle", "idle_seconds": idle_timeout}
            return
        if should_stop is not None and should_stop(last):
            # Drain whatever landed between the last read and the stop signal, so the
            # final events of a finished run are never lost to a race.
            for ev in read_new_events(path, offset)[0]:
                yield ev
            yield {"kind": FOLLOW_END, "reason": "should_stop"}
            return
        time.sleep(poll)


# ---- human-readable rendering ----------------------------------------------

def use_color(stream) -> bool:
    """True only on a real TTY without ``NO_COLOR``. Piped/CI output stays plain.

    ``stream`` is required: the decision must be made about the stream the caller
    actually writes to, never a default that could colorize stderr based on stdout.
    """
    if os.environ.get("NO_COLOR"):
        return False
    try:
        return bool(stream.isatty())
    except Exception:  # noqa: BLE001 — a stub stream without isatty is "not a tty"
        return False


_CODES = {"dim": "2", "bold": "1", "green": "32", "red": "31", "yellow": "33", "cyan": "36"}


def colorize(text: str, style: str, *, enabled: bool) -> str:
    if not enabled or style not in _CODES:
        return text
    return f"\033[{_CODES[style]}m{text}\033[0m"


# Every C0 control char (except TAB) and every C1 control char, mapped away. Event
# values are model/subprocess-controlled — `optimizer_error.error` is the optimizer
# CLI's own stderr — so an ESC/OSC/CSI sequence in a payload would otherwise reach the
# terminal verbatim (set window title, clear screen, OSC 52 clipboard write), and a
# raw "\n" would forge an extra progress line ("FINALIZE test=1.0 …") for a run that
# never finished. Newlines/CRs collapse to a visible "⏎" rather than vanishing, so a
# multi-line optimizer error is still legible on one line.
_CTRL = {c: None for c in range(0x20) if c != 0x09}
_CTRL[0x7F] = None                       # DEL
_CTRL.update({c: None for c in range(0x80, 0xA0)})  # C1, incl. 0x9B (8-bit CSI)
_CTRL[0x0A] = _CTRL[0x0D] = "⏎"


def sanitize(text: str) -> str:
    """Strip control characters / ESC sequences so no event value can drive the
    terminal or forge extra output lines. Applied by :func:`format_event` to the
    whole finished line, so every field and every future event kind is covered."""
    return str(text).translate(_CTRL)


def _num(v, fmt="{:.4f}") -> str:
    try:
        return fmt.format(float(v))
    except (TypeError, ValueError):
        return "?"


def _meter(totals: dict | None) -> str:
    """`  [$0.0123 · 4.2k tok]` — the live cost meter, or '' if nothing spent yet."""
    if not totals:
        return ""
    usd, tok = totals.get("usd", 0.0), totals.get("tokens", 0)
    if not usd and not tok:
        return ""
    tokens = f"{tok / 1000:.1f}k" if tok >= 1000 else str(tok)
    return f"  [${usd:.4f} · {tokens} tok]"


def accrue_totals(ev: dict, totals: dict | None) -> None:
    """Accumulate the run's spend into ``totals`` (``{"usd","tokens"}``), counting
    each dollar exactly once. Public so every live readout (terminal meter, #138's
    dashboard burn line) uses one arithmetic instead of forking it.

    The harness reports the SAME runner spend twice: ``evaluate`` logs
    ``cost_usd``/``tokens`` (``harness.py:311``) and the following ``step`` re-states
    it alongside the optimizer's own ``opt_cost_usd``/``opt_tokens``
    (``harness.py:1326``). So the authoritative sources are:

    * runner spend    → ``evaluate`` only  (``cost_usd`` / ``tokens``)
    * optimizer spend → ``step``-like only (``opt_cost_usd`` / ``opt_tokens``)
    * intake spend    → ``intake`` only    (``usd`` / ``tokens``)

    which reproduces ``Spent.total_usd = usd + optimizer_usd + intake_usd``
    (``rundir.py:137``). Summing every cost-ish key on every event double-counted the
    runner and displayed ~2x the real spend.
    """
    if totals is None or not isinstance(ev, dict):
        return
    kind = str(ev.get("kind") or "")
    if kind == "evaluate":
        pairs = (("cost_usd", "tokens"),)
    elif kind in _STEP_KINDS:
        pairs = (("opt_cost_usd", "opt_tokens"),)
    elif kind == "intake":
        pairs = (("usd", "tokens"),)
    else:
        return
    for usd_key, tok_key in pairs:
        try:
            totals["usd"] = totals.get("usd", 0.0) + float(ev.get(usd_key) or 0.0)
        except (TypeError, ValueError):
            pass
        try:
            totals["tokens"] = totals.get("tokens", 0) + int(ev.get(tok_key) or 0)
        except (TypeError, ValueError):
            pass



def _timestamp(v) -> str:
    """``HH:MM:SS`` for an event's ``t``, or ``--:--:--`` for a malformed one.

    ``rundir.log_event`` serialises with ``json.dumps(..., default=str)``, so a ``t``
    that is a string / dict / out-of-range float is reachable in a real log. It must
    never raise: one bad record used to kill the follower thread and take the rest of
    the run's live output with it, which is the exact silence #116 exists to fix.
    """
    try:
        return time.strftime("%H:%M:%S", time.localtime(float(v if v else time.time())))
    except (TypeError, ValueError, OverflowError, OSError):
        return "--:--:--"


def format_event(ev: dict, totals: dict | None = None, *,
                 skip_kinds: tuple[str, ...] = BOOKKEEPING_KINDS) -> str | None:
    """Render one event as a single terminal line, or ``None`` to skip it.

    Total function: any malformed record (non-dict, bad ``t``, hostile string) yields
    ``None`` or a safe line, never an exception — a renderer that raises silences the
    whole run. Never emits ANSI, and no event value can: the finished line is run
    through :func:`sanitize`, so color is only ever added by :func:`render_line`.

    ``skip_kinds`` defaults to :data:`BOOKKEEPING_KINDS`; pass ``()`` to render every
    kind (what #138 needs for phase detection).
    """
    if not isinstance(ev, dict):
        return None
    kind = str(ev.get("kind") or "")
    if kind in skip_kinds or kind == FOLLOW_END:
        return None  # bookkeeping / noise — the dashboard shows these, the terminal shouldn't
    accrue_totals(ev, totals)
    ts = _timestamp(ev.get("t"))
    meter = _meter(totals)

    if kind == "splits":
        body = (f"splits frozen  train={ev.get('train')} val={ev.get('val')} "
                f"test={ev.get('test')} (test sealed)")
    elif kind == "baseline":
        body = f"baseline  val={_num(ev.get('val'))} ±{_num(ev.get('stderr'))}"
    elif kind == "baseline_reused":
        body = f"baseline reused from {ev.get('prior') or ev.get('from') or '?'}"
    elif kind in _STEP_KINDS:
        ok = bool(ev.get("accept"))
        verdict = "ACCEPT" if ok else "reject"
        where = ""
        if kind == "skillopt_step":
            where = f" e{ev.get('epoch')}s{ev.get('step_in_epoch')}"
        body = (f"{verdict}{where}  {ev.get('candidate')}  val={_num(ev.get('val'))}"
                f" (parent {_num(ev.get('parent_val'))})")
        if ev.get("reason"):
            body += f"  — {ev['reason']}"
    elif kind == "gepa_local_gate":
        body = (f"minibatch gate {'pass' if ev.get('passed') else 'fail'}  {ev.get('candidate')}"
                f"  child={_num(ev.get('child_sum'), '{:.3f}')}"
                f" parent={_num(ev.get('parent_sum'), '{:.3f}')}")
    elif kind == "gepa_select":
        body = f"selected parent {ev.get('parent')} ({ev.get('strategy')})"
    elif kind in ("gepa_start", "skillopt_start"):
        body = f"{kind.split('_')[0]} started  " + " ".join(
            f"{k}={v}" for k, v in ev.items() if k not in ("t", "kind"))
    elif kind == "gepa_stop":
        body = f"gepa stopped: {ev.get('reason')}"
    elif kind == "evaluate":
        body = (f"eval {ev.get('split')}/{ev.get('tag')}  reward={_num(ev.get('reward'))}"
                f" ±{_num(ev.get('stderr'))}  {_num(ev.get('seconds'), '{:.1f}')}s")
    elif kind == "gate_warning":
        body = f"gate warning ({ev.get('mode')}): {str(ev.get('reason')).split(' — ')[0]}"
    elif kind == "budget_warning":
        body = (f"BUDGET {ev.get('pct')}% of {ev.get('metric')}  "
                f"{ev.get('spent')}/{ev.get('limit')}")
    elif kind == "optimizer_error":
        body = f"OPTIMIZER ERROR  {ev.get('candidate')}: {str(ev.get('error'))[:200]}"
    elif kind == "finalize":
        body = (f"FINALIZE  test={_num(ev.get('test_reward'))} "
                f"(baseline {_num(ev.get('test_baseline_reward'))}, "
                f"Δ{_num(ev.get('test_delta'), '{:+.4f}')})  best={ev.get('best_id')}")
    elif kind == "intake":
        body = f"intake  ${_num(ev.get('usd'), '{:.4f}')}  {ev.get('output_summary') or ''}".rstrip()
    elif kind == "log_corruption":
        body = f"WARNING  {ev.get('dropped')} unreadable record(s) skipped in events.jsonl"
    else:
        # Unknown kind: still show it rather than hide progress from a new event type.
        extra = " ".join(f"{k}={v}" for k, v in ev.items() if k not in ("t", "kind"))
        body = f"{kind} {extra}".strip()
    # Sanitize the FINISHED line, once: every field of every kind (present and future)
    # is covered, so no event value can emit an escape sequence or forge an extra line.
    return sanitize(f"[{ts}] {body}{meter}")


_STYLE_BY_KIND = {"optimizer_error": "red", "budget_warning": "yellow",
                  "log_corruption": "yellow",
                  "finalize": "bold", "baseline": "cyan"}


def render_line(ev: dict, totals: dict | None = None, *, color: bool = False,
                **kw) -> str | None:
    """:func:`format_event` plus optional ANSI styling (accept green / reject dim).

    Styling only — all text safety lives in :func:`format_event`, so a caller can
    never get an unsanitised line by choosing one of these two over the other.
    ``**kw`` (e.g. ``skip_kinds``) is passed through to :func:`format_event`.
    """
    line = format_event(ev, totals, **kw)
    if line is None or not color:
        return line
    kind = str(ev.get("kind") or "")
    style = _STYLE_BY_KIND.get(kind)
    if kind in _STEP_KINDS:
        style = "green" if ev.get("accept") else "dim"
    return colorize(line, style, enabled=True) if style else line


# ---- is it working, stalled, crashed, or done? ------------------------------
#
# The hard part is NOT noticing silence — it is deciding how much silence is
# abnormal. A fixed 5-minute idle timeout is wrong in both directions: a toy run
# is silent for 5 minutes only if it is dead, while one τ²-bench rollout with
# 50 tool calls can legitimately take 20 minutes, so a constant would report a
# healthy expensive run as hung. A false "hung" is the worst outcome available
# here, because the user's reaction is to kill a run that was working.
#
# So the expectation is derived from THE SAME RUN: the bar is the slowest gap the
# run has already demonstrated, times a slack factor, floored. The bar therefore
# only ever rises as a run proves itself slow, and the run that sets it is the run
# judged by it — a workload that takes 20 minutes per step raises its own bar to
# an hour instead of tripping a global constant.

#: Never call a run stalled before this much silence, however fast its events have
#: been. Keeps a run that produced two events 40ms apart from being declared hung
#: 120ms later. 300s is the old hard-coded SSE idle close (#118) — demoted from
#: "the rule" to "the floor".
STALL_FLOOR_SECONDS = 300.0

#: Multiplier on the slowest gap the run has already shown. 3x is deliberately
#: generous: the cost of waiting is a slightly late warning, the cost of being
#: wrong is a killed run.
STALL_SLACK = 3.0

#: Env override for the derived threshold: a fixed number of seconds, for a user who
#: knows their workload better than the heuristic does. ``0``/unset = derive.
STALL_ENV = "CAPEVOLVE_STALL_SECONDS"


def _pid_alive(pid, host) -> bool | None:
    """True / False / ``None`` when it cannot be known.

    ``None`` (unknown) is a first-class answer and the reason this never guesses:
    a run recorded on another machine, or a pid file we can't parse, must NOT be
    reported crashed. Only a definite "this pid is gone" produces ``False``.

    ponytail: pid-only liveness, so a recycled pid could read as alive. The window
    needs ~32k intervening spawns plus the same host, and the failure direction is
    the safe one (a dead run looks quiet, not a live run looking dead). Upgrade to
    a pid+start-time pair if that ever matters.
    """
    import socket
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    if host and str(host) != socket.gethostname():
        return None  # someone else's machine — we cannot see its process table
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by another user
    except OSError:
        return None
    return True


def _owner_alive(root: Path) -> bool | None:
    """Read ``run.pid`` (written by ``cap-evolve run``) and probe the owner.

    ``None`` when there is no pid file at all: the per-phase skill-chain workflow
    (``/cap-evolve:baseline`` … ) has no single long-lived owner, so its runs get the
    time-based verdict only and are never labelled crashed.
    """
    try:
        info = json.loads((Path(root) / "run.pid").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(info, dict):
        return None
    return _pid_alive(info.get("pid"), info.get("host"))


def stall_threshold(gaps) -> float:
    """Seconds of silence that count as abnormal, derived from ``gaps`` (the run's own
    observed inter-event intervals). ``max(floor, slack * slowest_gap_so_far)``.

    ``max`` rather than a mean/quantile on purpose: a run that alternates 1s evals with
    20-minute optimizer calls has a mean of a couple of minutes, so a mean-based bar
    would fire during every optimizer call. The slowest thing the run has already done
    is the only defensible estimate of the slowest thing it might do next.
    """
    override = os.environ.get(STALL_ENV)
    if override:
        try:
            fixed = float(override)
            if fixed > 0:
                return fixed
        except ValueError:
            pass
    slowest = max(gaps, default=0.0)
    return max(STALL_FLOOR_SECONDS, STALL_SLACK * slowest)


def liveness_facts(root, *, events=None, now=None) -> dict:
    """Everything :func:`classify` needs, gathered from a run dir. Cheap: one
    ``stat`` plus (unless ``events`` is supplied) one read of ``events.jsonl``.

    ``events`` lets a caller that already has the parsed log — the dashboard reducer
    does — avoid a second read.

    Silence is measured from the events file's **mtime**, not the last event's ``t``:
    ``t`` is wall-clock recorded by the writer and can be skewed or malformed, while
    mtime is the filesystem's own answer to "when did this run last make a noise".
    """
    root = Path(root)
    path = root / "events.jsonl"
    now = time.time() if now is None else now
    if events is None:
        events, _ = read_new_events(path, 0)
    ts = []
    finalized = False
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if ev.get("kind") == "finalize":
            finalized = True
        try:
            ts.append(float(ev.get("t")))
        except (TypeError, ValueError):
            continue
    ts.sort()
    gaps = [b - a for a, b in zip(ts, ts[1:]) if b >= a]
    try:
        silence = max(0.0, now - path.stat().st_mtime)
    except OSError:
        silence = None  # no events file yet — the run hasn't spoken at all
    return {"silence": silence, "threshold": stall_threshold(gaps),
            "slowest_gap": max(gaps, default=0.0), "events": len(ts),
            "finalized": finalized, "alive": _owner_alive(root)}


def classify(facts: dict) -> str:
    """One of ``"done"`` / ``"crashed"`` / ``"stalled"`` / ``"live"``.

    Order matters, and it is the whole design:

    ``done``     ``finalize`` sealed the test. Terminal state; nothing about silence
                 or a departed process can downgrade it, so a finished run degrades
                 to a clean "done" rather than "its process is gone → crashed".
    ``crashed``  the owning process is *definitely* gone and the run never finalized.
                 Needs proof (a pid file naming a pid on this host that no longer
                 exists) — ``alive is None`` never reaches this branch.
    ``stalled``  silent for longer than the run's own derived expectation, while its
                 process is still alive or unknown. "Alive but not talking."
    ``live``     everything else, including long silences that are still within what
                 this run has already shown itself capable of.
    """
    if facts.get("finalized"):
        return "done"
    if facts.get("alive") is False:
        return "crashed"
    silence, threshold = facts.get("silence"), facts.get("threshold") or STALL_FLOOR_SECONDS
    if silence is not None and silence > threshold:
        return "stalled"
    return "live"


def _mins(s) -> str:
    if s is None:
        return "?"
    return f"{s / 60:.1f}m" if s >= 60 else f"{s:.0f}s"


def describe_status(facts: dict) -> str:
    """One human sentence for the terminal, always naming the numbers behind the
    verdict — a user deciding whether to kill a run needs the bar, not just the word."""
    status = classify(facts)
    silence, thr = facts.get("silence"), facts.get("threshold")
    bar = (f"threshold {_mins(thr)}"
           + (f", derived from a slowest gap of {_mins(facts.get('slowest_gap'))}"
              if (facts.get("slowest_gap") or 0) * STALL_SLACK > STALL_FLOOR_SECONDS else
              " (floor)"))
    if status == "done":
        return "done — finalize sealed the test split"
    if status == "crashed":
        return (f"CRASHED — the process that owned this run is gone and it never "
                f"finalized (last event {_mins(silence)} ago)")
    if status == "stalled":
        return (f"STALLED — no events for {_mins(silence)}, over this run's own "
                f"{bar}. The process is "
                + ("still alive" if facts.get("alive") else "not reporting a pid")
                + " — it may be wedged rather than dead.")
    return (f"working — last event {_mins(silence)} ago, within this run's {bar}")
