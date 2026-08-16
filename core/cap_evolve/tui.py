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
import textwrap
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
#:
#: Read cross-module as ``tui.DEMO_BANNER`` (``cli.py`` replay path, ``test_replay.py``,
#: ``scripts/generate_demo_session.py``), so static analysis flags it as an unused
#: global. It is not — deleting it removes a truthfulness guard and breaks those tests.
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
    ("header", 1, 9),
    ("footer", 1, 2),
    ("tree", 3, 40),
    # 12: an 8-entry backlog plus the title and the in-flight line, with room for one
    # wrapped reason. Capped for real by ``activity_rows`` (the lines it actually has).
    ("activity", 1, 12),
    ("algo", 1, 3),
    # diff before heatmap: the diff panel only exists when the user asked for it
    # (--diff), so on a short terminal it outranks a panel they did not request.
    ("diff", 4, 14),
    ("heatmap", 2, 10),
    # 10 is the chart's CONTENT size; it is also the surplus sink (see :data:`_FILL`),
    # where it grows past this without limit once every panel has its own rows.
    ("chart", 5, 10),
)
# Growth order once every section has its minimum: give spare rows to the panels
# that carry information density before letting the chart stretch.
_GROW = ("header", "footer", "tree", "diff", "algo", "heatmap", "activity", "chart")
#: Where a genuine SURPLUS goes once every section is at its content size AND its
#: stretch size, in order of preference. The chart is first: more rows there is more
#: vertical resolution, which is real information, whereas more rows anywhere else is
#: padding. The rest are fallbacks for a frame with no chart yet.
_FILL = ("chart", "tree", "activity", "diff", "heatmap")


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
                       has_activity: bool = True, tree_rows: int | None = None,
                       has_algo: bool = False, has_heatmap: bool = False,
                       has_diff: bool = False, heatmap_rows: int | None = None,
                       diff_rows: int | None = None,
                       header_rows: int | None = None,
                       activity_rows: int | None = None,
                       stretch: dict | None = None) -> dict[str, int]:
    """Row allocation whose sum NEVER exceeds ``avail_rows``.

    Three passes:

    1. **minimums**, in :data:`_SECTIONS` priority order — a section starved by a tiny
       terminal gets 0 rows and is simply not drawn.
    2. **content**, in :data:`_GROW` order up to each section's maximum, where the
       ``*_rows`` arguments cap a panel at the rows its content actually occupies. This
       is what stops a 3-row panel from sitting under a band of padding.
    3. **stretch/surplus**, in :data:`_FILL` order: leftover rows go to the panels that
       turn height into information — ``stretch[name]`` is the rows a panel could use
       for its *nice-to-have* lines (a wrapped gate reason), and the chart takes whatever
       remains as real vertical resolution. Without this pass a tall terminal ended with
       a quarter of the frame blank: every panel was at its cap and nobody took the rest.

    ``sum(...) <= avail_rows`` is the invariant that keeps an inline repaint honest: emit
    one row more than the terminal has and the previous frame scrolls out of reach of the
    cursor-up, leaving a duplicated half-frame on screen.
    """
    want = {"header": True, "footer": True, "tree": has_tree,
            "activity": has_activity, "chart": has_chart,
            "algo": has_algo, "heatmap": has_heatmap, "diff": has_diff}
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
        # Cap a panel at the rows it actually has, so spare space reaches the chart
        # instead of becoming a band of padding under a 3-row panel.
        for who, cap in (("tree", tree_rows), ("heatmap", heatmap_rows),
                         ("diff", diff_rows), ("header", header_rows),
                         ("activity", activity_rows)):
            if name == who and cap is not None:
                hi = min(hi, max(1, int(cap)))
        grow = min(max(0, hi - out[name]), left)
        out[name], left = out[name] + grow, left - grow
    # Stretch pass: the panels that can turn extra rows into extra text (wrapped gate
    # reasons) get them before the chart, but only up to what they would actually use.
    for name, cap in (stretch or {}).items():
        if left <= 0:
            break
        if name not in out or out[name] == 0:
            continue
        grow = min(max(0, int(cap) - out[name]), left)
        out[name], left = out[name] + grow, left - grow
    # Surplus pass: rows still unspent, so hand them to the first panel that can use
    # height for real rather than leaving a band of dead frame at the bottom.
    for name in _FILL:
        if left <= 0:
            break
        if out[name] == 0:
            continue  # starved by the budget; do not resurrect it here either
        out[name], left = out[name] + left, 0
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


def _ell(text: str, width: int) -> str:
    """``text`` in at most ``width`` columns, marking a crop with ``…``.

    A silently clipped sentence (``… SE=0 → STRICT fallback, wa``) reads as a rendering
    bug; the ellipsis says "there is more" instead. Only ever applied to already
    sanitized text, and never to a line that fits.
    """
    text = str(text)
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    cut = text[: max(0, width - 1)]
    # Back up to a word boundary when one is close: "— no evid…" reads as a rendering
    # bug, "— no …" reads as a deliberate crop. Only a short reach back, so a long
    # unbroken token (a path, a hash) still shows as much of itself as it can.
    space = cut.rfind(" ")
    if space >= 8 and len(cut) - space <= 14:
        cut = cut[:space + 1]
    return cut + "…"


def _wrap(text: str, width: int) -> list[str]:
    """``text`` wrapped on word boundaries, or ``[]`` when there is no usable width.

    The gate reason justifies every accept/reject/indecisive decision, so when the frame
    has vertical room the reason is continued on the next line rather than truncated.
    """
    text = str(text).strip()
    if not text or width < 8:
        return []
    return textwrap.wrap(text, width) or []


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


