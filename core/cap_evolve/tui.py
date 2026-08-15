"""Live full-screen-ish terminal view of a cap-evolve run. Stdlib only.

The whole design is one sentence: **the renderer is a pure function of one state
object and nothing else.**

    events.jsonl → dashboard.reduce_run() → render_frame(reduced, size) -> str → terminal

:func:`render_frame` touches no terminal, no clock and no filesystem, so it is unit
testable without a TTY, and ``watch`` (live) and ``replay`` (recorded) differ ONLY in
what feeds events into the same reducer + renderer.

Public API:

``render_frame(reduced, size, ...) -> str``
    The pure renderer. Never raises: a malformed/absent key degrades to a
    placeholder line, because a renderer that throws silences the run.

``plan_section_sizes(avail_rows, ...) -> dict[str, int]``
    The height budget. ``sum(sizes.values()) <= avail_rows`` always holds — that
    invariant is what stops an inline repaint from duplicating frames.

``watch(root, ...) -> str | None``
    Attach to a run dir (running or finished). Returns the ``follow_events``
    FOLLOW_END reason ("stop_kind" / "idle" / ...) so the CLI can pick an exit code.

``replay(src, ...) -> None``
    Re-feed a recorded ``events.jsonl`` through the same renderer at N× speed.

``DEMO_DIR``
    The committed, keyless demo session (synthetic numbers — see ``replay --demo``).

Repaint model: inline cursor-up + clear-to-end, never the alternate screen, so
scrollback (CI logs, screen recordings) survives. Frames are cropped to the terminal
height rather than wrapped. On a non-TTY the full-screen path is skipped entirely in
favour of the line-oriented :func:`eventstream.render_line` stream.

All event-derived text passes through :func:`eventstream.sanitize` — event values are
model/subprocess-controlled and that is this codebase's terminal-injection defense.
"""

from __future__ import annotations

import json
import shutil
import signal
import sys
import time
from collections import deque
from pathlib import Path

from . import eventstream
from .dashboard import _C, _term_width, reduce_run

__all__ = ["render_frame", "plan_section_sizes", "watch", "replay", "DEMO_DIR",
           "terminal_size"]

#: The committed keyless demo session (see ``scripts/generate_demo_session.py``).
DEMO_DIR = Path(__file__).resolve().parent / "demo_session"

#: The honesty banner for ``replay --demo``. The demo numbers are hand-authored, so
#: this text is a product requirement, not decoration: it must accompany every
#: replay of the sample so a viewer can never read it as a benchmark claim.
DEMO_BANNER = ("illustrative sample — replays the cap-evolve UI with no API key. "
               "The numbers are synthetic and make no benchmark claim.")

# ---- one glyph/style table, defined once ------------------------------------

#: status → (glyph, ANSI code from dashboard._C). ``~`` is an *indecisive* step:
#: the gate could not tell signal from noise, which is neither accept nor reject.
GLYPHS = {
    "seed":       ("○", _C.GREY),
    "queued":     ("○", _C.GREY),
    "running":    ("▶", _C.CYAN),
    "accepted":   ("✓", _C.GREEN),
    "rejected":   ("✗", _C.YELLOW),
    "indecisive": ("~", _C.BLUE),
    "failed":     ("!", _C.RED),
    "best":       ("★", _C.BOLD),
}

_SPARK = "▁▂▃▄▅▆▇█"
_SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

#: cap-evolve's real pipeline, in order. The lit stage is derived from the reduced run.
PHASES = ("intake", "check", "baseline", "optimize", "finalize", "report")

# Height budget. (name, min, max) in PRIORITY order — under pressure the earlier
# sections keep their rows and the later ones collapse to zero.
_SECTIONS = (
    ("header", 1, 6),
    ("footer", 1, 2),
    ("tree", 3, 40),
    ("activity", 1, 6),
    ("chart", 7, 12),
)
# Growth order once every section has its minimum: give spare rows to the panels
# that carry information density before letting the chart stretch.
_GROW = ("header", "footer", "activity", "tree", "chart")


