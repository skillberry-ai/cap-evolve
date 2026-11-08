# cap-evolve project — tau2-bench airline (blackbox arm)

Filled by the `intake` skill. Records the decisions behind this run so anyone
(human or agent) can understand and reproduce it.

## What we're optimizing
- Capability: tools — the airline agent's TOOL SURFACE only (the policy is not edited)
- Artifact: `seed_capability/` — `my_skill/scripts/<tool>.py` (14 wrappers, the edit surface),
  `primitive_tools/functions.py` (14 frozen `env_<tool>` primitives), `reference/data_model.py`
- Allowed edits: [edit]; protected_paths: primitive_tools/*, my_skill/SKILL.md, reference/*
- Delivery arm: blackbox (`intervention: blackbox`, `skill_name: my_skill`)

## How we run the target (the RUNNER)
- Benchmark: tau2-bench, https://github.com/sierra-research/tau2-bench branch main
- SHA in use: 4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699 (= TAU2_REFERENCE_SHA; tau2 1.0.1)
  recorded in vendor/tau2-bench.COMMIT. Clone is unmodified.
- Install note: at this SHA `tau2/__init__` imports `websockets` (via data_model/simulation.py →
  voice/audio_native/openai/provider.py) but upstream declares it only in the `[voice]` extra.
  Installed `websockets>=13.0` into the venv in addition to `-e core -e vendor/tau2-bench`.
- Agent under test: tau2 stock `llm_agent` via our factory `llm_agent_skillberry`, model
  sentinel `ibm/skillberry-local` → Skillberry Proxy-Agent → `openai/aws/claude-sonnet-5`
- User simulator: `user_simulator`, `openai/aws/claude-sonnet-5` on the gateway
- Models resolved from the repo `.env` (TAU2_AGENT_MODEL, TAU2_USER_MODEL, SPA_MODEL_NAME):
  agent aws/claude-sonnet-5, user aws/claude-sonnet-5
- Domain: `airline_skillberry`, registered by adapters/tau2_tailoring.py (outside-in tailoring)
- How `run_target` invokes it: `run_trials([task], ctx, n_trials=1, base_seed=seed)` →
  `tau2.runner.run_tasks(TextRunConfig(...), tasks, save_path=<run_dir>/native_sims/<tag>/results_<stamp>_<pid>.json)`

## How we score
- Metric: tau2 reward_info.reward (reward in [0,1]; airline reward_basis DB + COMMUNICATE)
- Feedback signal: argument-level, gold-safe localisation of failing action/communicate checks

## Data
- Source: "adapter" (50 airline tasks, tau2 get_tasks("base"))
- Split: no-holdout split files (train = val = test) — the test number is a FIT metric:
  split_ids_smoke.json ["9"], split_ids_budget.json [8,10,20,23,35,42,44], split_ids.json (all 50)

## Optimizer + algorithm
- Optimizer (proposer): claude-code, claude-opus-4-8 (smoke: mock)
- Algorithm: hill-climb (--focus all), gate paired k_se 0.2
- Budget: max_iterations 2 (smoke 1) / num_trials 5 (smoke 1) / max_usd 400 / max_optimizer_usd 400
  / stall 3 / optimizer_max_turns 400 / optimizer_usd_per_iter 40
- Cost note: the proxy reports no token usage, so the AGENT cost is unmeasured; only the user
  simulator's gateway cost counts. 0 in the cost panel = not measured.

## Inputs status
- NEEDED inputs resolved: tasks (adapter), scorer (tau2 reward), trajectories (cap-evolve
  per-rollout JSON; native tau2 results under <run_dir>/native_sims/), gateway credentials (.env)
- RECOMMENDED inputs defaulted: none beyond the prompt's values
