# cap-evolve project — tau2-bench airline (direct arm)

Filled by the `intake` skill. Records the decisions behind this run so anyone
(human or agent) can understand and reproduce it.

## What we're optimizing
- Capability: `tools` — the airline agent's TOOL SURFACE only (the policy / system prompt is NOT edited)
- Artifact: `seed_capability/tools/tools.py` (byte-for-byte copy of tau2's airline `tools.py`
  + `REMOVE_TOOLS: set[str] = set()`); `seed_capability/reference/data_model.py` (protected)
- Allowed edits: [edit] — tool bodies, new `@is_tool` methods, names in `REMOVE_TOOLS`
- Delivery arm: **direct** (no intervention) — the runner execs the candidate's tools.py in its own process

## How we run the target (the RUNNER)
- Benchmark: tau2-bench, cloned from https://github.com/sierra-research/tau2-bench `main` into `vendor/tau2-bench`
- **SHA in use: 4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699 (= TAU2_REFERENCE_SHA)** — recorded in `vendor/tau2-bench.COMMIT`; clone unmodified
- Install note: `uv pip install -e core -e vendor/tau2-bench` leaves `import tau2` broken — upstream's
  base import chain (`data_model/simulation.py` → `voice/audio_native/openai/provider.py`) imports
  `websockets`, which upstream declares only in its `voice` extra. Fixed by installing
  `websockets>=13.0` (tau2's own constraint) into the venv; the clone is untouched.
- Agent under test: tau2's stock `llm_agent`, model `openai/aws/claude-sonnet-5`
- User simulator: `user_simulator`, model `openai/aws/claude-sonnet-5`
- Models resolved from repo-root `.env` (`TAU2_AGENT_MODEL`, `TAU2_USER_MODEL`; nothing set in the shell)
- Gateway: `OPENAI_BASE_URL` from `.env`; `llm_args = {"api_base": <OPENAI_BASE_URL>, "temperature": 0.0}` (no key in llm_args)
- How `run_target` invokes it: `adapters/adapter.py` → `tau2.runner.run_tasks(TextRunConfig(domain="airline_candidate", ...), tasks, save_path=<run_dir>/native_sims/<tag>/results_<stamp>_<pid>.json, console_display=False)`, `workers=0`, `max_concurrency=125`
- Tailoring (outside the clone): `adapters/tau2_tailoring.py`, `install("direct")`:
  - T1 registers domain + tasks `airline_candidate` (env factory execs the current candidate's tools.py, fresh FlightDB per construction)
  - T2 wraps `EnvironmentEvaluator.calculate_reward` so GOLD is built with tau2's pristine `airline` env
- Seams: all LOCATEd at the reference SHA; see "Seam log" below.

## How we score
- Metric: tau2's task reward `reward_info.reward` in [0,1] (airline reward_basis = DB + COMMUNICATE)
- Feedback signal: argument-level, gold-safe text per failing check (action/arg key + the agent's own value, communicate misses)

## Data
- Source: `adapter` (all 50 airline `base` tasks)
- Splits (no-holdout, train = val = test; test number is a fit metric):
  `split_ids_smoke.json` ["9"], `split_ids_budget.json` [8,10,20,23,35,42,44], `split_ids.json` all 50

## Optimizer + algorithm
- Optimizer (proposer): claude-code, model claude-opus-4-8 (smoke spec: mock)
- Algorithm: hill-climb (--focus all), deterministic orchestration, memory md-files
- Budget (capevolve.yaml): 2 iterations, num_trials 5, optimizer_usd_per_iter 40, optimizer_max_turns 400, max_usd 400, max_optimizer_usd 400, stall 3; gate paired k_se 0.2
- Smoke (capevolve.smoke.yaml): 1 iteration, num_trials 1, optimizer mock

## Inputs status
- NEEDED inputs resolved: capability (seed_capability), dataset (adapter), scorer (tau2 reward_info), runner (vendor/tau2-bench), gateway credentials (.env)
- RECOMMENDED defaults: split_seed 0 (unused, explicit split files); trajectories() returns the last native_sims dir
- Cost note: cost_usd = agent_cost + user_cost as priced by litellm; a model litellm cannot price reports 0 (= NOT MEASURED)

## Seam log
- S1–S10 LOCATEd by grep at 4ce7c039…: every seam matched its LAST-KNOWN name and signature;
  no replacements. (`evaluator_env.py` has a second PREDICTED/GOLD pair in
  `FullDuplexEnvironmentEvaluator.calculate_reward`; full-duplex only, not used in text mode.)

## Runs
- Gateway probe (2026-10-12): `openai/aws/claude-sonnet-5` → `'OK.'` (agent = user model; one probe)
- Smoke `run_20261012_143358` (capevolve.smoke.yaml, task 9, mock optimizer): baseline 1.0,
  error null, db_match true; finalize test 1.0 (no-holdout fit metric, splits_warning logged).
- COST NOT MEASURED: litellm has no price for `aws/claude-sonnet-5` (tau2 logs "This model
  isn't mapped yet"), so agent_cost/user_cost — and therefore runner cost_usd — are 0.
  `max_usd` binds only on optimizer spend; the runner side is unmetered.
