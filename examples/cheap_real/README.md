# Example: cheap_real — a REAL LLM run in minutes, for $0 or cents

The missing middle rung. `toy_calc` is free but calls no model; the τ²-bench airline
example calls a real model but [takes hours and ~$148](../../docs/RESULTS.md). This
one is a **real** run — real LLM, real paired gate, real sealed test split — that
finishes in **minutes** and costs **$0** on a local model.

The task: normalize a human-written date (`"the 22nd of November, 1963"`) to ISO
(`1963-11-22`), scored by exact match. The seed prompt is a generic "you are a helpful
assistant", so a small model answers in prose and scores **0**; the fix is an output
contract, which is exactly the kind of edit an optimizer proposes.

## The three rungs

| Rung | Runner | Optimizer | Runtime | Cost |
|---|---|---|---|---|
| free | `ollama/llama3.2:3b` | `mock` | **36 s** measured | **$0** measured |
| cheap-real | `ollama/llama3.2:3b` | `claude-code` (Haiku) | **5.4 min** measured | **$0.54** measured |
| full | tau2-bench airline | `claude-code` | hours | ~$148 |

Both measured rungs reached the same honest outcome — `baseline_val 0.0` →
`test_reward 1.0` on the sealed test split. The cheap rung's $0.54 is entirely the 3
proposals ($0.159 / $0.199 / $0.185 from the run's own `opt_cost_usd`); all 30 runner
calls were free because the runner is local.

Derivation and provenance of every figure: [`../../docs/GETTING_STARTED.md`](../../docs/GETTING_STARTED.md).

## Run it

```bash
# Rung 1 — free. Needs Ollama (`ollama pull llama3.2:3b`, ~2 GB) and `pip install litellm`.
bash examples/cheap_real/run.sh

# Rung 2 — real agent proposes the edit; the runner stays free and local.
CHEAP_REAL_OPTIMIZER=claude-code CHEAP_REAL_OPT_MODEL=claude-haiku-4-5 \
  bash examples/cheap_real/run.sh

# No local model? Use a cheap hosted one as the runner instead.
CHEAP_REAL_MODEL=claude-haiku-4-5 bash examples/cheap_real/run.sh
```

`run.sh` is the **programmatic entry point** — every knob is an env var with a default
and the last object on stdout is the run's summary JSON. See its header for the full
list (`CHEAP_REAL_MODEL`, `CHEAP_REAL_API_BASE`, `CHEAP_REAL_OPTIMIZER`,
`CHEAP_REAL_OPT_MODEL`, `CHEAP_REAL_WORKDIR`, `CHEAP_REAL_MAX_USD`,
`CHEAP_REAL_PYTHON`).

## Files

- `capevolve.yaml` — the preset. Only the keys that differ from
  [`templates/project/capevolve.yaml`](../../templates/project/capevolve.yaml) are set.
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
a standalone example and the zoo keeps its determinism guarantee intact.

## Honest limits

- The gate reports `SE=0 → STRICT fallback` at `num_trials: 1`, because a single
  deterministic-ish trial per task gives the paired gate no variance to work with.
  That is the documented behavior, not a defect of the preset — but it means the
  accept decision here is "Δ > 0", not a significance test. Raise `num_trials` to get
  a real bar, at a proportional increase in runner calls.
- A 3B local model is a weak reader. The point is to see the machinery work end to
  end on a real model, not to produce a publishable number.
