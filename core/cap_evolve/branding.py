"""Brand surface for the ``cap-evolve`` CLI: the capybara mark, the wordmark, the
home screen, and the per-command help. Stdlib only (``core/`` has zero runtime deps).

Everything here is a **pure function of (width, color depth)** and returns a list of
lines, so every screen is testable without a terminal.

The mark is the project's capybara logo (``docs/assets/cap-evolve-logo.png``) reduced
offline to an 18x9 half-block grid and committed as the :data:`LOGO_PIXELS` constant —
two RGB triples per character cell, painted with ``▀`` (top pixel = foreground, bottom
pixel = background). No Pillow, no PNG decoding at runtime, byte-identical everywhere.

Degradation is deliberate and stops at two tiers:

* **truecolor** (``COLORTERM=truecolor``/``24bit``): the capybara.
* **anything else** (256/16-color, ``NO_COLOR``, ``TERM=dumb``, a pipe, a terminal
  narrower than :data:`MIN_LOGO_COLS`): the wordmark alone, no art.

There is deliberately no 256-color or ASCII tier. The 6x6x6 xterm cube has no usable
brown, so a quantized capybara renders as pink-and-olive noise, and a thresholded
silhouette reads as a white blob — neither is the logo. Shipping nothing is honest;
shipping a blob and calling it the mark is not.
"""

from __future__ import annotations

import os

from .eventstream import crop_ansi

__all__ = ["banner", "home", "help_for", "wordmark", "color_depth", "COMMANDS",
           "ALGORITHMS", "TAGLINE", "LOGO_COLS", "LOGO_ROWS", "MIN_LOGO_COLS"]

#: The wordmark tagline. Product copy — keep it one short line.
TAGLINE = "watch capability evolve"

#: Brand purple (#7c5cff), truecolor. Falls back to plain magenta at lower depth.
_PURPLE_RGB = (124, 92, 255)

LOGO_COLS = 18
LOGO_ROWS = 9

#: Below this many columns the logo is omitted entirely (the wordmark still renders).
MIN_LOGO_COLS = 64

#: 18x9 half-block capybara: one row per text line, 18 cells per row, 12 hex chars per
#: cell (top RGB then bottom RGB); ``......`` means "transparent, leave the terminal
#: background alone". Derived once from docs/assets/cap-evolve-logo.png.
LOGO_PIXELS = """\
..................aaa4a9beb7ba0e455d243f521077961979960d384e1b748f050e1f0b2b3e05142600102329323e071a2c00102407182b00112607182a001125051628061a2e01162a48403e104c642621261d88a60216290d4e6813637e64646d046281......414d5a
a8a0a41047600748620d6d8c0f7190050e1e071527061829051021001327001225222f3d061a2da59582a29387dbb891968b7de0b991ac9c89d8b088b19d86dbb0877b6e5f9a75524a2f1d1e140d584b444e3f3502162a061c2e01041302172a0c445b020919037394073146
0b789a0523380616280412230617270214260010240615282c343e968472bb9a79b68c67ac7f5596714f986d46946944b4865a563c26c8a27b19181999704c5c402793664195653d4532227550324b4039424f5a65564d576d70021023242b31041729000f23020e1e031526
041324031627031426011022091729726f6e847b7393837aa38872635c5a9b7d627b634e9f7b589d7754936b47ac81596b503bb18358533f2e9e724b9d754f976f4ca8794f9c6f485f432f5a3b244d6e7e0824301747580a3a4c434a476a604d0815243e3835001223000b20
000c1e010f22343e4738393b7e6e6447382e555255231f1f645d5a4c433d886a50907254a97f589d734ca579518e633e8e633e956842835a389a6c438f643f8f623b996a428d603a7d53318f60380b0d0f422a1702232f26130776503181522d604e403f3a38000b21001125
000e20000a1c474545555250533f2f76583f382e2748332441362d5443359070519b78579f734ca97d559a6d458e633d9669417c532f8a5e376a4324805631623d207e522e643e20784d2b5f3c1f6a4426784e2c7a4f2d794f2e63462f252b31272b302d282557483bab7a4e
000a1b0111213f434714202d896d537464564e362541302167513e544334a2805f6a574498714e6147326a4728432b1851331a2a190b41271222140943281336210f4b2e165f391c6c45245e391e7349283331313938370d25350a1c2a4130226e4c31ad7b50af7d52a1744c
000d1d1c2b3a000d1d1525340916240a1b2b27292b05182930271e0715242b221a1721283122164e3825160f08120800160e0727180c2e1c0e382515502f14281d17443b300b2934233f490a44550816222b201632251b92643c9e6e46ac7f57ad7f569d6f4790623c825532
303a450b1622353f4a0c182336414b0d1924343f4a101b262d3a47131d283c444b142734584f4a1231412f3235303a450b0c0d141516060d130e0b09050f17281a100a0e0f3f26131e1d185533196d4727734c2c9e70478d623d9e724b9165418c5f3b8156337148286e4626"""