# ---- small formatters -------------------------------------------------------

def _sparkline(values) -> str:
    vals = [float(v) for v in (values or []) if isinstance(v, (int, float))]
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    return "".join(_SPARK[min(len(_SPARK) - 1,
                              int((v - lo) / span * (len(_SPARK) - 1)))] for v in vals)


def _spinner() -> str:
    """One frame of a spinner, derived from the monotonic clock (needs no state)."""
    return _SPIN[int(time.monotonic() * 8) % len(_SPIN)]


def _fmt_tokens(n) -> str:
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return "?"
    if n >= 1_000_000:
        return f"{n / 1e6:.1f}M"
    if n >= 1000:
        return f"{n / 1e3:.1f}k"
    return str(n)


def _fmt_dur(seconds) -> str:
    """``43s`` / ``7m03s`` / ``1h02m03s``."""
    try:
        s = int(max(0.0, float(seconds or 0.0)))
    except (TypeError, ValueError):
        return "—"
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m{s:02d}s"


def _fmt_val(v, nd: int = 3) -> str:
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_signed(v, nd: int = 3) -> str:
    try:
        return f"{float(v):+.{nd}f}"
    except (TypeError, ValueError):
        return "—"


def terminal_size(stream=None, default=(100, 30)) -> tuple[int, int]:
    """(cols, rows) for the frame, CLAUDECODE-margin-aware via ``dashboard._term_width``."""
    try:
        rows = shutil.get_terminal_size((default[0], default[1])).lines
    except OSError:
        rows = default[1]
    return _term_width(default[0]), max(4, rows)


# ---- height budget (the correctness-critical bit) ---------------------------

def plan_section_sizes(avail_rows: int, *, has_chart: bool = True, has_tree: bool = True,
                       has_activity: bool = True, tree_rows: int | None = None) -> dict[str, int]:
    """Row allocation whose sum NEVER exceeds ``avail_rows``.

    Minimums are granted in :data:`_SECTIONS` priority order (a section starved by a
    tiny terminal gets 0 rows and is simply not drawn), then spare rows are handed out
    in :data:`_GROW` order up to each section's maximum. ``tree_rows`` caps the lineage
    panel at the number of rows it actually has, so spare space reaches the chart.

    This is the invariant that keeps an inline repaint honest: emit one row more than
    the terminal has and the previous frame scrolls out of reach of the cursor-up,
    leaving a duplicated half-frame on screen.
    """
    want = {"header": True, "footer": True, "tree": has_tree,
            "activity": has_activity, "chart": has_chart}
    out = {name: 0 for name, _, _ in _SECTIONS}
    try:
        left = max(0, int(avail_rows))
    except (TypeError, ValueError):
        left = 0
    for name, lo, _hi in _SECTIONS:
        if not want[name] or left <= 0:
            continue
        take = min(lo, left)
        out[name], left = take, left - take
    for name in _GROW:
        if left <= 0:
            break
        if out[name] == 0:
            continue  # starved above; don't resurrect a section the budget rejected
        hi = next(h for n, _lo, h in _SECTIONS if n == name)
        if name == "tree" and tree_rows is not None:
            hi = min(hi, max(1, int(tree_rows)))
        grow = min(max(0, hi - out[name]), left)
        out[name], left = out[name] + grow, left - grow
    return out


# ---- line assembly ---------------------------------------------------------

def _c(text: str, style: str | None, color: bool) -> str:
    return f"{style}{text}{_C.RESET}" if (color and style) else text


