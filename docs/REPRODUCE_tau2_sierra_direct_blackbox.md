# Reproducing the τ²-bench airline runs: direct and blackbox

This reproduces the two runs of [`examples/tau2_sierra_airline`](../examples/tau2_sierra_airline), one
per delivery:

- **direct**: the runner loads each candidate's tool code into its own process;
- **blackbox**: each candidate is deployed to the Skillberry Store, and the Skillberry Proxy-Agent
  injects it into the agent's LLM calls (see the [Blackbox tab](https://skillberry-ai.github.io/cap-evolve/blackbox.html)).

Both run the same optimization against vanilla τ²-bench, which is never edited, on the same tasks,
trials, models and budget. Only the delivery differs. The goal is that the two climb the same way.

## Results of the recorded runs

| | direct | blackbox |
|---|---|---|
| Run | `run_20261013_094928` | `run_20261013_121303` |
| Baseline val (seed) | 0.286 ± 0.158 | 0.286 ± 0.127 |
| Val after iteration 1, 2, 3 | 0.571, 0.800, 0.914 | 0.514, 0.600, 0.771 |
| Best candidate | `cand_0003` | `cand_0003` |
| Sealed test (champion) | **0.943** ± 0.067 | **0.771** ± 0.107 |
| Sealed test (seed, same session) | 0.343 | 0.371 |
| Test gain over the seed | +0.600 | +0.400 |
| pass^2 on test | 0.900 | 0.600 |
| Candidates accepted | 3 of 3 | 3 of 3 |
| Optimizer spend | $6.07, 9.2M tokens | $8.95, 16.6M tokens |
| Wall time (runner / optimizer) | 69 min / 24 min | 101 min / 40 min |

Metric: the mean τ²-bench task reward in `[0, 1]`, with its standard error over the 7 tasks.

**This is a no-holdout run** (train = val = test, the same 7 tasks), so the "test" number is a **fit
metric**, not a held-out result. The run records say so (`train_equals_val`). The two deliveries are
compared on the same footing, which is what these runs are for.

The two runs agree on the shape: both accept all three candidates, rise at every iteration, and pick
`cand_0003`.

## Pinned versions

| | |
|---|---|
| τ²-bench | `sierra-research/tau2-bench` at `4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699` (`TAU2_REFERENCE_SHA` in each `setup.sh`, direct and blackbox) |
| Domain | airline |
| cap-evolve | this repository, `examples/tau2_sierra_airline/{direct,blackbox}` |

## Models

| Role | Model | Notes |
|---|---|---|
| Agent under test | `aws/claude-haiku-4-5` | `target_model` in the spec. Direct calls it through the gateway. Blackbox calls the sentinel `ibm/skillberry-local`, and the Proxy-Agent calls `aws/claude-haiku-4-5`. Temperature 0. |
| User simulator | `aws/claude-sonnet-5` | Set with `TAU2_USER_MODEL`. Calls the gateway directly in both runs, never the Proxy-Agent. Temperature 0. |
| Optimizer | `claude-opus-5-5` | Driven by Claude Code (`optimizer_skill: claude-code`). |

## The task split

Both runs use `split_ids_budget.json`, the same 7 τ²-bench airline tasks for train, val and test:

```json
{
  "train": ["8", "10", "20", "23", "35", "42", "44"],
  "val":   ["8", "10", "20", "23", "35", "42", "44"],
  "test":  ["8", "10", "20", "23", "35", "42", "44"]
}
```

Each task is run 5 times per evaluation (`num_trials: 5`). A full evaluation is 7 × 5 = 35 rollouts.

## The run specs

The two specs are the committed
[`direct/capevolve.yaml`](../examples/tau2_sierra_airline/direct/capevolve.yaml) and
[`blackbox/capevolve.yaml`](../examples/tau2_sierra_airline/blackbox/capevolve.yaml). They are
identical except for the delivery keys and the protected paths.

```yaml
# --- delivery (blackbox only) ---------------------------------------------------
intervention: blackbox                   # direct: omitted (the default)
skill_name: my_skill                     # the one skill the Proxy-Agent serves

# --- what to optimize -----------------------------------------------------------
capabilities: [tools]                    # the agent's tool surface only, not the policy
capability_path: seed_capability
actions: [edit]
capability_sources: [seed_capability/reference/data_model.py]
protected_paths: ["reference/*"]         # blackbox: ["primitive_tools/*", "my_skill/SKILL.md", "reference/*"]

# --- who proposes edits ---------------------------------------------------------
optimizer_skill: claude-code
optimizer_model: claude-opus-5-5
optimizer_max_turns: 400
optimizer_usd_per_iter: 50
optimizer_instructions_file: optimizer/INSTRUCTIONS.md
runner_repo_path: ../../vendor/tau2-bench
target_model: aws/claude-haiku-4-5

# --- how to iterate -------------------------------------------------------------
algorithm_skill: hill-climb
algorithm_focus: all
orchestration_mode: deterministic
memory_skill: md-files

# --- data and splits ------------------------------------------------------------
dataset_source: adapter
split_seed: 0
split_ids_file: split_ids_budget.json    # train = val = test, 7 tasks
num_trials: 5

# --- gate and budget ------------------------------------------------------------
gate_mode: paired                        # per-task paired standard error
gate_k_se: 0.2
max_iterations: 3
stall: 3
max_usd: 400
max_optimizer_usd: 400
store: git
```

## Environment

A repo-root `.env`:

```
OPENAI_BASE_URL=<your gateway>
OPENAI_API_KEY=<your key>
TAU2_AGENT_MODEL=aws/claude-haiku-4-5    # the agent model; on blackbox, the model the Proxy-Agent calls
TAU2_USER_MODEL=aws/claude-sonnet-5      # the user simulator
```

The optimizer needs a logged-in Claude Code session, or `ANTHROPIC_API_KEY`.

With blackbox delivery the adapter restarts the Proxy-Agent for each candidate with
`SPA_MODEL_NAME` set to `TAU2_AGENT_MODEL`, so the Proxy-Agent always answers with the agent model.
`SPA_MODEL_NAME` is only the fallback when `TAU2_AGENT_MODEL` is unset.

## Reproduce

Each run is two commands from the repo root. `setup.sh` clones τ²-bench at the pinned commit and
installs everything. The blackbox `setup.sh` also provisions the Skillberry Store and Proxy-Agent.

```bash
# direct
bash examples/tau2_sierra_airline/direct/setup.sh
bash examples/tau2_sierra_airline/direct/run.sh

# blackbox
bash examples/tau2_sierra_airline/blackbox/setup.sh
bash examples/tau2_sierra_airline/blackbox/run.sh
```

Both `run.sh` scripts take `--smoke` for a one-task, one-trial check with a mock optimizer and no spend
(`capevolve.smoke.yaml`, `split_ids_smoke.json`).

Runs land in `.capevolve/` (direct) and `.capevolve-blackbox/` (blackbox). Open them with
`cap-evolve dashboard --base .capevolve` or `--base .capevolve-blackbox`. A run's
**Config** tab shows its spec, and the blackbox run shows `intervention: blackbox` under Delivery.

## What to compare

- `final.json`: the champion's sealed test score, the seed's score in the same session, and `test_delta`.
- `events.jsonl`: the val score of each candidate and the gate decision behind it.
- `candidates/cand_0003/`: the champion's tool code.
- `state.json`: the optimizer's spend, tokens and wall time.

The run is stochastic at the agent level even at temperature 0, so a reproduction lands close to
these numbers, not on them. With 7 tasks a difference of about 0.2 is within the noise.