def color_depth(color: bool = True, env: dict | None = None) -> str:
    """``"truecolor"`` / ``"ansi"`` / ``"none"`` — the palette the caller may use.

    ``color=False`` (a pipe, ``--no-color``) always yields ``"none"``; ``NO_COLOR`` and
    ``TERM=dumb`` are honored even when the caller asked for color.
    """
    env = os.environ if env is None else env
    if not color or env.get("NO_COLOR") or str(env.get("TERM", "")).lower() == "dumb":
        return "none"
    ct = str(env.get("COLORTERM", "")).lower()
    if "truecolor" in ct or "24bit" in ct:
        return "truecolor"
    if "direct" in str(env.get("TERM", "")).lower():
        return "truecolor"
    return "ansi"


def _purple(depth: str) -> str:
    if depth == "truecolor":
        r, g, b = _PURPLE_RGB
        return f"\x1b[38;2;{r};{g};{b}m"
    return "\x1b[35m" if depth != "none" else ""


_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_GREY = "\x1b[90m"
_CYAN = "\x1b[36m"


def _s(text: str, code: str) -> str:
    return f"{code}{text}{_RESET}" if code else text


class _Pal:
    """The four styles every screen uses, gated on the depth once.

    A palette object rather than module constants so ``depth == "none"`` yields the
    empty string for every style — the only way a screen can be provably ANSI-free.
    """

    __slots__ = ("bold", "grey", "cyan", "warn", "brand")

    def __init__(self, depth: str):
        on = depth != "none"
        self.bold = _BOLD if on else ""
        self.grey = _GREY if on else ""
        self.cyan = _CYAN if on else ""
        self.warn = "\x1b[33m" if on else ""
        self.brand = (_BOLD + _purple(depth)) if on else ""


def logo_lines(depth: str) -> list[str]:
    """The capybara as :data:`LOGO_ROWS` lines, or ``[]`` at any depth but truecolor."""
    if depth != "truecolor":
        return []
    out = []
    for row in LOGO_PIXELS.strip("\n").split("\n"):
        line = []
        for i in range(0, len(row), 12):
            top, bot = row[i:i + 6], row[i + 6:i + 12]
            t_off, b_off = top.startswith("."), bot.startswith(".")
            if t_off and b_off:
                line.append(" ")
                continue
            def rgb(h: str) -> tuple[int, int, int]:
                return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            if t_off:
                r, g, b = rgb(bot)
                line.append(f"\x1b[38;2;{r};{g};{b}m▄{_RESET}")
            elif b_off:
                r, g, b = rgb(top)
                line.append(f"\x1b[38;2;{r};{g};{b}m▀{_RESET}")
            else:
                r, g, b = rgb(top)
                r2, g2, b2 = rgb(bot)
                line.append(f"\x1b[38;2;{r};{g};{b}m\x1b[48;2;{r2};{g2};{b2}m▀{_RESET}")
        out.append("".join(line))
    return out


