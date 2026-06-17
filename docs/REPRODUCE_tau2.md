# Reproducing a tau2-airline run (intake answers + exact commands)

A worked walkthrough of running the **v2 pipeline** on tau2-bench airline,
fully autonomously: `cap-evolve check → baseline → <algorithm> → finalize →
report → dashboard`, with the agent *and* user simulator both
`watsonx/openai/gpt-oss-120b` via IBM RITS. Two real runs (configs + dashboards)
live in [`../examples/tau2_airline/run_full/README.md`](../examples/tau2_airline/run_full/README.md);
this doc shows the inputs the **intake** phase collects and the answers behind them.

---

## 1. Prerequisites
- `tau2-bench` importable (this workspace has it at `../tau2-bench`).
- Repo-root `.env` (one level above `cap-evolve/`) with the RITS creds — read
  automatically by `tau2_runtime.load_env()` (quoted values are fine):
  `RITS_API_KEY`, `RITS_API_URL` (+ `WATSONX_*` if you route through watsonx;
  `BOBSHELL_API_KEY` if the optimizer is `ibm-bob`).
- `pip install ./core` (or set `CAPEVOLVE_CORE`); the optimizer CLI on PATH
  (`claude` for `claude-code`, `bob` for `ibm-bob`; `mock` needs nothing).

## 2. The intake phase — questions and example answers
`intake` collects the inputs in `skills/phases/intake/inputs/INPUTS.md`:

| Intake question | Example answer |
|---|---|
| **What capability to optimize?** | `[system-prompt, tools]` — the airline **policy** (`policy/policy.md`) **and** the **tools** (`tools/tools.py` docstrings + new composite tools). Artifact: `examples/tau2_airline/seed_caps/`. |
| **Target agent (RUNNER) + how to run it?** | tau2-bench airline; `adapter.run_batch` runs tasks through tau2's concurrent runner with agent+user = `openai/gpt-oss-120b` via RITS (`tau2_runtime`). |
| **How to score?** | tau2's own reward ∈ [0,1] (`adapter.score`) with gold-aware feedback (expected actions/info missed) as the learning signal. |
| **Dataset + splits?** | The 50 airline tasks. Prefer an **honest holdout** via `split_ids_file` (e.g. 30/10/10); or all 50 as train=val=test for a **no-holdout fit** (the engine logs a `splits_warning` and the report flags the test number as a fit metric). |
| **num_trials?** | 2–5 (gpt-oss is stochastic; trials give mean + stderr + pass^k/pass@k). |
| **Optimizer + model?** | Any name in `optimizers/registry.yaml` (`run-optimizer --list`): e.g. `claude-code` (a Claude model id) or `ibm-bob`. |
| **Algorithm?** | `hill-climb` (baseline), `gepa` (sample-efficient flagship), or `skillopt`. |
| **Budget?** | `max_iterations`, `stall`; for `gepa` also `--max-metric-calls` via `algorithm_args`. |
| **Gate?** | omit `gate_mode` → the engine auto-selects the **paired** gate (candidate & current share val tasks); `gate_k_se` tunes strictness. |
| **Iteration store?** | `git` (default) — every iteration is committed so the whole process is browsable. |
| **tau concurrency?** | `TAU2_MAX_CONCURRENCY=7`. |

## 3. Exact commands
```bash
REPO=$PWD                                    # cap-evolve repo root
R=/tmp/tau2_run; PROJECT=$R/.capevolve/project
export CAPEVOLVE_CORE=$REPO/core PYTHONPATH=$REPO/core:$PROJECT/adapters
export CAPEVOLVE_SKILLS_DIR=$REPO/skills CAPEVOLVE_TAU2_DATA=$REPO/examples/tau2_airline/data
export TAU2_MAX_CONCURRENCY=7 TAU2_LLM_TIMEOUT=240 TAU2_INFRA_RETRIES=2

mkdir -p $PROJECT/adapters
cp $REPO/examples/tau2_airline/{adapter.py,tau2_runtime.py} $PROJECT/adapters/
cp -R $REPO/examples/tau2_airline/seed_caps $R/seed_caps
# write $PROJECT/capevolve.yaml (capabilities/optimizer/algorithm/splits — see §2)
# and, for a holdout, $R/split_ids.json referenced by split_ids_file

python3 -m cap_evolve.cli run --spec $PROJECT/capevolve.yaml --project $PROJECT --run-ts run
```

## 4. Inspect the process
```bash
RD=$R/.capevolve/run_run
git -C $RD log --oneline      # one commit per iteration (the whole process)
cat $RD/report.md             # baseline → best-val → sealed test (scored once)
open $RD/dashboard.html       # KPIs, cumulative-best stair, per-task heatmap, lineage, cost
cat $RD/rejected.jsonl        # what the honest gate rejected (optimizer memory)
```

## 5. A note on honest results
On a small held-out val, the **paired gate correctly refuses gains it can't
distinguish from noise** — so a run may honestly finalize at the seed. That is the
system working, not failing. To give a real gain the statistical power to clear the
gate, use a larger val / more trials (or the no-holdout fit, labeled as such). See
the two runs in `examples/tau2_airline/run_full/` for honest worked outcomes.