def _breadcrumb(current: str, width: int, color: bool) -> str:
    cells = []
    for i, name in enumerate(PHASES):
        if i:
            cells.append((" › ", _C.GREY))
        if name == current:
            cells.append((name, _C.BOLD + _C.CYAN))
        else:
            cells.append((name, _C.GREY))
    return _fit(cells, width, color)


def _gate_mode(summary: dict) -> tuple[str, str]:
    """``(mode, k_se)`` as strings, read from the gate's OWN recorded reasons.

    Never guessed: a run whose log carries no gate decision yields ``("—", "—")`` rather
    than the default configuration, which may not be the one that ran.
    """
    mode, k = "—", "—"
    for d in (summary.get("gate_decisions") or []):
        if not isinstance(d, dict):
            continue
        reason = str(d.get("reason") or "")
        if "STRICT" in reason:
            mode = "strict (SE=0 fallback)"
        elif reason.startswith("paired") or "paired" in reason:
            mode = "paired"
        if d.get("k_se") is not None:
            k = _fmt_val(d.get("k_se"), 2)
    return mode, k


def _trials(summary: dict) -> str:
    """Trials per task, as RECORDED by the evaluations (``—`` when nothing recorded)."""
    ns = [int(e.get("trials") or 0) for e in (summary.get("evaluations") or [])
          if isinstance(e, dict) and e.get("trials")]
    return str(max(ns)) if ns else "—"


def run_meta(summary: dict, *, elapsed: float | None = None) -> list[tuple[str, str]]:
    """The run's identity as ``(label, value)`` pairs — the masthead's content.

    Everything here answers "is this the run I think I launched?": the resolved spec
    path, the algorithm and orchestration mode, the split it froze, the trials and gate
    bar behind every number, and the target model. A run started against the wrong
    project's ``capevolve.yaml`` is visible here in seconds instead of after the spend.

    Pure, sanitized, and honest: a value the run never recorded is ``—``, never a
    plausible default.
    """
    cfg = summary.get("run_config") or {}
    sp = summary.get("splits") or {}
    S = lambda v: eventstream.sanitize(str(v))  # noqa: E731
    algo = S(summary.get("algorithm") or cfg.get("algorithm") or "—")
    mode = S(cfg.get("orchestration_mode") or "—")
    gate, k = _gate_mode(summary)
    n = lambda v: (str(v) if isinstance(v, int) else "—")  # noqa: E731
    split = (f"train {n(sp.get('train'))} · val {n(sp.get('val'))} · "
             f"test {n(sp.get('test'))}" + (f"   seed {sp.get('seed')}"
                                            if sp.get("seed") is not None else "")
             if sp else "—")
    if elapsed is None:
        elapsed = summary.get("wall_clock_seconds")
    # Exactly LOGO_ROWS - 3 pairs: the block is sized to end level with the capybara,
    # so the masthead reads as one unit instead of a logo with a ragged list beside it.
    return [
        ("run", S(summary.get("run_id") or "?") + f"   {_fmt_dur(elapsed)}"
                if elapsed else S(summary.get("run_id") or "?")),
        ("algorithm", f"{algo}" + (f" · {mode}" if mode != "—" else "")),
        ("spec", S(cfg.get("spec") or "—")),
        ("split", split),
        ("gate", f"{gate}   k_se {k}   trials {_trials(summary)}"),
        ("target", S((summary.get("target_profile") or {}).get("model") or "—")),
    ]


def _provenance(summary: dict, width: int, *, color: bool) -> str:
    """One compact line naming the spec + algorithm that produced this run.

    The masthead already carries spec + algorithm, but it only renders on a truecolor
    terminal tall enough for the logo. So this line is the FALLBACK: the caller passes
    ``masthead=True`` to suppress it once the masthead has actually been printed, and
    provenance is still never the thing that got dropped — reading the wrong project's
    spec is the failure this line exists to catch.
    """
    cfg = summary.get("run_config") or {}
    algo = eventstream.sanitize(str(summary.get("algorithm")
                                    or cfg.get("algorithm") or "—"))
    mode = eventstream.sanitize(str(cfg.get("orchestration_mode") or ""))
    spec = eventstream.sanitize(str(cfg.get("spec") or "not recorded"))
    right = f"   {algo}" + (f" · {mode}" if mode else "")
    return _fit([("spec ", _C.GREY),
                 (_ell(spec, max(8, width - len(right) - 5)), None),
                 (right, _C.GREY)], width, color)


def _header_lines(summary: dict, graph: dict, width: int, *, color: bool,
                  totals: dict | None, elapsed: float | None,
                  masthead: bool = False) -> list[str]:
    """The header's content, unpadded — the caller decides how many rows it gets.

    Returned unpadded so :func:`render_frame` can cap the header's row budget at the
    rows it actually needs; a fixed maximum let the header absorb every spare row and
    starve the lineage panel down to its minimum.
    """
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

    lines = [_fit(title, width, color)]
    if not masthead and (summary.get("run_config") or summary.get("algorithm")):
        lines.append(_provenance(summary, width, color=color))
    lines += [_breadcrumb(_phase(summary), width, color), _fit(kpi, width, color)]
    # Spend split (runner vs optimizer vs intake). Only ever the numbers the run
    # actually recorded: a role with no recorded spend is omitted, not shown as $0.
    cost = summary.get("cost") or {}
    parts = [(label, cost.get(key)) for label, key in
             (("runner", "runner_usd"), ("optimizer", "optimizer_usd"),
              ("intake", "intake_usd"))]
    have = [(label, v) for label, v in parts if isinstance(v, (int, float)) and v]
    if have and width >= 60:
        cells: list = [("spend  ", _C.GREY)]
        for i, (label, v) in enumerate(have):
            if i:
                cells.append((" · ", _C.GREY))
            cells += [(f"{label} ", _C.GREY), (f"${float(v):.4f}", None)]
        lines.append(_fit(cells, width, color))
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
        lines.append(_fit([(_ell(f"⚠ {len(warns)} gate warning(s): {txt}", width),
                            _C.YELLOW)], width, color))
    lines.append(_c("─" * width, _C.GREY, color))
    return lines


