# Reproducing the tau2-airline run (exact commands, inputs, and intake answers)

This is the full recipe for the headline run: optimize the airline **policy + tools
together** (composite) with the **claude-code optimizer @ claude-opus-4-6**, the
agent *and* user simulator both **gpt-oss-120b** (watsonx/RITS), over **all 50**
airline tasks, **10 iterations**, **num_trials 4**, tau **concurrency 7**, with a
**git** iteration store and optimizer **memory**.

It documents (1) the inputs the intake phase needs, (2) the answers the agent
(Claude Code, i.e. me) gave to the intake questions, and (3) the exact commands.

---

## 1. Prerequisites

- `tau2-bench` importable (this workspace has it at `../tau2-bench`).
- Repo `.env` (one level above `cap-evolve/`) with the RITS/watsonx creds — read
  automatically by `tau2_runtime.load_env()`:
  ```
  RITS_API_KEY=…        WATSONX_APIKEY=…
  RITS_API_URL=…        WATSONX_PROJECT_ID=…
                        WATSONX_URL=…
  ```
- `claude` CLI on PATH (the optimizer); `pip install ./core` (or `CAPEVOLVE_CORE`).

## 2. The intake phase — questions and the answers given (by Claude Code)

`intake` collects the inputs in `skills/phases/intake/inputs/INPUTS.md`. For this
run the answers were:

| Intake question | Answer (this run) |
|---|---|
| **What capability to optimize?** | `composite` — the airline **policy** (a `system-prompt` member) **and** the **tools** (`tools.py` docstrings + new composite tools). Artifact: `examples/tau2_airline/seed_caps/` (`policy/policy.md` + `tools/tools.py`). |
| **Where is the target agent (RUNNER) + how to run it?** | tau2-bench airline; `adapter.run_batch` runs tasks through tau2's concurrent runner with agent+user = `openai/gpt-oss-120b` via RITS (`tau2_runtime.run_airline_batch`). |
| **How to score?** | tau2's own reward ∈ [0,1] (`adapter.score`), with gold-aware feedback (expected actions/info missed) as the learning signal. |
| **Dataset + splits?** | All 50 airline tasks. `split_ids_file: split_ids.json` with train = val = test = all 50 (a deliberate **no-holdout fit** on the full benchmark — the run logs a leakage warning and the test number is reported as a fit metric). |
| **num_trials?** | 4 (gpt-oss is stochastic; 4 trials → mean + stderr + pass^k/pass@k). |
| **Optimizer + model?** | `claude-code` @ `claude-opus-4-6` (substitute a current Claude Opus model id your `claude` CLI accepts). |
| **Algorithm?** | `all-at-once` (propose against the whole train set each iteration). |
| **Budget?** | `max_iterations: 10`, `stall: 0`. |
| **Gate?** | `significant` (Δ > 1·SE on val). |
| **Iteration store?** | `git` (default) — every iteration is committed so the whole process is browsable. |
| **tau concurrency?** | `TAU2_MAX_CONCURRENCY=7`. |

These answers are encoded in `examples/tau2_airline/run_full/cap-evolve.composite.yaml`.

## 3. Input files (what the user/agent provides)

```
examples/tau2_airline/
├── adapter.py                 # the 4-method CapabilityAdapter (tasks/run_target/score/apply) + run_batch
├── tau2_runtime.py            # RITS routing + inject(policy + tools) + gpt-oss empty-turn retry
├── seed_caps/
│   ├── policy/policy.md       # the airline policy  (system-prompt member)  ← optimized
│   └── tools/tools.py         # the 14 airline tool docstrings as editable fns ← optimized
├── data/airline.jsonl         # the 50 tasks
└── run_full/
    ├── cap-evolve.composite.yaml   # the run spec (answers above)
    ├── split_ids_all50.json   # train=val=test=all 50 ids
    └── reuse_baseline.sh      # the launcher (reuses the cached baseline)
```

## 4. Exact commands

### 4a. Baseline (run once; reused afterwards)
```bash
REPO=$PWD                       # cap-evolve repo root
export CAPEVOLVE_CORE=$REPO/core PYTHONPATH=$REPO/core CAPEVOLVE_SKILLS_DIR=$REPO/skills
export CAPEVOLVE_TAU2_DATA=$REPO/examples/tau2_airline/data TAU2_MAX_CONCURRENCY=7

R=/tmp/tau2_full; mkdir -p $R/.capevolve/project/adapters
cp $REPO/examples/tau2_airline/{adapter.py,tau2_runtime.py} $R/.capevolve/project/adapters/
cp -R $REPO/examples/tau2_airline/seed_caps $R/seed_composite
cp $REPO/examples/tau2_airline/run_full/split_ids_all50.json $R/split_ids.json
cp $REPO/examples/tau2_airline/run_full/cap-evolve.composite.yaml $R/.capevolve/project/capevolve.yaml

python3 -m cap_evolve.cli run --spec $R/.capevolve/project/capevolve.yaml \
    --project $R/.capevolve/project --run-ts full
```
The baseline over all 50 tasks × 4 trials was **val = 0.46 ± 0.058** (gpt-oss-120b
on the seed policy + default tool docs). It was cached to `/tmp/tau2_baseline_cache`.

### 4b. The optimization (reusing the baseline to save the ~40-min baseline pass)
```bash
REPO=$PWD BASELINE=/tmp/tau2_baseline_cache R=/tmp/tau2_comp \
    examples/tau2_airline/run_full/reuse_baseline.sh
```
This snapshots the composite seed, reuses the cached baseline (val 0.46), then runs
`all-at-once` for 10 iterations (claude-opus-4-6 proposes coordinated edits to the
policy + tool docstrings + may add composite tools), evaluating each candidate on
all 50×4, gating on val, committing every iteration to git, and writing
`report.md` + `dashboard.html` + the git history + `MEMORY.md`/`rejected.jsonl`.

### 4c. Inspect the process
```bash
RD=/tmp/tau2_comp/.capevolve/run_comp
git -C $RD log --oneline          # one commit per iteration (the whole process)
cat $RD/report.md                 # baseline → best-val → test
open $RD/dashboard.html           # KPIs, per-task heatmap, score-over-iterations, leaderboard
cat $RD/rejected.jsonl            # approaches the gate rejected (optimizer memory)
```

## 5. What "all 50 tasks in train/val/test" means here
The user asked to use all 50 tasks for train, val, AND test. That is a **no-holdout
fit** on the full airline benchmark (train = val = test = the 50 tasks). cap-evolve
allows it but logs a `splits_warning` and the report flags the test number as a fit
metric (not held-out). For a held-out result, set `split_ids_file: ""` and use the
ratio split (`split_train/val/test`) instead.

## 6. Notes on cost
all-at-once evaluates the val split (50 × 4 = 200 tau2 conversations) each
iteration, so the run is ~200 (baseline) + 10×200 + 200 (test) ≈ 2,400 multi-turn
conversations + 10 claude-opus-4-6 calls — several hours at concurrency 7. Reduce
`max_iterations`/`num_trials`, or use a ratio split, for a faster pass.
