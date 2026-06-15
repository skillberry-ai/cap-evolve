# Example: tau2-bench airline (real, watsonx `gpt-oss-120b`)

A real, end-to-end agent-capo example that optimizes the **airline policy** against
[tau2-bench](https://github.com/sierra-research/tau2-bench), with the agent and the
user simulator both running `openai/gpt-oss-120b` via IBM RITS / watsonx.

See **[RESULTS.md](RESULTS.md)** for measured outcomes (A/B Δ = +0.40 reward).

## Files
- `adapter.py` — the 4-method `CapabilityAdapter` (tasks / run_target / score / apply) +
  a fast `run_batch` over tau2's concurrent runner. Scores with tau2's reward and
  rich, gold-aware feedback.
- `tau2_runtime.py` — RITS routing for `gpt-oss-120b`, policy injection into tau2's
  airline domain, and the gpt-oss empty-turn retry. Redirects tau2's stdout to
  stderr so the skill JSON contract stays clean.
- `policy/policy.md` — the full (good) airline policy = the optimization *target*.
- `policy_degraded/policy.md` — seed with the Cancel-flight section removed.
- `mock_script.json` — deterministic restoration edit (stand-in optimizer for CI).
- `ab_compare.py` — head-to-head degraded-vs-restored scorer.
- `data/airline.jsonl`, `data/splits_small.json` — tasks + a curated split.

## Prerequisites
1. `.env` (repo root) with `RITS_API_KEY` (and `WATSONX_*`). The runtime loads it.
2. tau2-bench importable (`pip install -e ../tau2-bench` or it's already on PYTHONPATH).
3. `pip install ./core` (or `export AGENT_CAPO_CORE=$PWD/core`).

## Run the full skill pipeline
```bash
REPO=$PWD
export AGENT_CAPO_CORE="$REPO/core"
export ACAPO_TAU2_DATA="$REPO/examples/tau2_airline/data"
export ACAPO_TAU2_TASK_IDS="0,1,26,39,41,43,45,49"   # cancellation tasks
export TAU2_MAX_CONCURRENCY=20

# scaffold a project, wire the adapter:
mkdir -p run/.agentcapo/project/adapters && cd run
cp $REPO/examples/tau2_airline/adapter.py .agentcapo/project/adapters/
cp $REPO/examples/tau2_airline/tau2_runtime.py .agentcapo/project/adapters/
cp -R $REPO/examples/tau2_airline/policy_degraded seed_policy
cp $REPO/examples/tau2_airline/mock_script.json .
export PYTHONPATH="$AGENT_CAPO_CORE:$PWD/.agentcapo/project/adapters"
export ACAPO_MOCK_SCRIPT="$PWD/mock_script.json"

python3 -m agent_capo check .agentcapo/project                 # HARD GATE
python3 $REPO/skills/phases/baseline/scripts/run.py   --base .agentcapo --project .agentcapo/project --capability seed_policy --n-trials 2 --max-iterations 1 --run-ts demo
OPT="python3 $REPO/skills/optimizers/mock/scripts/run.py --workdir {workdir} --prompt {prompt}"
python3 $REPO/skills/algorithms/all-at-once/scripts/run.py --run-dir .agentcapo/run_demo --project .agentcapo/project --optimizer "$OPT" --max-iterations 1 --n-trials 2
python3 $REPO/skills/phases/finalize/scripts/run.py   --run-dir .agentcapo/run_demo --project .agentcapo/project --n-trials 2
python3 $REPO/skills/phases/report/scripts/run.py     --run-dir .agentcapo/run_demo
```

To use a **real optimizer** instead of the mock, swap the `--optimizer` command for
the `claude-code` optimizer skill (requires the `claude` CLI):
```
OPT="python3 $REPO/skills/optimizers/claude-code/scripts/run.py --workdir {workdir} --prompt {prompt}"
```
Claude will read the gold-aware diagnosis in `INSTRUCTIONS.md` and edit `policy.md`.

## Notes
- Use `num_trials ≥ 2` and ≥ 6–8 tasks per split: tau2 + gpt-oss is stochastic.
- The held-out test split is scored once and sealed; a second finalize errors.
