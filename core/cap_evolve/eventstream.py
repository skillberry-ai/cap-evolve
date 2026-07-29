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
                idle_timeout=300.0, should_stop=None) -> Iterator[dict]``
    Blocking generator that yields event dicts as they are appended. Stops after
    an event whose ``kind`` is in ``stop_kinds``, after ``idle_timeout`` seconds
    with no new events, or when ``should_stop()`` returns true.

``format_event(ev, totals=None) -> str | None``
    One human-readable line for an event, or ``None`` for events with nothing
    worth showing. ``totals`` is an optional caller-owned dict used to accumulate
    the live cost/token meter across events.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Callable, Iterator

__all__ = ["read_new_events", "follow_events", "format_event", "render_line",
           "colorize", "use_color"]


def read_new_events(path: Path, offset: int) -> tuple[list[dict], int]:
    """Return (new events, new byte offset). A partial trailing line (no newline)
    is left unconsumed so the next read picks it up once complete."""
    p = Path(path)
    if not p.exists():
        return [], offset
    if offset >= p.stat().st_size:
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
    events = []
    for line in complete.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events, offset + last_nl + 1


def follow_events(
    path: Path,
    *,
    offset: int = 0,
    poll: float = 0.5,
    stop_kinds: tuple[str, ...] = ("finalize",),
    idle_timeout: float | None = 300.0,
    should_stop: Callable[[], bool] | None = None,
) -> Iterator[dict]:
    """Yield events from ``path`` as they are appended (blocking generator).

    ``offset=0`` replays the whole file first, then follows. Waits for the file to
    appear, so a follower can attach before the run creates it. ``idle_timeout=None``
    means wait forever.
    """
    idle_start = time.monotonic()
    while True:
        events, offset = read_new_events(path, offset)
        for ev in events:
            yield ev
            if ev.get("kind") in stop_kinds:
                return
        if events:
            idle_start = time.monotonic()
        elif idle_timeout is not None and time.monotonic() - idle_start >= idle_timeout:
            return
        if should_stop is not None and should_stop():
            # Drain whatever landed between the last read and the stop signal, so the
            # final events of a finished run are never lost to a race.
            for ev in read_new_events(path, offset)[0]:
                yield ev
            return
        time.sleep(poll)


# ---- human-readable rendering ----------------------------------------------

def use_color(stream=None) -> bool:
    """True only on a real TTY without ``NO_COLOR``. Piped/CI output stays plain."""
    stream = stream or sys.stdout
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


def _accrue(ev: dict, totals: dict | None) -> None:
    if totals is None:
        return
    for k in ("cost_usd", "opt_cost_usd", "usd"):
        try:
            totals["usd"] = totals.get("usd", 0.0) + float(ev.get(k) or 0.0)
        except (TypeError, ValueError):
            pass
    for k in ("tokens", "opt_tokens"):
        try:
            totals["tokens"] = totals.get("tokens", 0) + int(ev.get(k) or 0)
        except (TypeError, ValueError):
            pass


def format_event(ev: dict, totals: dict | None = None) -> str | None:
    """Render one event as a single terminal line, or ``None`` to skip it.

    Never emits ANSI: color is layered on by :func:`render_line`, so the piped /
    no-TTY path is plain text by construction.
    """
    kind = str(ev.get("kind") or "")
    _accrue(ev, totals)
    ts = time.strftime("%H:%M:%S", time.localtime(float(ev.get("t") or time.time())))
    meter = _meter(totals)

    if kind == "splits":
        body = (f"splits frozen  train={ev.get('train')} val={ev.get('val')} "
                f"test={ev.get('test')} (test sealed)")
    elif kind == "baseline":
        body = f"baseline  val={_num(ev.get('val'))} ±{_num(ev.get('stderr'))}"
    elif kind == "baseline_reused":
        body = f"baseline reused from {ev.get('prior') or ev.get('from') or '?'}"
    elif kind in ("step", "gepa_val_gate", "skillopt_step"):
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
    elif kind in ("minibatch", "optimizer_context_warning", "target_profile",
                  "seed_dir_created", "splits_warning", "gepa_resume",
                  "gepa_merge_skip", "gepa_merge_local", "skillopt_slow_eval",
                  "skillopt_slow_update"):
        return None  # bookkeeping / noise — the dashboard shows these, the terminal shouldn't
    else:
        # Unknown kind: still show it rather than hide progress from a new event type.
        extra = " ".join(f"{k}={v}" for k, v in ev.items() if k not in ("t", "kind"))
        body = f"{kind} {extra}".strip()
    return f"[{ts}] {body}{meter}"


_STYLE_BY_KIND = {"optimizer_error": "red", "budget_warning": "yellow",
                  "finalize": "bold", "baseline": "cyan"}


def render_line(ev: dict, totals: dict | None = None, *, color: bool = False) -> str | None:
    """:func:`format_event` plus optional ANSI styling (accept green / reject dim)."""
    line = format_event(ev, totals)
    if line is None or not color:
        return line
    kind = str(ev.get("kind") or "")
    style = _STYLE_BY_KIND.get(kind)
    if kind in ("step", "gepa_val_gate", "skillopt_step"):
        style = "green" if ev.get("accept") else "dim"
    return colorize(line, style, enabled=True) if style else line