def _fit(cells, width: int, color: bool) -> str:
    """Join (text, style) cells, cropping to ``width`` VISIBLE columns.

    Cropping happens on the plain text before any ANSI is added, so a truncated line
    can never end mid-escape-sequence.
    """
    out, used = [], 0
    for text, style in cells:
        if used >= width:
            break
        t = str(text)[: max(0, width - used)]
        if not t:
            continue
        used += len(t)
        out.append(_c(t, style, color))
    return "".join(out)


def _pad(lines: list[str], n: int) -> list[str]:
    """Exactly ``n`` lines: crop the overflow, pad the shortfall with blanks."""
    if n <= 0:
        return []
    return (lines[:n] + [""] * n)[:n]


def _phase(summary: dict) -> str:
    if summary.get("test_reward") is not None:
        return "report" if summary.get("test_sealed") else "finalize"
    if (summary.get("counts") or {}).get("total", 0) > 1 or summary.get("per_iteration"):
        return "optimize"
    if summary.get("baseline_val") is not None:
        return "baseline"
    if (summary.get("intake") or {}).get("usd"):
        return "intake"
    return "check"


def _breadcrumb(current: str, color: bool) -> str:
    cells = []
    for i, name in enumerate(PHASES):
        if i:
            cells.append((" › ", _C.GREY))
        if name == current:
            cells.append((name, _C.BOLD + _C.CYAN))
        else:
            cells.append((name, _C.GREY))
    return _fit(cells, 200, color)


def _header(summary: dict, graph: dict, width: int, *, color: bool, totals: dict | None,
            elapsed: float | None, n: int) -> list[str]:
    counts = summary.get("counts") or {}
    nodes = [x for x in (graph.get("nodes") or []) if (x.get("iteration") or 0) > 0]
    best_series = [x.get("best_so_far") for x in
                   sorted(nodes, key=lambda x: x.get("iteration") or 0)
                   if x.get("best_so_far") is not None]
    indecisive = sum(1 for x in nodes if "indecisive" in str(x.get("reason") or "").lower())
    usd = (summary.get("cost") or {}).get("total_usd") or 0.0
    tok = summary.get("tokens") or 0
    if totals:  # live accrual can be ahead of the projection mid-iteration
        usd = max(float(usd or 0.0), float(totals.get("usd") or 0.0))
        tok = max(int(tok or 0), int(totals.get("tokens") or 0))
    if elapsed is None:
        elapsed = summary.get("wall_clock_seconds") or 0.0
    model = (summary.get("target_profile") or {}).get("model") or ""
    budget = summary.get("budget") or {}
    max_it = budget.get("max_iterations") or 0
    it = len(summary.get("per_iteration") or [])

    title = [("cap-evolve", _C.BOLD), (" · ", _C.GREY),
             (eventstream.sanitize(summary.get("run_id") or "?"), _C.CYAN)]
    if model:
        title += [(" · ", _C.GREY), (eventstream.sanitize(model), _C.GREY)]
    title += [("  ", None), (_fmt_dur(elapsed), _C.GREY)]

    kpi = [
        (f"iter {it}", _C.BOLD), (f"/{max_it}" if max_it else "", _C.GREY), ("  ", None),
        (f"{GLYPHS['accepted'][0]}{counts.get('accepted', 0)}", _C.GREEN), (" ", None),
        (f"{GLYPHS['rejected'][0]}{counts.get('rejected', 0)}", _C.YELLOW), (" ", None),
        (f"{GLYPHS['indecisive'][0]}{indecisive}", _C.BLUE), (" ", None),
        (f"{GLYPHS['failed'][0]}{counts.get('failed', 0)}", _C.RED), ("   ", None),
        (f"best↑ {_fmt_val(summary.get('best_val'))} ", _C.GREEN),
        (_sparkline(best_series), _C.GREEN), ("   ", None),
        (f"base {_fmt_val(summary.get('baseline_val'))}", _C.GREY), ("   ", None),
        (f"${float(usd or 0.0):.4f} · {_fmt_tokens(tok)} tok", _C.GREY),
    ]

    lines = [_fit(title, width, color), _breadcrumb(_phase(summary), color),
             _fit(kpi, width, color)]
    if summary.get("test_reward") is not None:
        seal = " (sealed)" if summary.get("test_sealed") else ""
        lines.append(_fit([(f"test{seal} {_fmt_val(summary.get('test_reward'))}", _C.BOLD),
                           ("   ", None),
                           (f"Δ vs base {_fmt_signed(summary.get('delta_abs'))}",
                            _C.GREEN if (summary.get("delta_abs") or 0) > 0 else _C.GREY)],
                          width, color))
    warns = summary.get("gate_warnings") or []
    if warns:
        txt = eventstream.sanitize(str((warns[-1] or {}).get("reason") or ""))
        lines.append(_fit([(f"⚠ {len(warns)} gate warning(s): {txt}", _C.YELLOW)], width, color))
    lines.append(_c("─" * width, _C.GREY, color))
    # The rule always closes the header, even when the budget crops the middle rows.
    if n and len(lines) > n:
        lines = lines[: n - 1] + [lines[-1]]
    return _pad(lines, n)