def wordmark(depth: str, *, tagline: bool = True) -> list[str]:
    """``cap-evolve`` + tagline, 2 lines (1 when ``tagline`` is false)."""
    p = _Pal(depth)
    out = [_s("cap-evolve", p.brand)]
    if tagline:
        out.append(_s(TAGLINE, p.grey))
    return out


#: Label column of a masthead pair. Wide enough for the longest label we use.
PAIR_LABEL_COLS = 10


def banner(width: int = 100, *, color: bool = True, env: dict | None = None,
           lines: tuple[str, ...] = (),
           pairs: tuple[tuple[str, str], ...] = ()) -> list[str]:
    """The brand headline: capybara on the left, wordmark + ``lines``/``pairs`` right.

    ``pairs`` are ``(label, value)`` rows rendered as an aligned two-column block — a
    masthead, which is what stops the 9 rows beside the logo from being empty space.
    The label is grey and the value is plain, so the values are what the eye lands on.

    Falls back to the wordmark alone when the depth is not truecolor or the terminal is
    narrower than :data:`MIN_LOGO_COLS`. Never returns a line wider than ``width``
    visible columns (the art's escapes are not counted — they occupy no columns).
    """
    depth = color_depth(color, env)
    p = _Pal(depth)
    room = max(8, width - (LOGO_COLS + 2) - PAIR_LABEL_COLS)
    text = wordmark(depth) + [_s(t, p.grey) for t in lines]
    text += [_s(str(label)[:PAIR_LABEL_COLS].ljust(PAIR_LABEL_COLS), p.grey)
             + _s(str(value)[:room], p.bold if i == 0 else "")
             for i, (label, value) in enumerate(pairs)]
    art = logo_lines(depth) if width >= MIN_LOGO_COLS else []
    if not art:
        return text
    gap = "  "
    pad = " " * (LOGO_COLS + len(gap))
    out = []
    for i in range(max(len(art), len(text))):
        right = text[i] if i < len(text) else ""
        left = (art[i] + gap) if i < len(art) else pad
        out.append((left + right).rstrip())
    return out


# ---- command catalog -------------------------------------------------------
# (name, group, one-line summary, usage, examples). The single source of truth for
# the home screen, ``cap-evolve help``, and each subcommand's own --help epilog.

