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
           "FOLLOW_END", "BOOKKEEPING_KINDS"]

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
                     "skillopt_slow_update", "skillopt_step")

# The one-iteration-finished event, carrying the optimizer's own spend. Exactly ONE
# kind: every algorithm writes it via ``harness.record_iteration`` (#216/#224).
# ``gepa_val_gate`` is no longer emitted at all, and ``skillopt_step`` is auxiliary
# epoch detail that duplicated the same candidate's row — it is skipped in the terminal
# via BOOKKEEPING_KINDS above (the dashboard still shows it).
_STEP_KINDS = ("step",)


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

def crop_ansi(line: str, width: int) -> str:
    """Crop to ``width`` VISIBLE columns, counting no ANSI escape as a column.

    Pre-styled text cannot be sliced plainly: the slice can cut mid-escape and (worse)
    leave a line wider than the terminal. One wrapped line breaks the live view's inline
    repaint arithmetic, and on the home screen it wraps the command table.
    """
    out, used, i = [], 0, 0
    try:
        width = max(0, int(width))
    except (TypeError, ValueError):
        return line
    while i < len(line) and used < width:
        ch = line[i]
        if ch == "\x1b":
            j = i + 1
            if j < len(line) and line[j] == "[":
                j += 1
                while j < len(line) and not line[j].isalpha():
                    j += 1
            out.append(line[i: j + 1])
            i = j + 1
            continue
        out.append(ch)
        used += 1
        i += 1
    if "\x1b" in line:
        out.append("\x1b[0m")   # close any style the crop cut off from its reset
    return "".join(out)


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
        body = (f"{verdict}  {ev.get('candidate')}  val={_num(ev.get('val'))}"
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