def _chart(graph: dict, width: int, height: int, *, color: bool) -> list[str]:
    """Cumulative-best stair over iterations.

    Same character grid and glyph vocabulary as ``dashboard.render_ansi``'s chart
    (``█`` best-so-far, ``○`` accept, ``·`` reject, ``x`` fail) — reproduced here
    because that chart is inline in ``render_ansi`` rather than a callable, and
    dashboard.py is not ours to refactor.
    """
    if height <= 2:
        return _pad([], height)
    series = [(n.get("iteration"), n.get("best_so_far"), n.get("val"), n.get("status"))
              for n in (graph.get("nodes") or []) if n.get("iteration") is not None]
    series = sorted([s for s in series if s[1] is not None], key=lambda s: s[0])
    if not series:
        return _pad([], height)
    grid_h = height - 2
    vals = [b for _, b, _, _ in series] + [v for _, _, v, _ in series if v is not None]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    grid_w = max(1, width - 8)
    step = max(1, len(series) // grid_w)
    cols = series[::step][:grid_w]
    # Stretch a short run across the panel so 7 iterations don't render as a 7-column
    # smudge in a 100-column terminal (downsampling above still caps long runs).
    rep = max(1, grid_w // max(1, len(cols)))
    cols = [c for c in cols for _ in range(rep)][:grid_w]
    grid = [[" "] * len(cols) for _ in range(grid_h)]
    for x, (_, b, v, st) in enumerate(cols):
        grid[grid_h - 1 - int(round((b - lo) / span * (grid_h - 1)))][x] = "█"
        if v is not None:
            y = grid_h - 1 - int(round((v - lo) / span * (grid_h - 1)))
            if grid[y][x] == " ":
                grid[y][x] = {"rejected": "·", "failed": "x"}.get(st, "○")
    paint = {"█": _C.GREEN, "x": _C.RED, "·": _C.YELLOW, "○": _C.CYAN}
    out = [_c("cumulative best", _C.BOLD, color)]
    for r, row in enumerate(grid):
        axis = f"{hi:.2f}" if r == 0 else (f"{lo:.2f}" if r == grid_h - 1 else "")
        out.append(_c(axis.rjust(5), _C.GREY, color) + " "
                   + "".join(_c(ch, paint.get(ch), color) for ch in row))
    out.append(_c("      █ best  ○ accept  · reject  x fail", _C.GREY, color))
    return _pad(out, height)


def _tree_rows(graph: dict) -> list[tuple[str, dict]]:
    """(prefix, node) rows in lineage order: DFS from the root, box-drawing indents.

    A ``seen`` set guards against a cycle in the parent edges and orphans (a parent
    that never made it into the graph) are reparented onto the root, so a truncated or
    hostile log yields a shorter tree rather than an exception or an infinite walk.
    """
    nodes = {str(n.get("id")): n for n in (graph.get("nodes") or []) if isinstance(n, dict)}
    if not nodes:
        return []
    root = str(graph.get("root") or "seed")
    if root not in nodes:
        root = next(iter(nodes))
    kids: dict[str, list[str]] = {k: [] for k in nodes}
    for nid, n in nodes.items():
        p = str(n.get("parent") or "")
        if nid == root:
            continue
        kids[p if p in nodes and p != nid else root].append(nid)
    for v in kids.values():
        v.sort(key=lambda k: nodes[k].get("iteration") or 0)

    rows: list[tuple[str, dict]] = []
    seen: set[str] = set()

    def walk(nid: str, prefix: str, stem: str) -> None:
        if nid in seen or len(rows) > 500:
            return
        seen.add(nid)
        rows.append((prefix + stem, nodes[nid]))
        children = kids.get(nid) or []
        base = prefix + ("" if not stem else ("    " if stem == "└─ " else "│   "))
        for i, c in enumerate(children):
            walk(c, base, "└─ " if i == len(children) - 1 else "├─ ")

    walk(root, "", "")
    return rows


def _tree(graph: dict, summary: dict, width: int, height: int, *, color: bool) -> list[str]:
    if height <= 1:
        return _pad([], height)
    rows = _tree_rows(graph)
    if not rows:
        return _pad([_c("lineage", _C.BOLD, color),
                     _c("  (no candidates yet)", _C.GREY, color)], height)
    body_h = height - 1
    hidden = 0
    if len(rows) > body_h:  # keep the TAIL — the newest candidates are the live ones
        hidden = len(rows) - (body_h - 1)
        rows = rows[-(body_h - 1):]
    out = [_c("lineage", _C.BOLD, color)]
    if hidden:
        out.append(_c(f"  … {hidden} earlier hidden", _C.GREY, color))
    best = str(summary.get("best_id") or "")
    for prefix, n in rows:
        status = str(n.get("status") or "queued")
        if status == "rejected" and "indecisive" in str(n.get("reason") or "").lower():
            status = "indecisive"
        glyph, style = GLYPHS.get(status, GLYPHS["queued"])
        nid = eventstream.sanitize(str(n.get("id") or "?"))
        stderr = n.get("stderr")
        val = f"{_fmt_val(n.get('val'))}" + (f"±{_fmt_val(stderr, 3)}" if stderr else "")
        pv = n.get("parent_val")
        try:
            delta = f"{float(n['val']) - float(pv):+.3f}"
        except (TypeError, ValueError, KeyError):
            delta = "     —"
        reason = eventstream.sanitize(str(n.get("reason") or ""))
        secs = _fmt_dur(n.get("seconds"))
        cells = [
            (prefix, _C.GREY),
            (f"{glyph} ", style),
            (f"{GLYPHS['best'][0]}" if nid == best else " ", _C.BOLD),
            (f"{nid:<14}", None),
            (f"{val:>14}", _C.CYAN),
            (f"{delta:>9}", _C.GREEN if delta.startswith("+") else _C.GREY),
            (f"{secs:>9}", _C.GREY),
            ("  ", None),
            (reason, _C.GREY),
        ]
        out.append(_fit(cells, width, color))
    return _pad(out, height)


def _activity(activity, running: str | None, width: int, height: int,
              *, color: bool) -> list[str]:
    if height <= 1:
        return _pad([], height)
    out = [_c("activity", _C.BOLD, color)]
    body = height - 1
    # Running-first: an in-flight item must never scroll out behind finished ones.
    if running:
        out.append(_fit([(running, _C.CYAN)], width, color))
        body -= 1
    for line in list(activity)[-max(0, body):]:
        out.append(_fit([(eventstream.sanitize(str(line)), _C.GREY)], width, color))
    return _pad(out, height)


def _footer(root, width: int, height: int, *, color: bool) -> list[str]:
    return _pad([_c("─" * width, _C.GREY, color),
                 _fit([(str(root), _C.GREY), ("   ", None),
                       ("Ctrl-C to detach (run continues)", _C.DIM)], width, color)],
                height)


# ---- the pure renderer -----------------------------------------------------

def render_frame(reduced: dict, size: tuple[int, int] = (100, 30), *, color: bool = False,
                 root: str = "", activity=(), running: str | None = None,
                 totals: dict | None = None, elapsed: float | None = None) -> str:
    """One frame for ``reduced`` (a :func:`dashboard.reduce_run` result).

    Pure: no terminal, no clock, no filesystem — everything time-dependent
    (``elapsed``, the spinner inside ``running``) is passed in, which is what makes
    this unit-testable and makes ``replay`` the same code path as ``watch``.

    Total: any missing/malformed key degrades to a placeholder line. The frame is
    never taller than ``size[1]`` rows.
    """
    width, rows = 80, 24
    try:
        width, rows = max(20, int(size[0])), max(1, int(size[1]))
    except (TypeError, ValueError, IndexError):
        pass
    try:
        graph = reduced.get("graph") or {}
        summary = reduced.get("summary") or {}
        sizes = plan_section_sizes(
            rows,
            has_chart=bool([n for n in (graph.get("nodes") or [])
                            if n.get("best_so_far") is not None]),
            has_tree=True, has_activity=bool(activity or running),
            tree_rows=len(_tree_rows(graph)) + 2,
        )
        out: list[str] = []
        out += _header(summary, graph, width, color=color, totals=totals,
                       elapsed=elapsed, n=sizes["header"])
        out += _chart(graph, width, sizes["chart"], color=color)
        out += _tree(graph, summary, width, sizes["tree"], color=color)
        out += _activity(activity, running, width, sizes["activity"], color=color)
        out += _footer(root, width, sizes["footer"], color=color)
        return "\n".join(out[:rows])
    except Exception as e:  # noqa: BLE001 — a frame that raises silences the whole run
        return _c(f"[tui] frame unavailable ({e!r}) — the run continues",
                  _C.YELLOW, color)[:width]


# ---- terminal plumbing -----------------------------------------------------

class _Painter:
    """Inline repaint: cursor-up + clear-to-end. Never the alternate screen, so
    scrollback (CI logs, screen recordings) survives the session."""

    def __init__(self, stream, *, inline: bool = True):
        self.stream, self.inline, self._rows = stream, inline, 0

    def paint(self, frame: str) -> None:
        try:
            if self.inline and self._rows:
                self.stream.write(f"\x1b[{self._rows}A\x1b[0J")
            self.stream.write(frame + "\n")
            self.stream.flush()
            self._rows = frame.count("\n") + 1
        except Exception:  # noqa: BLE001 — a dead stream must not kill the run
            self.inline = False

    def close(self) -> None:
        # Only ever emit the restore sequence on the path that emitted the hide one:
        # a piped/redirected frame stream must stay byte-for-byte ANSI-free.
        if not self.inline:
            return
        try:
            self.stream.write("\x1b[?25h" + _C.RESET + "\n")
            self.stream.flush()
        except Exception:  # noqa: BLE001
            pass

    def __enter__(self):
        try:
            if self.inline:
                self.stream.write("\x1b[?25l")  # hide cursor while repainting
        except Exception:  # noqa: BLE001
            self.inline = False
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _reduce(root) -> dict:
    """``reduce_run`` on a bare path. Degrades to an empty projection, never raises.

    ``RunDir(root)`` (not ``.open``) on purpose: a run dir that has events but no
    state.json yet — or a replay scratch dir that will never have one — must still
    render. ``reduce_run`` already treats ``spent``/``read_splits`` as optional.
    """
    from .rundir import RunDir
    try:
        return reduce_run(RunDir(Path(root)))
    except Exception:  # noqa: BLE001
        return {"graph": {"nodes": [], "root": "seed", "best_id": "seed"},
                "summary": {"run_id": Path(root).name}}


def _stream_lines(path: Path, stream, *, color: bool, offset: int = 0,
                  idle_timeout: float | None = None, should_stop=None) -> str | None:
    """Non-TTY fallback: the existing line-oriented event stream."""
    totals: dict = {}
    reason = None
    for ev in eventstream.follow_events(path, offset=offset, poll=0.5,
                                        idle_timeout=idle_timeout,
                                        should_stop=should_stop):
        if ev.get("kind") == eventstream.FOLLOW_END:
            reason = ev.get("reason")
            continue
        line = eventstream.render_line(ev, totals, color=color)
        if line:
            print(line, file=stream, flush=True)
    return reason


def _live_feed(path: Path, *, offset: int, idle_timeout: float | None, poll: float,
               should_stop=None):
    """Yield events, plus an empty dict every ``poll`` seconds as a repaint tick.

    The tick is why the TUI keeps ticking (elapsed, spinner) and picks up a terminal
    resize with zero events arriving. ``follow_events`` owns all the stop semantics;
    it just runs on a thread because it blocks between polls.
    """
    import queue
    import threading

    q: "queue.Queue" = queue.Queue()

    def worker():
        try:
            for ev in eventstream.follow_events(path, offset=offset, poll=poll,
                                                idle_timeout=idle_timeout,
                                                should_stop=should_stop):
                q.put(ev)
        except Exception as e:  # noqa: BLE001
            q.put({"kind": eventstream.FOLLOW_END, "reason": "error", "error": repr(e)})
        q.put(None)

    threading.Thread(target=worker, name="cap-evolve-tui", daemon=True).start()
    while True:
        try:
            ev = q.get(timeout=poll)
        except queue.Empty:
            yield {}
            continue
        if ev is None:
            return
        yield ev


def _drive(root, feed, *, stream, color: bool, poll: float = 0.4) -> str | None:
    """The one loop both modes share: fold events → repaint on a dirty flag + tick."""
    activity: deque = deque(maxlen=8)
    totals: dict = {}
    reduced = _reduce(root)
    dirty, reason, done = False, None, False
    last_event = time.monotonic()

    with _Painter(stream) as painter:
        # SIGTERM must restore the terminal too, not just Ctrl-C.
        def _term(*_a):
            raise KeyboardInterrupt  # unwinds to the finally below → terminal restored

        prev = None
        try:
            prev = signal.signal(signal.SIGTERM, _term)
        except (ValueError, OSError, AttributeError):
            prev = None
        try:
            for ev in feed:
                if ev:
                    if ev.get("kind") == eventstream.FOLLOW_END:
                        reason, done = ev.get("reason"), True
                    else:
                        eventstream.accrue_totals(ev, totals)
                        line = eventstream.render_line(ev, None)
                        if line:
                            activity.append(line)
                        last_event = time.monotonic()
                    dirty = True
                if dirty:
                    reduced = _reduce(root)
                    dirty = False
                running = None if done else (
                    f"{_spinner()} working… {_fmt_dur(time.monotonic() - last_event)} "
                    f"since last event")
                painter.paint(render_frame(reduced, terminal_size(stream), color=color,
                                           root=root, activity=activity, running=running,
                                           totals=totals))
        except KeyboardInterrupt:
            return "interrupt"
        finally:
            if prev is not None:
                try:
                    signal.signal(signal.SIGTERM, prev)
                except (ValueError, OSError):
                    pass
    return reason


def watch(root, *, stream=None, color: bool | None = None, from_start: bool = True,
          idle_timeout: float | None = None, poll: float = 0.4,
          should_stop=None) -> str | None:
    """Live TUI over a run dir. Returns the FOLLOW_END reason (or ``"interrupt"``).

    Writes to ``stream`` (default stderr) so stdout stays the machine-readable
    contract. On a non-TTY the full-screen path is skipped for the line-oriented
    :func:`eventstream.render_line` stream.
    """
    stream = stream or sys.stderr
    if color is None:
        color = eventstream.use_color(stream)
    root = Path(root)
    events = root / "events.jsonl"
    offset = 0 if from_start or not events.exists() else events.stat().st_size
    if not _is_tty(stream):
        return _stream_lines(events, stream, color=color, offset=offset,
                             idle_timeout=idle_timeout, should_stop=should_stop)
    return _drive(root, _live_feed(events, offset=offset, idle_timeout=idle_timeout,
                                   poll=poll, should_stop=should_stop),
                  stream=stream, color=color, poll=poll)


def _is_tty(stream) -> bool:
    try:
        return bool(stream.isatty())
    except Exception:  # noqa: BLE001
        return False


def replay(src, *, stream=None, color: bool | None = None, speed: float = 1.0,
           max_gap: float = 1.0, banner: str | None = None) -> None:
    """Re-feed a recorded ``events.jsonl`` through the SAME reducer + renderer.

    Events are appended to a scratch run dir one at a time and re-reduced, so replay
    exercises the real projection instead of a parallel mock. ``baseline.json`` /
    ``final.json`` are copied in only when their event arrives, so the frame never
    shows a result the log has not reached yet.
    """
    import tempfile

    stream = stream or sys.stderr
    if color is None:
        color = eventstream.use_color(stream)
    src = Path(src)
    events = [json.loads(ln) for ln in
              (src / "events.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    if banner:
        print(_c(banner, _C.YELLOW, color), file=stream, flush=True)
    tty = _is_tty(stream)

    with tempfile.TemporaryDirectory(prefix="capevolve-replay-") as d:
        scratch = Path(d) / src.name  # keeps the header's run_id honest, not "tmpXXXX"
        scratch.mkdir()
        log = scratch / "events.jsonl"
        painter = _Painter(stream, inline=tty)
        reduced = _reduce(scratch)
        totals: dict = {}
        activity: deque = deque(maxlen=8)
        with painter:
            prev_t = None
            for ev in events:
                with log.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(ev) + "\n")
                for name, kind in (("baseline.json", "baseline"), ("final.json", "finalize")):
                    if ev.get("kind") == kind and (src / name).exists():
                        shutil.copy2(src / name, scratch / name)
                gap = 0.0
                if prev_t is not None:
                    try:
                        gap = max(0.0, (float(ev.get("t") or 0) - prev_t) / max(0.01, speed))
                    except (TypeError, ValueError):
                        gap = 0.0
                prev_t = float(ev.get("t") or 0) if ev.get("t") else prev_t
                if gap:
                    time.sleep(min(gap, max_gap))
                eventstream.accrue_totals(ev, totals)
                line = eventstream.render_line(ev, None)
                if line:
                    activity.append(line)
                    if not tty:  # piped: the line log IS the output
                        print(line, file=stream, flush=True)
                reduced = _reduce(scratch)
                if tty:
                    painter.paint(render_frame(reduced, terminal_size(stream), color=color,
                                               root=str(src), activity=activity,
                                               totals=totals))
            if not tty:
                # Still end on a frame so a piped replay shows the same final state.
                print(render_frame(reduced, (terminal_size(stream)[0], 200), color=color,
                                   root=str(src), activity=activity, totals=totals),
                      file=stream, flush=True)
        if banner:
            print(_c(banner, _C.YELLOW, color), file=stream, flush=True)


if __name__ == "__main__":  # tiny self-check: the budget invariant holds everywhere
    for r in range(0, 200):
        assert sum(plan_section_sizes(r).values()) <= r, r
    assert render_frame({"summary": None}, (10, 5))  # malformed → placeholder, no raise
    print("tui self-check ok")
