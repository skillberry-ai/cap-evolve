# Example: cheap_real — a REAL LLM run in minutes, for $0 or cents

The missing middle rung. `toy_calc` is free but calls no model; the τ²-bench airline
example calls a real model but [takes hours and ~$148](../../docs/RESULTS.md). This
one is a **real** run — real LLM, a real accept/reject decision, a real sealed test
split — that finishes in **minutes** and costs **$0** on a local model.

The task: normalize a human-written date (`"the 22nd of November, 1963"`) to ISO
(`1963-11-22`), scored by exact match. The seed prompt is a generic "you are a helpful
assistant", so a small model answers in prose and scores **0**; the fix is an output
contract, which is exactly the kind of edit an optimizer proposes.

## The three rungs

| Rung | Runner | Optimizer | Runtime | Cost |
|---|---|---|---|---|
| free | `ollama/llama3.2:3b` | `mock` | **~30 s** measured (30.4 / 33.9 / 34.2 s on three runs) | **$0** measured |
| hosted-runner | `claude-haiku-4-5` | `mock` | **98 s** measured | **$0.0115** measured |
| cheap-real | `ollama/llama3.2:3b` | `claude-code` (Haiku) | **5.4 min** measured | **$0.54** measured |
| full | tau2-bench airline | `claude-code` | hours | ~$148 |