def _header(lines: list[str], n: int) -> list[str]:
    """Fit prebuilt header lines into ``n`` rows, always keeping the closing rule."""
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
    width_used = min(grid_w, rep * len(cols))
    grid = [[" "] * width_used for _ in range(grid_h)]
    for i, (_, b, v, st) in enumerate(cols):
        x0 = i * rep
        if x0 >= width_used:
            break
        top = grid_h - 1 - int(round((b - lo) / span * (grid_h - 1)))
        for x in range(x0, min(width_used, x0 + rep)):
            # Filled stair, not a one-pixel line: the area under the cumulative best is
            # what makes a 4-iteration run readable instead of three dots in a big box.
            for y in range(top + 1, grid_h):
                grid[y][x] = "▒"
            grid[top][x] = "█"
        if v is not None:
            # ONE marker per iteration, at the middle of its stretched band. Painting it
            # across the whole band drew a dotted horizontal *line* that read as a
            # second data series instead of a single measured point.
            x = min(width_used - 1, x0 + rep // 2)
            y = grid_h - 1 - int(round((v - lo) / span * (grid_h - 1)))
            if grid[y][x] in (" ", "▒"):
                grid[y][x] = {"rejected": "·", "failed": "x"}.get(st, "○")
    paint = {"█": _C.GREEN, "▒": _C.DIM + _C.GREEN, "x": _C.RED, "·": _C.YELLOW,
             "○": _C.CYAN}
    out = [_c("cumulative best", _C.BOLD, color)]
    for r, row in enumerate(grid):
        axis = f"{hi:.2f}" if r == 0 else (f"{lo:.2f}" if r == grid_h - 1 else "")
        out.append(_c(axis.rjust(5), _C.GREY, color) + " "
                   + "".join(_c(ch, paint.get(ch), color) for ch in row))
    # Every glyph on the grid is named here. The shaded area under the stair used to be
    # unexplained, which left a viewer guessing whether it was data or decoration.
    out.append(_fit([("      █ best so far  ▒ area under best  "
                      "○ accept  · reject  x fail", _C.GREY)], width, color))
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


#: Visible columns the lineage row's fixed part occupies before the reason, excluding
#: the tree prefix: glyph+space, best mark, id, val, delta, seconds, gap.
_TREE_FIXED = 2 + 1 + 14 + 14 + 9 + 9 + 2


def _tree_cells(prefix: str, n: dict, best: str) -> tuple[list, str]:
    """``(fixed cells, sanitized reason)`` for one lineage row."""
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
    ]
    return cells, eventstream.sanitize(str(n.get("reason") or ""))


def _tree_reason_lines(prefix: str, reason: str, width: int) -> list[str]:
    """The reason split across its row + continuation lines (plain text, no ANSI).

    ``[]`` when it already fits, so the caller can render the simple single-line form.
    The split is on word boundaries in BOTH directions: a hard slice for the first line
    would leave the same mid-word stub the wrapping exists to remove.
    """
    room = width - len(prefix) - _TREE_FIXED
    # Below ~24 columns a "wrap" is one word per line — a ragged column that looks more
    # broken than the ellipsis it replaced. Narrower than that, crop and say so.
    if room < 24 or len(reason) <= room:
        return []
    parts = _wrap(reason, room)
    if len(parts) < 2:
        return []
    # At most one continuation line: two is a paragraph in a table, and the full text is
    # a keystroke away in the activity log and `cap-evolve diff`.
    if len(parts) > 2:
        parts = [parts[0], _ell(" ".join(parts[1:]), room)]
    return parts


def _tree_height(graph: dict, width: int) -> int:
    """Rows the lineage panel WANTS at ``width``, wrapped reasons included.

    Fed to :func:`plan_section_sizes` as the panel's honest cap so the budget can give
    the reasons their continuation lines instead of stopping at one row per candidate.
    """
    rows = _tree_rows(graph)
    total = 1 + len(rows)
    for prefix, n in rows:
        reason = eventstream.sanitize(str(n.get("reason") or ""))
        total += max(0, len(_tree_reason_lines(prefix, reason, width)) - 1)
    return total


