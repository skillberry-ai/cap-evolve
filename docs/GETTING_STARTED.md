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

## 4. Scaffold your own runnable project — `cap-evolve quickstart`

`toy_calc` runs *inside the repo*. `quickstart` writes the same kind of project into a
directory of your own, from a **free or local** preset, and asks nothing:

```bash
mkdir ~/my-run && cd ~/my-run
cap-evolve quickstart --yes              # or plain `cap-evolve quickstart` for one question
export CAPEVOLVE_MOCK_SCRIPT=~/my-run/.capevolve/mock_script.json
cap-evolve check .capevolve/project      # already green — no adapter to implement
cap-evolve run                           # sealed test number, $0
```

The `export` is not optional: it points the offline `mock` optimizer at the edit script
quickstart wrote. quickstart prints the exact line for your directory in its `next` list,
so copy it from there. Skip it and the optimizer proposes nothing — the run still exits 0
but seals `test_reward 0.0`, i.e. the baseline. (Since #248 it also says so loudly on
stderr rather than passing silently.)

| preset | cost | target runner | needs |
|---|---|---|---|
| `mock` (default) | $0 | offline deterministic stand-in | nothing at all |
| `local` | $0 | local OpenAI-compatible server | `ollama serve` **and** `ollama pull qwen2.5:3b` |
| `free` | $0 | Gemini free tier (OpenAI-compatible) | `GEMINI_API_KEY` exported |

**`--model` / `--base-url` need a preset with an endpoint.** `mock` is an offline
stand-in with neither, so passing them there is refused rather than silently ignored.

**A `doctor` failure does not fail the command.** quickstart's contract is "the project
was scaffolded", and it was; health is advisory about your *environment* and is reported
in the `health` key and on stderr. `cap-evolve check` and `cap-evolve run` are the gates
that actually refuse.

**How this differs from `intake`.** `quickstart` is the zero-question *fast path*: it
picks a preset and writes a project that is already `cap-evolve check`-green, so the very
next command is `cap-evolve run`. `intake` is the guided *interview* for your own
capability and benchmark — it mines your working dir, asks what to optimize, and leaves an
adapter **stub** you implement before the `implement-and-check` gate opens. Use
`quickstart` to see the pipeline work; use `intake` when you have real work to optimize.

**Non-interactive.** `--yes`, `--preset`, or a non-terminal stdin all mean "defaults,
never read stdin" — so quickstart in CI or behind a pipe cannot hang.

**No secrets.** quickstart reports which credential env var is *present* — never a value,
a prefix, or a length — and writes only the variable's **name** into the project. A base
URL carrying `user:token@` has its credential stripped, and a non-default endpoint is
reported as `<custom>`.

Stdout is exactly one JSON object; the human summary goes to stderr.

## 5. Where to next

| You want to… | Go to |
|---|---|
| Understand what cap-evolve optimizes and how | [`../README.md`](../README.md) · [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Set up a real optimizer/runner (credentials, dashboard) | [`INSTALL.md`](INSTALL.md) |
| Optimize your own agent + benchmark | [`OPTIMIZE_YOUR_OWN.md`](OPTIMIZE_YOUR_OWN.md) |
| See real benchmark results | [`RESULTS.md`](RESULTS.md) |
| Something failed | [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) |