COMMANDS: dict[str, dict] = {
    "init": {
        "group": "set up",
        "summary": "scaffold .capevolve/project and write capevolve.yaml",
        "usage": "cap-evolve init [--project DIR] [--algorithm NAME] [--optimizer NAME] [--yes]",
        "long": ("Creates the project layout the rest of the pipeline expects: an adapter\n"
                 "stub, a capevolve.yaml spec, and PROJECT.md. Prompts for the few choices\n"
                 "that matter (capability path, algorithm, optimizer) and defaults the rest.\n"
                 "Nothing is overwritten unless you pass --force."),
        "examples": ["cap-evolve init",
                     "cap-evolve init --algorithm gepa --optimizer claude-code --yes",
                     "cap-evolve init --project ./my/.capevolve/project"],
        "next": "cap-evolve doctor",
    },
    "doctor": {
        "group": "set up",
        "summary": "readiness check: what is missing and the command that fixes it",
        "usage": "cap-evolve doctor [--project DIR] [--json]",
        "long": ("Every precondition a run needs, each with a verdict and a fix:\n"
                 "spec file, adapter, seed capability, skills registry, split ids,\n"
                 "optimizer CLI on PATH, and the `cap-evolve check` adapter contract."),
        "examples": ["cap-evolve doctor", "cap-evolve doctor --json"],
        "next": "cap-evolve run --tui",
    },
    "check": {
        "group": "set up",
        "summary": "the hard gate: prove the adapter contract holds (deterministic scorer)",
        "usage": "cap-evolve check [project_dir | --project DIR]",
        "long": ("Loads adapters/adapter.py and proves: no stub methods, tasks() is\n"
                 "non-empty and stable, the scorer is deterministic, materialize() is pure.\n"
                 "`cap-evolve run` refuses to spend budget until this passes."),
        "examples": ["cap-evolve check", "cap-evolve check .capevolve/project",
                     "cap-evolve check --project .capevolve/project"],
        "next": "cap-evolve run",
    },
    "algorithms": {
        "group": "set up",
        "summary": "the optimization algorithms and how to select each",
        "usage": "cap-evolve algorithms [NAME] [--json]",
        "long": "What each algorithm is for, when to prefer it, and the exact spec lines.",
        "examples": ["cap-evolve algorithms", "cap-evolve algorithms gepa"],
        "next": "cap-evolve init --algorithm <name>",
    },
    "splits": {
        "group": "set up",
        "summary": "freeze a seeded train/val/test split over task ids",
        "usage": "cap-evolve splits --ids a,b,c [--seed N] [--ratios 0.5,0.25,0.25]",
        "long": "Prints the split as JSON. The run freezes its own split; this is for inspection.",
        "examples": ["cap-evolve splits --ids t1,t2,t3,t4 --seed 0"],
    },
    "run": {
        "group": "optimize",
        "summary": "the whole pipeline: check → baseline → algorithm → finalize → report",
        "usage": "cap-evolve run [--spec FILE] [--tui|--follow] [--resume] [--plan-only] [--dry-run]",
        "long": ("Sequences the phase skills, threading one run dir between them. stdout is\n"
                 "the machine-readable JSON result; --tui/--follow write the live view to\n"
                 "stderr, so `cap-evolve run --tui > result.json` keeps working."),
        "examples": ["cap-evolve run --tui",
                     "cap-evolve run --plan-only",
                     "cap-evolve run --dry-run",
                     "cap-evolve run --max-iterations 20 --max-usd 5",
                     "cap-evolve run --resume --max-iterations 30",
                     "cap-evolve run --tui > result.json"],
        "next": "cap-evolve diff --best",
    },
    "estimate": {
        "group": "optimize",
        "summary": "pre-run cost estimate (call counts + a $ range), spends nothing",
        "usage": "cap-evolve estimate [--spec FILE] [--price-in $/MTok] [--price-out $/MTok]",
        "long": ("Calibrates from prior runs' real spend when any exist, else your\n"
                 "--price-in/--price-out, else a bundled approximate table."),
        "examples": ["cap-evolve estimate", "cap-evolve estimate --price-in 3 --price-out 15"],
    },
    "diff": {
        "group": "inspect",
        "summary": "see the actual edit a candidate made (unified or side-by-side)",
        "usage": "cap-evolve diff [CANDIDATE] [--vs OTHER|--best] [--stat] [--files] [--unified N]",
        "long": ("Every candidate is a snapshot under <run>/candidates/. This diffs two of\n"
                 "them. Default comparison is the candidate against its own parent, so you\n"
                 "see exactly what that iteration changed. --best diffs seed → best.\n"
                 "Side-by-side above 120 columns, unified below; --unified N forces unified."),
        "examples": ["cap-evolve diff --best",
                     "cap-evolve diff cand_0003",
                     "cap-evolve diff cand_0003 --vs cand_0001",
                     "cap-evolve diff --best --stat",
                     "cap-evolve diff cand_0002 --unified 5 --no-color"],
    },
    "watch": {
        "group": "inspect",
        "summary": "live view of a running (or finished) run",
        "usage": "cap-evolve watch [run_dir] [--base DIR] [--diff] [--idle-timeout S]",
        "long": ("Attaches to events.jsonl and repaints inline (scrollback survives).\n"
                 "--diff adds a panel showing what the latest accepted candidate changed.\n"
                 "Exit codes: 0 finished, 1 no runs, 2 impossible path, 3 idle timeout,\n"
                 "130 Ctrl-C."),
        "examples": ["cap-evolve watch", "cap-evolve watch --diff",
                     "cap-evolve watch .capevolve/run_20250101_120000"],
    },
    "tail": {
        "group": "inspect",
        "summary": "one line per event (pipe-friendly, no repaint)",
        "usage": "cap-evolve tail [run_dir] [--base DIR] [--from-start] [--idle-timeout S]",
        "long": "Same exit codes as watch. Use in CI logs where a repainting view is noise.",
        "examples": ["cap-evolve tail", "cap-evolve tail --from-start | tee run.log"],
    },
    "replay": {
        "group": "inspect",
        "summary": "re-feed a recorded run through the live view (--demo needs no API key)",
        "usage": "cap-evolve replay <run_dir>|--demo [--speed N] [--diff]",
        "long": "The same reducer and renderer as `watch`, driven by a recorded events.jsonl.",
        "examples": ["cap-evolve replay --demo", "cap-evolve replay --demo --speed 4",
                     "cap-evolve replay .capevolve/run_20250101_120000"],
    },
    "dashboard": {
        "group": "inspect",
        "summary": "launch the web dashboard over a base dir of runs",
        "usage": "cap-evolve dashboard [--base DIR] [--port N] [--no-open]",
        "long": "Needs the optional dashboard backend: pip install -e dashboard/backend.",
        "examples": ["cap-evolve dashboard", "cap-evolve dashboard --port 8080 --no-open"],
    },
    "version": {
        "group": "inspect",
        "summary": "print the cap-evolve version as JSON",
        "usage": "cap-evolve version",
        "long": "",
        "examples": ["cap-evolve version"],
    },
    "help": {
        "group": "inspect",
        "summary": "full help and examples for one command",
        "usage": "cap-evolve help [COMMAND]",
        "long": "",
        "examples": ["cap-evolve help", "cap-evolve help diff"],
    },
}

