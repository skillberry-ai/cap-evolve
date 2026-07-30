# Getting started

Your first successful cap-evolve run, in two minutes, with **no API key**.

## Prerequisites
- Python **3.10+** and **git**.

## 1. Clone and enter

```bash
git clone https://github.com/skillberry-ai/cap-evolve.git
cd cap-evolve
```

## 2. Create a clean environment and install the core

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install ./core          # package: cap-evolve-core, CLI: cap-evolve (zero runtime deps)
cap-evolve version          # verify
```

> If your default pip index requires auth, append `--index-url https://pypi.org/simple`.

## 3. Run the zero-API toy example

`toy_calc` is a deterministic stand-in agent that only answers correctly when its system
prompt contains a `[CALC]` marker. The `mock` optimizer adds the marker, so the score
provably rises — **no model is called**.

```bash
bash examples/toy_calc/run.sh
```

Expected output — the seed prompt scores `0.0` on val; the optimized prompt is
gate-accepted and scores `1.0` on the sealed test split:

```text
baseline_val 0.0  ->  test_reward 1.0   (gate-accepted, test sealed) + dashboard.html
```

This is exactly what `core/tests/test_e2e_slice.py` asserts. The script prints a working
directory; open the `dashboard.html` it writes in any browser to see the run (KPIs,
per-iteration diffs, the tasks × iterations heatmap).

## 4. Watch a run live in the terminal

A run is otherwise silent until it finishes. `--follow` prints progress from the run's
`events.jsonl` — the same typed event stream the web dashboard reads, so the two can
never disagree:

```bash
cap-evolve run --spec .capevolve/project/capevolve.yaml --follow
```

```text
[14:02:11] splits frozen  train=4 val=2 test=2 (test sealed)
[14:02:12] baseline  val=0.0000 ±0.0000
[14:02:40] ACCEPT  cand_0001  val=1.0000 (parent 0.0000)  — paired Δ̄=+1.0000 > 0  [$0.0620 · 4.1k tok]
[14:03:05] reject  cand_0002  val=1.0000 (parent 1.0000)  — paired Δ̄=+0.0000 <= 0  [$0.1240 · 8.3k tok]
[14:03:31] FINALIZE  test=1.0000 (baseline 0.0000, Δ+1.0000)  best=cand_0001
```

Progress goes to **stderr**; stdout stays the machine-readable final JSON, so
`cap-evolve run --follow > result.json` still works for scripts. Output is plain text
whenever the stream is not a TTY (piped, CI, `NO_COLOR`) — no ANSI in your logs.

To watch a run started elsewhere (another shell, `nohup`, a CI job), attach to its run
dir instead:

```bash
cap-evolve tail                                    # newest run under .capevolve/
cap-evolve tail .capevolve/run_20260130_140211 --from-start
```

`tail` waits for the run dir to appear, so you can attach before the run creates it. It
exits `0` when the run finishes, `2` on a path that can never be a run dir, and `3` when
`--idle-timeout` elapses with no events — so a script can tell a timeout from a result.

The `[$… · … tok]` meter is the run's own recorded spend: runner cost from `evaluate`
events plus optimizer cost from `step` events, matching `Spent.total_usd` in `state.json`.
Event text is stripped of control characters before it reaches your terminal, so an
optimizer's stderr can never move the cursor, clear the screen, or forge a progress line.

### The output degradation ladder

Live output adapts to the terminal it actually has. There are exactly five rungs, and
`cap-evolve tail --ladder` prints which one this invocation is on:

| Rung | Detected by | Output |
|---|---|---|
| `full` | TTY, `TERM` not `dumb`/`unknown`, no `NO_COLOR` | ANSI colour + Unicode |
| `plain` | TTY + `NO_COLOR` present (any value, incl. empty) | same text, zero escape bytes |
| `dumb` | TTY + `TERM=dumb` / `unknown`, no `FORCE_COLOR` | no colour, append-only lines |
| `pipe` | not a TTY (redirect, CI) | plain lines, grep-clean logs |
| `none` | stream missing/closed (`2>&-`) | nothing (following disables itself) |

`NO_COLOR` is presence-based per [no-color.org](https://no-color.org): `export NO_COLOR`
with no value demotes, same as `NO_COLOR=1`. `FORCE_COLOR` is the one override in the
other direction, for a colour-capable terminal that reports `TERM=dumb` (some CI runners,
`emacs -nw`); `NO_COLOR` still wins over it. `CI` is deliberately *not* a demotion signal —
`isatty` already covers real CI, and demoting on it would break `docker run -t`.

Nothing on the ladder repaints the screen or moves the cursor — output is append-only at
every rung, so there is no live layout to overflow on a resize and no terminal width to
budget. That is a deliberate scope reduction against issue #144's items 2 and 4 (height
budget, width detection): both presuppose output that takes over the screen, and this
does not. A future repainting view would need `dashboard._term_width` and that item
re-opened.

Under a non-UTF-8 stream (`PYTHONIOENCODING=ascii`, `LC_ALL=C`, a legacy Windows
console) glyphs transliterate rather than crash or print mojibake: `±` → `+/-`,
`Δ` → `d`, `—` → `-`.

### When something crashes

An unhandled crash writes a **forensic log** and prints one line pointing at it:

```text
cap-evolve run crashed: RuntimeError: optimizer died
forensic log (redacted, safe to attach to a bug report): .capevolve/run_…/crash-20260730-140455-8134-41207.json
```

It records the version, argv, python/platform, the terminal rung and encoding, the
traceback, and the last 25 events seen — enough to file a bug without reproducing it.
It lands next to the run when there is one, else under
`${XDG_CACHE_HOME:-~/.cache}/cap-evolve/crashes/`, mode `0600`, with the oldest pruned
beyond 50 files. The filename carries pid and thread id and is created with `O_EXCL`, so
two handlers firing on the same failure in the same second each keep their own record
instead of one truncating the other.

The whole payload passes through the same secret redactor the dashboard uses. That
redactor scrubs secret-looking *keys*, secret-shaped *values*, **and** the literal values
of every env var in this process that looks like credential material regardless of what
it was named — so a bare high-entropy token exported as `MODEL_ENDPOINT_SUFFIX` is masked
too. Ctrl-C also writes a log (the exit code is unchanged). A dying live view is handled
the same way: the run continues, the reason is on disk, and the final JSON on stdout
gains `"follow": "stopped"` so automation can see it without parsing stderr.

## 5. Where to next

| You want to… | Go to |
|---|---|
| Understand what cap-evolve optimizes and how | [`../README.md`](../README.md) · [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Set up a real optimizer/runner (credentials, dashboard) | [`INSTALL.md`](INSTALL.md) |
| Optimize your own agent + benchmark | [`OPTIMIZE_YOUR_OWN.md`](OPTIMIZE_YOUR_OWN.md) |
| See real benchmark results | [`RESULTS.md`](RESULTS.md) |
| Something failed | [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) |
