# Getting started

Your first successful cap-evolve run, in two minutes, with **no API key** — then a
real one, cheaply, before committing to anything expensive.

## The ladder

Three rungs, so "see it work" and "run it for real" are not the same decision. Every
figure is either **measured** on the run it describes or labelled an **estimate** with
its arithmetic — no rung is advertised on a guess.

| Rung | What is real | Runtime | Cost | How |
|---|---|---|---|---|
| **1. free** | pipeline, gate, sealed test — **no model** | seconds | **$0** | [`examples/toy_calc`](../examples/toy_calc/) · §3 |
| **2. cheap-real** | **a real LLM**, real gate, real sealed test | **36 s**–**5.4 min** measured | **$0** local, or **$0.54** measured with a hosted proposer | [`examples/cheap_real`](../examples/cheap_real/) · §4 |
| **3. full** | a published benchmark (τ²-bench airline) | hours | ~$148 | [`REPRODUCE_tau2.md`](REPRODUCE_tau2.md) |

### Where rung 2's numbers come from

The preset is 20 tasks → train 10 / val 5 / test 5, `num_trials: 1`,
`max_iterations: 3`. So the call counts are fixed and checkable:

```
runner calls   = val 5 x trials 1 x (1 baseline + 3 candidates)  = 20
               + test 5 x (best + baseline seed)                 = 10   → 30 calls
proposer calls = max_iterations                                  =  3
```

- **Free variant** — local `ollama/llama3.2:3b` runner + `mock` proposer.
  **MEASURED: 36 s wall clock, $0.00.** A local model is not metered and the `mock`
  proposer makes no network call at all, so this is $0 by construction, not by luck.
- **Cheap variant** — same local runner, `claude-code`/Haiku proposer. The 30 runner
  calls stay $0; only the 3 proposals cost anything. **MEASURED** from the run's own
  accounting (`state.json` → `spent`): **$0.5427 total, 321 s (5.4 min) wall clock,
  exactly the 30 `metric_calls` the formula above predicts.** Per-proposal spend was
  $0.159 / $0.199 / $0.185, so budget **~$0.15–0.35 per iteration**. Proposal latency
  dominates: 293 s of the 321 s was the optimizer, and only 27 s the runner.
- **Hosted-runner variant** — no local model available, so the runner is
  `claude-haiku-4-5` too. 30 runner calls at the bundled price table's Haiku rate and
  cap-evolve's assumed 3 000 in / 800 out tokens per rollout:
  `30 x (3000 x $1.00 + 800 x $5.00) / 1e6` ≈ **$0.21 — an ESTIMATE**, derived from
  `core/cap_evolve/pricing.py`, not measured.

The preset's `max_usd: 3.0` / `max_optimizer_usd: 2.5` are hard stops, so rung 2
cannot quietly become rung 3. Rung 3's ~$148 is the committed τ² run's own reported
optimizer spend ([`RESULTS.md`](RESULTS.md)).

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

## 4. Run the cheap FIRST REAL example (rung 2)

`toy_calc` proves the machinery but calls no model. This one calls a real one — and
still finishes in minutes for $0, so there is a rung between it and the multi-hour
τ² run.

The task: normalize a human-written date (`"the 22nd of November, 1963"`) to ISO
(`1963-11-22`), scored by exact match. The seed prompt is a generic "you are a helpful
assistant", so a small model replies in prose and scores 0; the fix is an output
contract — exactly what an optimizer is good at proposing.

```bash
pip install litellm                      # the runner's provider shim
ollama pull llama3.2:3b                  # ~2 GB, free, local

bash examples/cheap_real/run.sh          # rung 2, free variant
```

For the paid variant, let a real agent propose the edit instead of `mock` (the runner
stays local and free):

```bash
CHEAP_REAL_OPTIMIZER=claude-code CHEAP_REAL_OPT_MODEL=claude-haiku-4-5 \
  bash examples/cheap_real/run.sh
```

No local model? Point the runner at a cheap hosted one — one env var, no code change:

```bash
CHEAP_REAL_MODEL=claude-haiku-4-5 bash examples/cheap_real/run.sh
```

`run.sh` is also the **programmatic entry point**: every knob is an env var with a
default and the last object on stdout is the run's summary JSON. It preflights the
model endpoint before spending anything, because the adapter (correctly) turns a
failed model call into reward `0.0`, which otherwise makes a broken run look like a
clean one. Details, all three variants and the honest limits:
[`examples/cheap_real/README.md`](../examples/cheap_real/README.md).

## 5. Where to next

| You want to… | Go to |
|---|---|
| Understand what cap-evolve optimizes and how | [`../README.md`](../README.md) · [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| See a real (cheap) LLM run end to end | [`../examples/cheap_real/`](../examples/cheap_real/) |
| Set up a real optimizer/runner (credentials, dashboard) | [`INSTALL.md`](INSTALL.md) |
| Optimize your own agent + benchmark | [`OPTIMIZE_YOUR_OWN.md`](OPTIMIZE_YOUR_OWN.md) |
| See real benchmark results | [`RESULTS.md`](RESULTS.md) |
| Something failed | [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) |