_GROUP_ORDER = ("set up", "optimize", "inspect")

#: Every algorithm: what each is for, and the EXACT spec lines that select it. An entry
#: carrying ``deprecated`` is listed last and rendered as deprecated -- it stays here so an
#: existing spec still resolves, not because anyone should pick it.
ALGORITHMS: dict[str, dict] = {
    "hill-climb": {
        "for": "the default. Parent is always the current best; one edit per iteration.",
        "prefer": "your first run, or feedback-poor binary tasks.",
        "mode": "deterministic",
        "spec": ["algorithm_skill: hill-climb",
                 "algorithm_focus: all        # all | cyclic | hardest-first"],
        "extras": "focus schedule",
    },
    "gepa": {
        "for": "sample-efficient reflective Pareto search (arXiv:2507.19457).",
        "prefer": "rollouts are expensive and the scorer gives rich per-task feedback.",
        "mode": "deterministic",
        "spec": ["algorithm_skill: gepa",
                 "max_metric_calls: 200",
                 "algorithm_args: \"--minibatch-size 4 --component-selector round_robin\""],
        "extras": "minibatch gate vs full-val gate, Pareto frontier",
    },
    "skillopt": {
        "for": "single lineage over epochs x mini-batches with a decaying edit budget.",
        "prefer": "you want annealing and per-epoch consolidation, not one-shot proposals.",
        "mode": "deterministic",
        "spec": ["algorithm_skill: skillopt",
                 "algorithm_args: \"--epochs 6 --lr-schedule cosine\""],
        "extras": "epoch boundaries, textual learning-rate schedule",
    },
    "evograph": {
        "for": "collaborative weakness-graph search; one solver agent per weakness.",
        "prefer": "nothing new — use agent-optimize, which fans the same work out behind the val gate.",
        "mode": "agent",
        "spec": ["algorithm_skill: evograph", "orchestration_mode: agent"],
        "extras": "weakness-graph tab (read from the run dir), whole-round revert",
        # Deprecated: kept so an existing spec still resolves and an old run dir still
        # reads, but never offered as a choice. It accepted merges on a self-reported
        # raw train delta -- no val split, no significance gate.
        "deprecated": "use agent-optimize (agent mode), or hill-climb | gepa | skillopt",
    },
    "agent-optimize": {
        "for": "free-form: the conversational agent owns the whole search.",
        "prefer": "the search needs judgement a fixed loop cannot express.",
        "mode": "agent",
        "spec": ["algorithm_skill: agent-optimize", "orchestration_mode: agent",
                 "stop_condition: \"stop when val gains stall for 3 rounds or $20 is spent\""],
        "extras": "free-form round log (no fixed iteration shape)",
    },
}