All three measured rungs reached the same honest outcome — `baseline_val 0.0` →
`test_reward 1.0` on the sealed test split. The cheap rung's $0.54 is entirely the 3
proposals ($0.159 / $0.199 / $0.185 from the run's own `opt_cost_usd`); its 30 runner
calls were **metered at $0** because the runner is local — the runner's cost there is
*time* (29.5 s, 3 863 tokens), not zero across the board. The hosted-runner rung is the
mirror image: `mock` proposes for $0 and the 30 runner calls cost $0.0115 in total.

Derivation and provenance of every figure: [`../../docs/GETTING_STARTED.md`](../../docs/GETTING_STARTED.md).

## Run it

```bash
# Rung 1 — free. Needs Ollama (`ollama pull llama3.2:3b`, ~2 GB) and `pip install litellm`.
bash examples/cheap_real/run.sh

# Rung 2 — real agent proposes the edit; the runner stays free and local.
CHEAP_REAL_OPTIMIZER=claude-code CHEAP_REAL_OPT_MODEL=claude-haiku-4-5 \
  bash examples/cheap_real/run.sh

# No local model? Use a cheap hosted one as the runner instead. Needs that provider's
# credential in the environment (e.g. ANTHROPIC_API_KEY). MEASURED: 98 s, $0.0115.
CHEAP_REAL_MODEL=claude-haiku-4-5 bash examples/cheap_real/run.sh
```

`run.sh` is the **programmatic entry point** — every knob is an env var with a default
and **all of stdout is the run's summary JSON**: progress goes to stderr (#116) and the
script filters `cap-evolve run`'s output down to the last object, so a plain
`json.loads(stdout)` works even with `CAPEVOLVE_DASHBOARD=auto`, which makes the CLI
print a second object (#217). See its header for the full knob list
(`CHEAP_REAL_MODEL`, `CHEAP_REAL_API_BASE`, `CHEAP_REAL_OPTIMIZER`,
`CHEAP_REAL_OPT_MODEL`, `CHEAP_REAL_WORKDIR`, `CHEAP_REAL_MAX_USD`,
`CHEAP_REAL_PYTHON`).

It **preflights every variant** before spending anything, because the adapter turns a
failed model call into reward `0.0` — a broken run otherwise looks like an honest one.
Local: the endpoint answers *and* the model is actually pulled. Hosted: one real
1-token completion through the same wiring the adapter uses. `run.sh` also exports
`LITELLM_DROP_PARAMS=1`, because the bundled adapter forwards `seed=` and Anthropic
rejects it — without that every hosted rollout scored `0.0` behind a clean-looking run.
`API_BASE` is exported **only for an `ollama/` model**: `model_config.py` reads the
generic `API_BASE` before any provider special-casing, so setting it unconditionally
pointed a hosted model at localhost.

## Files

- `capevolve.yaml` — the preset. Only the keys that differ from
  [`templates/project/capevolve.yaml`](../../templates/project/capevolve.yaml) are set.
  Note `protected_paths` is **omitted, not `[]`** — and what omission buys is not just
  the default globs: `protect.py:168-170` resolves an omitted key to
  `[*_DEFAULT_GLOBS, *spec['dataset_source']]`. `tasks.jsonl` matches **none** of the
  default globs (those are `adapters`, `capevolve.yaml`, and `*gold*` suffixes) — the
  answer key is covered *because* `dataset_source` is folded in when the key is absent.
  Declare the key and that fold-in never happens.
- `tasks.jsonl` — 20 dates. **20 is a floor, not a preference:** at the default
  0.5/0.25/0.25 ratios that is train 10 / val 5 / test 5, and val 5 is the smallest
  split that clears *both* of #113's bars — `MIN_VAL_TASKS = 2` (below which
  `gate.decide` refuses outright) and `LOW_CONFIDENCE_VAL_TASKS = 5` (below which
  every decision is stamped LOW CONFIDENCE). Shrinking the task count to save money
  would buy a cheaper run by giving up the honest gate.
- `capability/prompt.txt` — the seed system prompt that gets optimized.
- `mock_script.json` — the deterministic edit the `mock` optimizer applies, so rung 1
  is reproducible and zero-API.
- `optimizer_INSTRUCTIONS.md` — the per-iteration prompt for the real-agent rung.
- **No adapter.** `run.sh` copies
  [`templates/adapters/jsonl_litellm/adapter.py`](../../templates/adapters/jsonl_litellm/adapter.py)
  and `model_config.py` verbatim; a JSONL dataset scored by exact match is precisely
  what that bundled template is for.

## Why this is not a benchmark-zoo entry

The benchmark zoo (`docs/BENCHMARK_ZOO.md`, landing in #233) would be the natural home
— declarative manifest, one code file, a `verify` command. It cannot host this one:
`verify`'s step 5 runs every val task **twice** and fails the benchmark if any rollout
fingerprint differs (`NON-DETERMINISTIC: … cannot produce a reproducible number`).
That guard is correct and worth keeping, but a real LLM cannot satisfy it even at
`temperature=0` and a fixed seed. This example exists to call a real model, so it is
a standalone example and the zoo's exactness guard stays as strict as it is today.

That is the answer for *this* PR, not the durable one: `cheap_real` is the first of a
class, and every future live-model benchmark hits the same wall. The open shape is an
explicit `determinism: exact | statistical | none` grade in the manifest, where
`statistical` substitutes a variance check for the byte-exact fingerprint and the zoo
*reports* the grade rather than implying everything in it is exact. Deferred to #233 or
a follow-up — not settled.

## Honest limits

- The gate reports `SE=0 → STRICT fallback` at `num_trials: 1`, because a single
  deterministic-ish trial per task gives the paired gate no variance to work with.
  That is the documented behavior, not a defect of the preset — but it means the
  accept decision here is "Δ > 0", not a significance test. Raise `num_trials` to get
  a real bar, at a proportional increase in runner calls.
- **This run never exercises a rejection on merit.** Val saturates at 1.0 on iteration
  1, so the two candidates that follow are rejected against a ceiling — there was
  nothing left to improve, not a plausible candidate found wanting. The gate *ran* and
  made real decisions; it was never asked a hard question. A task the model still gets
  partly wrong *with* the output contract would land baseline ~0.0 → best ~0.6 at the
  same cost and give the gate something to decide. Do not read this example as a
  demonstration that the significance machinery works — read `examples/skillsbench`
  (`num_trials: 3`) for that.
- `test_pass_k` reports `{"2": 0.0}` even though `num_trials: 1`, so pass^2 is not
  measurable here. That is pre-existing #112 (pass^k above `num_trials` should read
  N/A), not a property of this preset — ignore the `"2"` entry.
- A 3B local model is a weak reader. The point is to see the machinery work end to
  end on a real model, not to produce a publishable number.