def _tree(graph: dict, summary: dict, width: int, height: int, *, color: bool) -> list[str]:
    if height <= 1:
        return _pad([], height)
    rows = _tree_rows(graph)
    if not rows:
        return _pad([_c("lineage", _C.BOLD, color),
                     _c("  (no candidates yet)", _C.GREY, color)], height)
    best = str(summary.get("best_id") or "")
    built = [(_tree_cells(prefix, n, best), prefix) for prefix, n in rows]
    # Two renderings of every row: one line with an explicit ellipsis, or the reason
    # wrapped onto continuation lines. Wrapping is the goal (the gate reason justifies
    # the decision and is the most valuable string here) but it costs rows, so rows are
    # upgraded NEWEST-FIRST with whatever the budget gave us. That degrades one candidate
    # at a time instead of falling off a cliff into all-ellipsis with a blank half-panel.
    wrapped: list[list[str]] = []
    compact: list[list[str]] = []
    for (cells, reason), prefix in built:
        room = max(0, width - len(prefix) - _TREE_FIXED)
        compact.append([_fit(cells + [(_ell(reason, room), _C.GREY)], width, color)])
        parts = _tree_reason_lines(prefix, reason, width) or [reason[:room]]
        indent = " " * min(width, len(prefix) + 5)
        wrapped.append(
            [_fit(cells + [(parts[0], _C.GREY)], width, color)]
            + [_fit([(indent, None), (ln, _C.GREY)], width, color) for ln in parts[1:]])
    body_h = height - 1
    groups = list(compact)
    spare = body_h - len(groups)
    for i in reversed(range(len(groups))):
        extra = len(wrapped[i]) - 1
        if 0 < extra <= spare:
            groups[i], spare = wrapped[i], spare - extra
    lines = [ln for g in groups for ln in g]
    out = [_c("lineage", _C.BOLD, color)]
    if len(lines) > body_h:  # keep the TAIL — the newest candidates are the live ones
        kept = body_h - 1
        out.append(_fit([(f"  … {len(lines) - kept} earlier line(s) hidden", _C.GREY)],
                        width, color))
        lines = lines[-kept:]
    return _pad(out + lines, height)


def _activity_height(activity, running: str | None, width: int) -> int:
    """Rows the activity panel WANTS: title + the in-flight line + each entry wrapped.

    Its honest cap for :func:`plan_section_sizes` — without it the panel claimed rows it
    could only fill with blanks, and those blanks were the empty band at the frame's
    bottom instead of chart resolution.
    """
    total = 1 + (1 if running else 0)
    for line in activity or ():
        text = eventstream.sanitize(str(line))
        total += len(_wrap(text, width - 3)) if len(text) > width else 1
    return max(1, total)


def _activity(activity, running: str | None, width: int, height: int,
              *, color: bool) -> list[str]:
    if height <= 0:
        return []
    if height == 1:
        # One row: spend it on the newest line rather than on a title or a blank. A
        # starved panel should still say something true.
        newest = running or (eventstream.sanitize(str(list(activity)[-1]))
                             if activity else "")
        return [_fit([(_ell(newest, width), _C.CYAN if running else _C.GREY)],
                     width, color)]
    out = [_c("activity", _C.BOLD, color)]
    body = height - 1
    # Running-first: an in-flight item must never scroll out behind finished ones.
    if running:
        out.append(_fit([(running, _C.CYAN)], width, color))
        body -= 1
    body = max(0, body)
    items = [eventstream.sanitize(str(line)) for line in activity]
    # Newest-last, so budget the rows from the newest backwards: an event whose gate
    # reason overflows gets a continuation line when the panel still has room, and an
    # explicit ellipsis when it does not.
    rendered: list[list[str]] = []
    used = 0
    for text in reversed(items):
        if used >= body:
            break
        # width-3 so a continuation line still fits once its indent is added.
        parts = _wrap(text, width - 3) if len(text) > width else [text]
        if not parts:
            continue
        if len(parts) > body - used:  # no room to continue it — say it was cropped
            parts = [_ell(text, width)]
        rendered.append([_fit([("   " if i else "", None), (ln, _C.GREY)], width, color)
                         for i, ln in enumerate(parts)])
        used += len(parts)
    for group in reversed(rendered):
        out += group
    return _pad(out, height)


# ---- generic panel: per-task heatmap ---------------------------------------

#: reward → glyph. ``·`` is reserved for "this task was NOT evaluated for this
#: candidate" — a free-form/agentic run may score a task SUBSET, and a missing
#: measurement must never render as the same cell as a measured 0.0.
_HEAT = ("░", "▒", "▓", "█")
_HEAT_STYLE = (_C.RED, _C.YELLOW, _C.CYAN, _C.GREEN)
_MISSING = "·"


def _heat_cell(v) -> tuple[str, str]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return _MISSING, _C.GREY
    i = 0 if f <= 0.0 else min(len(_HEAT) - 1, int(f * len(_HEAT)))
    return _HEAT[i], _HEAT_STYLE[i]


def has_per_task(graph: dict) -> bool:
    """True when at least one candidate recorded per-task rewards (the panel's gate)."""
    for n in (graph.get("nodes") or []):
        if isinstance(n, dict) and isinstance(n.get("per_task"), dict) and n["per_task"]:
            return True
    return False