#: Rows an 80x24 terminal really has for the home screen: one goes to the shell line
#: the command was typed on, and overshooting by one scrolls the capybara off the top —
#: which loses the brand, the value prop and the golden path, and leaves the user
#: looking at the version string. The screen degrades to fit instead.
HOME_PROMPT_ROWS = 1


def home(width: int = 100, *, color: bool = True, env: dict | None = None,
         version: str = "", rows: int | None = None) -> list[str]:
    """The no-args home screen: brand, value prop, golden path, grouped commands.

    Adaptive in BOTH axes, the same way :func:`banner` already degrades by color depth:

    * every line is clipped to ``width`` (the command summaries used to run to 88
      columns and wrap on an 80-column terminal);
    * when ``rows`` cannot hold the full three-group command table (20 rows of it), the
      table condenses to one line per group listing just the command names — the user
      still learns every command exists, in 3 rows instead of 20.

    ``rows=None`` means "unlimited", for callers that are not a terminal.
    """
    depth = color_depth(color, env)
    p = _Pal(depth)
    clip = lambda ls: [crop_ansi(x, width) for x in ls]  # noqa: E731

    head = banner(width, color=color, env=env, lines=(
        "",
        "Measure a capability, let a coding agent edit it, and accept only",
        "what beats the baseline on a held-out split — with the test split",
        "sealed until the very end.",
    ))
    path = ["", _s("  Golden path", p.bold)]
    for n, cmd, why in (("1", "cap-evolve init", "scaffold the project + write capevolve.yaml"),
                        ("2", "cap-evolve doctor", "prove it is ready before spending a cent"),
                        ("3", "cap-evolve run --tui", "optimize, with the live view")):
        path.append(f"  {_s(n, p.grey)}  {_s(cmd.ljust(24), p.cyan)}  {_s(why, p.grey)}")

    full: list[str] = [""]
    for group in _GROUP_ORDER:
        full.append(_s(f"  {group}", p.bold))
        full += [f"    {_s(name.ljust(12), p.cyan)}{meta['summary']}"
                 for name, meta in COMMANDS.items() if meta["group"] == group]
        full.append("")
    compact: list[str] = [""]
    for group in _GROUP_ORDER:
        names = [n for n, m in COMMANDS.items() if m["group"] == group]
        compact.append(f"  {_s(group.ljust(9), p.bold)} {_s('  '.join(names), p.cyan)}")

    # Drop the grey explanation when it will not fit, rather than letting the
    # width clip mid-word: "…a real session through th" reads as a broken
    # renderer, while the label + command alone still tells the user what to type.
    def _hint(label: str, cmd: str, why: str) -> str:
        if len(f"  {label} {cmd} {why}") <= width:
            return f"  {_s(label, p.bold)} {_s(cmd, p.cyan)} {_s(why, p.grey)}"
        return f"  {_s(label, p.bold)} {_s(cmd, p.cyan)}"

    tail = [_hint("no API key? ", "cap-evolve replay --demo",
                  " replays a real session through the live view"),
            _hint("one command?", "cap-evolve help <command>",
                  "full help + copy-paste examples")]
    ver = ["", _s(f"  cap-evolve {version}", p.grey)] if version else []

    budget = None if rows is None else max(1, int(rows) - HOME_PROMPT_ROWS)
    out = head + path + full + tail + ver
    if budget is not None and len(out) > budget:
        out = head + path + compact + tail + ver
    # Still too short for even the compact form (a very short terminal): keep the top,
    # which is where the brand and the golden path are.
    return clip(out if budget is None else out[:budget])