def _heatmap(graph: dict, summary: dict, width: int, height: int, *,
             color: bool) -> list[str]:
    """Per-task val reward, one row per candidate, one column per task.

    Algorithm-agnostic: it reads ``node["per_task"]``, which every algorithm fills via
    the same ``evaluate`` phase. A task a candidate never ran shows :data:`_MISSING`,
    never a zero — an unmeasured task is missing data, not a failure.
    """
    if height <= 1:
        return _pad([], height)
    tasks = [str(t) for t in (summary.get("tasks") or [])]
    nodes = [n for n in (graph.get("nodes") or []) if isinstance(n, dict)]
    if not tasks:  # fall back to the union of whatever the nodes measured
        seen: list[str] = []
        for n in nodes:
            for t in (n.get("per_task") or {}):
                if t not in seen:
                    seen.append(str(t))
        tasks = seen
    rows = [n for n in nodes if isinstance(n.get("per_task"), dict) and n["per_task"]]
    if not tasks or not rows:
        return _pad([], height)
    rows.sort(key=lambda n: n.get("iteration") or 0)
    label_w = 14
    avail = max(1, width - label_w - 6)
    # A 2-task split should not render as two lonely characters: widen the cell until
    # the row fills the panel (capped, so a 200-task split stays one column each).
    cell_w = max(1, min(6, avail // max(1, len(tasks))))
    cols = max(1, avail // cell_w)
    shown, hidden = tasks[:cols], max(0, len(tasks) - cols)
    best = str(summary.get("best_id") or "")
    head = [("per-task val", _C.BOLD), ("  ", None),
            (f"{len(shown)}/{len(tasks)} tasks", _C.GREY), ("   ", None),
            (f"{_HEAT[0]} low  {_HEAT[-1]} high  {_MISSING} not evaluated", _C.GREY)]
    out = [_fit(head, width, color)]
    body = height - 1
    if len(rows) > body:
        rows = rows[-body:]
    for n in rows:
        per = n.get("per_task") or {}
        nid = eventstream.sanitize(str(n.get("id") or "?"))
        mark = GLYPHS["best"][0] if nid == best else " "
        cells = [(f"{(nid[:label_w - 2]):<{label_w - 2}}", None), (mark, _C.BOLD), (" ", None)]
        for t in shown:
            glyph, style = _heat_cell(per.get(t))
            cells.append((glyph * cell_w, style))
        if hidden:
            cells.append((f" …{hidden}", _C.GREY))
        out.append(_fit(cells, width, color))
    return _pad(out, height)


# ---- per-algorithm extras (capability-gated) --------------------------------

def fold_algo_stats(ev: dict, stats: dict | None) -> None:
    """Accumulate per-algorithm signal from ONE event into ``stats``.

    Kept separate from :func:`dashboard.reduce_run` on purpose: the algorithm-specific
    kinds (``gepa_select`` / ``gepa_local_gate`` / ``skillopt_slow_update`` …) are real
    emitted events the reducer does not project, and the live view is where they matter.
    Counts only; a kind that never fires leaves no key, which is what lets
    :func:`algo_panel` omit a panel instead of rendering a fabricated zero.
    """
    if stats is None or not isinstance(ev, dict):
        return
    kind = str(ev.get("kind") or "")
    if not kind or kind == eventstream.FOLLOW_END:
        return
    kinds = stats.setdefault("kinds", {})
    kinds[kind] = kinds.get(kind, 0) + 1
    if kind == "gepa_local_gate":
        key = "mb_pass" if ev.get("passed") else "mb_fail"
        stats[key] = stats.get(key, 0) + 1
    elif kind == "gepa_select":
        stats["parent"] = eventstream.sanitize(str(ev.get("parent") or ""))
        stats["strategy"] = eventstream.sanitize(str(ev.get("strategy") or ""))
    elif kind == "skillopt_step":
        for src, dst in (("epoch", "epoch"), ("step_in_epoch", "step_in_epoch"),
                         ("lr", "lr"), ("edit_budget", "lr")):
            if ev.get(src) is not None:
                stats[dst] = eventstream.sanitize(str(ev.get(src)))
    elif kind in ("skillopt_start", "gepa_start"):
        for k in ("epochs", "lr_schedule", "minibatch_size", "component_selector",
                  "max_metric_calls"):
            if ev.get(k) is not None:
                stats[k] = eventstream.sanitize(str(ev.get(k)))


def algo_panel(stats: dict | None, summary: dict) -> tuple[str, list[str]]:
    """``(algorithm_name, extra_lines)`` — or ``("", [])`` when the log evidences none.

    The name is DERIVED from the kinds actually in the log, never guessed: a
    ``hill-climb`` run and an agent-driven run emit the same ``step`` events, so
    neither is named. Missing capability ⇒ no panel.
    """
    kinds = (stats or {}).get("kinds") or {}
    if any(k.startswith("gepa") for k in kinds):
        bits = []
        if kinds.get("gepa_select"):
            sel = f"parent picks {kinds['gepa_select']}"
            if (stats or {}).get("strategy"):
                sel += f" ({stats['strategy']})"
            bits.append(sel)
        if (stats or {}).get("mb_pass") or (stats or {}).get("mb_fail"):
            bits.append(f"minibatch gate {stats.get('mb_pass', 0)}✓ "
                        f"{stats.get('mb_fail', 0)}✗")
        if kinds.get("gepa_val_gate"):
            bits.append(f"full-val gates {kinds['gepa_val_gate']}")
        if summary.get("frontier") is not None:
            bits.append(f"pareto frontier {summary['frontier']}")
        if (stats or {}).get("minibatch_size"):
            bits.append(f"minibatch size {stats['minibatch_size']}")
        return "gepa", bits
    if any(k.startswith("skillopt") for k in kinds):
        bits = []
        ep, eps = (stats or {}).get("epoch"), (stats or {}).get("epochs")
        if ep is not None:
            bits.append(f"epoch {ep}" + (f"/{eps}" if eps else ""))
        if (stats or {}).get("step_in_epoch") is not None:
            bits.append(f"step {stats['step_in_epoch']} in epoch")
        if (stats or {}).get("lr") is not None:
            bits.append(f"edit budget {stats['lr']}"
                        + (f" ({stats['lr_schedule']})" if (stats or {}).get("lr_schedule") else ""))
        if kinds.get("skillopt_slow_update"):
            bits.append(f"epoch-boundary updates {kinds['skillopt_slow_update']}")
        return "skillopt", bits
    return "", []


def _algo(stats: dict | None, summary: dict, width: int, height: int, *,
          color: bool) -> list[str]:
    if height <= 0:
        return []
    name, bits = algo_panel(stats, summary)
    if not name:
        return _pad([], height)
    out = [_fit([(f"algorithm  {name}", _C.BOLD)], width, color)]
    for i in range(0, len(bits), 2):
        out.append(_fit([("  ", None),
                         (" · ".join(bits[i:i + 2]), _C.GREY)], width, color))
    return _pad(out, height)


# ---- diff panel (what the accepted candidate actually changed) --------------

def _diff(diff: dict | None, width: int, height: int, *, color: bool) -> list[str]:
    """Render a precomputed diff payload: ``{"title": str, "lines": [str]}``.

    The lines are produced by :mod:`cap_evolve.diffview` (which sanitizes every one of
    them — candidate files are model-authored) and simply cropped here, so the renderer
    stays pure and testable.
    """
    if height <= 1 or not diff:
        return _pad([], height)
    title = eventstream.sanitize(str(diff.get("title") or "changes"))
    out = [_fit([("changes  ", _C.BOLD), (title, _C.GREY)], width, color)]
    lines = list(diff.get("lines") or [])
    body = height - 1
    if len(lines) > body:
        lines, extra = lines[: body - 1], len(lines) - (body - 1)
        lines.append(_c(f"  … {extra} more line(s) — cap-evolve diff for the rest",
                        _C.GREY, color))
    out += [_crop_ansi(ln, width) for ln in lines]
    return _pad(out, height)


def _crop_ansi(line: str, width: int) -> str:
    """Crop to ``width`` VISIBLE columns. Shared with the home screen — see
    :func:`cap_evolve.eventstream.crop_ansi`."""
    return eventstream.crop_ansi(line, width)


def _footer(root, width: int, height: int, *, color: bool,
            hint: str = "") -> list[str]:
    text = hint or "Ctrl-C to detach (run continues)"
    room = width - len(str(root)) - 3
    return _pad([_c("─" * width, _C.GREY, color),
                 _fit([(str(root), _C.GREY), ("   ", None),
                       (_ell(text, room), _C.DIM)],
                      width, color)],
                height)


# ---- the pure renderer -----------------------------------------------------

def render_frame(reduced: dict, size: tuple[int, int] = (100, 30), *, color: bool = False,
                 root: str = "", activity=(), running: str | None = None,
                 totals: dict | None = None, elapsed: float | None = None,
                 algo_stats: dict | None = None, diff: dict | None = None,
                 hint: str = "", masthead: bool = False) -> str:
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
        # A caller handed us a malformed size (short tuple, None, non-numeric — e.g. a
        # `terminal_size` probe that failed on a pipe). 80x24 is the right answer: a
        # renderer that raises would take the whole watch loop down over a cosmetic
        # unknown, and the frame is clamped to `rows` either way.
        pass
    try:
        graph = reduced.get("graph") or {}
        summary = reduced.get("summary") or {}
        hdr = _header_lines(summary, graph, width, color=color, totals=totals,
                            elapsed=elapsed, masthead=masthead)
        sizes = plan_section_sizes(
            rows,
            header_rows=len(hdr),
            # TWO points minimum: "cumulative best" over a single point is not a series,
            # and because the chart is the surplus sink (_FILL) a one-point chart turned
            # every spare row into blank space — 23 empty rows on a 40-row terminal. That
            # is the ONLY frame the two agent-mode algorithms ever show from
            # `cap-evolve run`, which stops right after baseline.
            has_chart=len([n for n in (graph.get("nodes") or [])
                           if n.get("best_so_far") is not None]) >= 2,
            has_tree=True, has_activity=bool(activity or running),
            # Content size first (one row per entry), then the wrapped size as stretch:
            # every panel gets its rows before any panel gets its continuation lines.
            # 6 entries is the activity panel's CONTENT size even when the backlog holds
            # more: it restates facts the lineage and heatmap already show, so the rows
            # beyond six are worth less than a wrapped gate reason above it.
            activity_rows=1 + (1 if running else 0) + min(6, len(list(activity or ()))),
            tree_rows=len(_tree_rows(graph)) + 1,
            stretch={"tree": _tree_height(graph, width),
                     "activity": _activity_height(activity, running, width)},
            has_algo=bool(algo_panel(algo_stats, summary)[0]),
            has_heatmap=has_per_task(graph),
            has_diff=bool(diff and diff.get("lines")),
            heatmap_rows=1 + sum(1 for n in (graph.get("nodes") or [])
                                 if isinstance(n, dict) and (n.get("per_task") or {})),
            diff_rows=1 + len((diff or {}).get("lines") or []),
        )
        out: list[str] = []
        out += _header(hdr, sizes["header"])
        out += _chart(graph, width, sizes["chart"], color=color)
        out += _tree(graph, summary, width, sizes["tree"], color=color)
        out += _heatmap(graph, summary, width, sizes["heatmap"], color=color)
        out += _algo(algo_stats, summary, width, sizes["algo"], color=color)
        out += _diff(diff, width, sizes["diff"], color=color)
        out += _activity(activity, running, width, sizes["activity"], color=color)
        out += _footer(root, width, sizes["footer"], color=color, hint=hint)
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
        reduced = reduce_run(RunDir(Path(root)))
    except Exception:  # noqa: BLE001
        return {"graph": {"nodes": [], "root": "seed", "best_id": "seed"},
                "summary": {"run_id": Path(root).name}}
    try:
        # `run_config` is provenance the reducer does not project (it is not part of the
        # dashboard's schema, and dashboard.py is not ours to change). The live header
        # needs it: it is the only artifact that says WHICH spec produced this run.
        (reduced.setdefault("summary", {}) or {})["run_config"] = _run_config(root)
    except Exception:  # noqa: BLE001 — provenance is decoration, never fatal
        pass
    return reduced


def _run_config(root) -> dict:
    """The last ``run_config`` event's fields, sanitized. ``{}`` when the run logged none."""
    out: dict = {}
    path = Path(root) / "events.jsonl"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for ln in text.splitlines():
        if '"run_config"' not in ln:
            continue
        try:
            ev = json.loads(ln)
        except ValueError:
            continue
        if ev.get("kind") != "run_config":
            continue
        out = {k: eventstream.sanitize(str(v)) for k, v in ev.items()
               if k not in ("kind", "t") and v is not None}
    return out


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


def latest_diff(root, reduced: dict, width: int, *, color: bool,
                rows: int = 12) -> dict | None:
    """``{"title", "lines"}`` for the newest accepted candidate vs its parent.

    Impure by design (it reads the two snapshots off disk) so :func:`render_frame` stays
    pure. Returns ``None`` when the run kept no snapshots — a run whose store did not
    persist candidate dirs has nothing honest to show here.
    """
    try:
        from . import diffview
        nodes = [n for n in ((reduced.get("graph") or {}).get("nodes") or [])
                 if isinstance(n, dict) and n.get("status") == "accepted"]
        if not nodes:
            return None
        node = max(nodes, key=lambda n: n.get("iteration") or 0)
        cid = str(node.get("id") or "")
        parent = str(node.get("parent") or "seed")
        cand = Path(root) / "candidates"
        a, b = cand / parent, cand / cid
        if not (a.is_dir() and b.is_dir()):
            return None
        ta, tb = diffview.read_tree(a), diffview.read_tree(b)
        lines = diffview.render(ta, tb, width=width, color=color, context=1,
                               side_by_side=False, max_lines=max(2, rows))
        if not lines:
            return None
        return {"title": f"{parent} → {cid}   {diffview.summary_line(ta, tb)}",
                "lines": lines}
    except Exception:  # noqa: BLE001 — an optional panel must never kill the view
        return None


def _drive(root, feed, *, stream, color: bool, poll: float = 0.4,
           show_diff: bool = False, reserved_rows: int = 0) -> str | None:
    """The one loop both modes share: fold events → repaint on a dirty flag + tick."""
    activity: deque = deque(maxlen=8)
    totals: dict = {}
    algo_stats: dict = {}
    diff: dict | None = None
    reduced = _reduce(root)
    dirty, reason, done = False, None, False
    hint = ("Ctrl-C to detach (run continues)" if show_diff else
            "Ctrl-C to detach · --diff shows what each accepted candidate changed")
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
                        fold_algo_stats(ev, algo_stats)
                        line = eventstream.render_line(ev, None)
                        if line:
                            activity.append(line)
                        last_event = time.monotonic()
                    dirty = True
                cols, rows_avail = terminal_size(stream)
                size = (cols, max(4, rows_avail - reserved_rows))
                if dirty:
                    reduced = _reduce(root)
                    if show_diff:
                        diff = latest_diff(root, reduced, size[0], color=color)
                    dirty = False
                running = None if done else (
                    f"{_spinner()} working… {_fmt_dur(time.monotonic() - last_event)} "
                    f"since last event")
                painter.paint(render_frame(reduced, size, color=color,
                                           root=root, activity=activity, running=running,
                                           totals=totals, algo_stats=algo_stats,
                                           diff=diff, hint=hint,
                                           masthead=bool(reserved_rows)))
        except KeyboardInterrupt:
            return "interrupt"
        finally:
            if prev is not None:
                try:
                    signal.signal(signal.SIGTERM, prev)
                except (ValueError, OSError):
                    # Restoring the previous SIGTERM handler is best-effort cleanup:
                    # `signal.signal` raises ValueError off the main thread and OSError
                    # on platforms that refuse the signal. We are already unwinding, so
                    # raising here would mask the real exit reason with a teardown error.
                    pass
    return reason


def headline(stream, *, color: bool, meta: dict | None = None) -> int:
    """Print the brand headline ONCE, above the repaint region.

    Deliberately not part of the frame: the capybara is 9 rows tall and the frame's
    height budget is for live data. Printed before the painter starts, it stays in
    scrollback (and in a screen recording) without costing a row every repaint.

    ``meta`` is a reduced run; its :func:`run_meta` pairs fill the block beside the
    logo, turning nine rows of empty space into the run's identity card.
    """
    if not color:
        return 0  # the mark only exists in truecolor; a pipe gets the line log anyway
    try:
        from . import branding
        cols, rows = terminal_size(stream)
        pairs = tuple(run_meta((meta or {}).get("summary") or {})) if meta else ()
        art = branding.banner(cols, color=True, lines=("",) if pairs else (),
                              pairs=pairs)
        # Only when the frame can still breathe underneath it. The caller subtracts
        # these rows from the frame budget, so the headline stays pinned above the
        # repaint region instead of scrolling away on the first paint.
        if not art or len(art) + 18 > rows:
            return 0
        print("\n".join(art), file=stream, flush=True)
        # +2: the shell line the view was launched from, and the newline the painter
        # writes after each frame. One row of overshoot scrolls the headline away.
        return len(art) + 2
    except Exception:  # noqa: BLE001 — decoration must never block the view
        return 0


def watch(root, *, stream=None, color: bool | None = None, from_start: bool = True,
          idle_timeout: float | None = None, poll: float = 0.4,
          should_stop=None, show_diff: bool = False) -> str | None:
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
    used = headline(stream, color=color, meta=_reduce(root))
    return _drive(root, _live_feed(events, offset=offset, idle_timeout=idle_timeout,
                                   poll=poll, should_stop=should_stop),
                  stream=stream, color=color, poll=poll, show_diff=show_diff,
                  reserved_rows=used)


def _is_tty(stream) -> bool:
    try:
        return bool(stream.isatty())
    except Exception:  # noqa: BLE001
        return False


def _copy_rollouts(src: Path, scratch: Path, ev: dict) -> None:
    """Copy the rollouts an ``evaluate`` event just measured into the replay scratch dir.

    Per-candidate per-task rewards are reconstructed by the reducer from
    ``rollouts/<split>/<task>__<tag>__t<k>.json``, which the replay scratch dir did not
    have — so the per-task heatmap showed only the seed row (its per-task data comes
    from ``baseline.json``) while the lineage above it listed every candidate. Copying
    them as their ``evaluate`` event arrives keeps replay honest: the panel never shows a
    measurement the log has not reached yet.
    """
    if ev.get("kind") != "evaluate" or not ev.get("tag"):
        return
    split = str(ev.get("split") or "val")
    from_dir = src / "rollouts" / split
    if not from_dir.is_dir():
        return
    to_dir = scratch / "rollouts" / split
    to_dir.mkdir(parents=True, exist_ok=True)
    tag = str(ev["tag"]).replace("/", "_")
    for f in sorted(from_dir.glob(f"*__{tag}__t*.json")):
        try:
            shutil.copy2(f, to_dir / f.name)
        except OSError:  # noqa: PERF203 — one unreadable rollout must not stop the replay
            continue


def replay(src, *, stream=None, color: bool | None = None, speed: float = 1.0,
           max_gap: float = 1.0, banner: str | None = None,
           show_diff: bool = False) -> None:
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
    # The masthead describes the recorded run, so it is built from the SOURCE dir (the
    # scratch replay dir has no events yet at this point). ``+1`` for the banner row
    # already printed above it: unbudgeted, it scrolled the top of the masthead away.
    reserved = 0
    if tty:
        reserved = headline(stream, color=color, meta=_reduce(src))
        if reserved and banner:
            reserved += 1

    with tempfile.TemporaryDirectory(prefix="capevolve-replay-") as d:
        scratch = Path(d) / src.name  # keeps the header's run_id honest, not "tmpXXXX"
        scratch.mkdir()
        log = scratch / "events.jsonl"
        painter = _Painter(stream, inline=tty)
        reduced = _reduce(scratch)
        totals: dict = {}
        algo_stats: dict = {}
        diff: dict | None = None
        activity: deque = deque(maxlen=8)
        with painter:
            prev_t = None
            for ev in events:
                with log.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(ev) + "\n")
                for name, kind in (("baseline.json", "baseline"), ("final.json", "finalize")):
                    if ev.get("kind") == kind and (src / name).exists():
                        shutil.copy2(src / name, scratch / name)
                _copy_rollouts(src, scratch, ev)
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
                fold_algo_stats(ev, algo_stats)
                line = eventstream.render_line(ev, None)
                if line:
                    activity.append(line)
                    if not tty:  # piped: the line log IS the output
                        print(line, file=stream, flush=True)
                reduced = _reduce(scratch)
                if tty:
                    _cols, _rows = terminal_size(stream)
                    size = (_cols, max(4, _rows - reserved))
                    if show_diff:
                        # Snapshots live in the SOURCE run dir, not the replay scratch.
                        diff = latest_diff(src, reduced, size[0], color=color)
                    painter.paint(render_frame(reduced, size, color=color,
                                               root=str(src), activity=activity,
                                               totals=totals, algo_stats=algo_stats,
                                               diff=diff, masthead=bool(reserved),
                                               hint="replay of a recorded run · "
                                                    "Ctrl-C to stop"))
            if not tty:
                # Still end on a frame so a piped replay shows the same final state.
                print(render_frame(reduced, (terminal_size(stream)[0], 200), color=color,
                                   root=str(src), activity=activity, totals=totals,
                                   algo_stats=algo_stats),
                      file=stream, flush=True)
        if banner:
            print(_c(banner, _C.YELLOW, color), file=stream, flush=True)


if __name__ == "__main__":  # tiny self-check: the budget invariant holds everywhere
    for r in range(0, 200):
        assert sum(plan_section_sizes(r).values()) <= r, r
        s = plan_section_sizes(r, stretch={"tree": 99, "activity": 99}, tree_rows=4,
                               has_heatmap=True, heatmap_rows=3)
        assert sum(s.values()) <= r, (r, s)
        # ...and every row is spent once the frame is big enough to hold the sections
        assert r < 14 or sum(s.values()) == r, (r, s)
    assert render_frame({"summary": None}, (10, 5))  # malformed → placeholder, no raise
    print("tui self-check ok")