def help_for(name: str | None = None, width: int = 100, *, color: bool = True,
             env: dict | None = None) -> list[str]:
    """Help for one command, or the command index when ``name`` is falsy/unknown."""
    depth = color_depth(color, env)
    p = _Pal(depth)
    meta = COMMANDS.get(str(name or ""))
    if meta is None:
        out = [_s("cap-evolve", p.brand) + _s("  " + TAGLINE, p.grey), ""]
        if name:
            out.append(_s(f"  unknown command: {name}", p.warn))
            out.append("")
        for group in _GROUP_ORDER:
            out.append(_s(f"  {group}", p.bold))
            for n, m in COMMANDS.items():
                if m["group"] == group:
                    out.append(f"    {_s(n.ljust(12), p.cyan)}{m['summary']}")
            out.append("")
        out.append(_s("  cap-evolve help <command>   for usage, notes and examples", p.grey))
        return out
    out = [_s(f"cap-evolve {name}", p.brand),
           _s(f"  {meta['summary']}", p.grey), "",
           _s("  usage", p.bold), f"    {meta['usage']}", ""]
    if meta.get("long"):
        for ln in str(meta["long"]).split("\n"):
            out.append(f"  {ln}")
        out.append("")
    out.append(_s("  examples", p.bold))
    for ex in meta.get("examples") or []:
        out.append(f"    {_s(ex, p.cyan)}")
    if meta.get("next"):
        out += ["", _s(f"  next: {meta['next']}", p.grey)]
    return out


def algorithms_screen(name: str | None = None, width: int = 100, *, color: bool = True,
                      env: dict | None = None) -> list[str]:
    """The algorithm chooser: what each is for + the exact spec lines to select it."""
    depth = color_depth(color, env)
    p = _Pal(depth)
    items = ([(name, ALGORITHMS[name])] if name in ALGORITHMS else
             sorted(ALGORITHMS.items(), key=lambda kv: bool(kv[1].get("deprecated"))))
    live = sum(1 for m in ALGORITHMS.values() if not m.get("deprecated"))
    out = [_s("cap-evolve algorithms", p.brand),
           _s(f"  {live} ways to search; the honesty gate is the same for all of them", p.grey), ""]
    if name and name not in ALGORITHMS:
        out.append(_s(f"  unknown algorithm: {name} — showing all", p.warn))
        out.append("")
    for n, m in items:
        tag = "agent-driven" if m["mode"] == "agent" else "deterministic loop"
        if m.get("deprecated"):
            tag = f"DEPRECATED — {m['deprecated']}"
            out.append(f"  {_s(n.ljust(15), p.bold + p.grey)}{_s(tag, p.warn)}")
        else:
            out.append(f"  {_s(n.ljust(15), p.bold + p.cyan)}{_s(tag, p.grey)}")
        out.append(f"    what   {m['for']}")
        out.append(f"    prefer {m['prefer']}")
        out.append(f"    extras {_s(m['extras'], p.grey)}")
        out.append(_s("    select it with these capevolve.yaml lines:", p.grey))
        for ln in m["spec"]:
            out.append(f"      {_s(ln, p.cyan)}")
        out.append("")
    out.append(_s("  cap-evolve init --algorithm <name>   writes those lines for you", p.grey))
    return out


if __name__ == "__main__":  # self-check: every screen renders at every width, ANSI-free
    import re
    _A = re.compile(r"\x1b\[[0-9;]*m")
    for w in (40, 80, 100, 200):
        for fn in (lambda: home(w, color=False), lambda: help_for("diff", w, color=False),
                   lambda: help_for(None, w, color=False),
                   lambda: algorithms_screen(None, w, color=False)):
            for line in fn():
                assert not _A.search(line), line
        for line in banner(w, color=False, pairs=(("spec", "x" * 200),)):
            assert not _A.search(line) and len(line) <= max(w, 18), (w, line)
    assert logo_lines("ansi") == [] and logo_lines("none") == []
    assert len(logo_lines("truecolor")) == LOGO_ROWS
    print("branding self-check ok")
