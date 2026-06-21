# cap-evolve with skillberry-benchmarks / tau2-bench

Use cap-evolve to optimize the tau2-bench **airline agent** (its `policy.md` system
prompt and `tools.py`) running through the
[skillberry-benchmarks exgentic wrapper](https://github.com/skillberry-ai/skillberry-benchmarks/tree/main/exgentic).

The benchmark runs inside the `skillberry-benchmarks/exgentic/` harness. cap-evolve
proposes edits every iteration and accepts only those that genuinely improve the
val score — every iteration is versioned in git and the final result is an
honest, sealed-test number.

---

## Prerequisites

| What | Where |
|---|---|
| `skillberry-benchmarks` cloned and exgentic set up | `skillberry-benchmarks/exgentic/` — run `make install && make setup-exgentic` once |
| A model endpoint (OpenAI-compatible) | Any endpoint LiteLLM can route to; see credential section below |
| `cap-evolve` core installed | `pip install ./core` from the cap-evolve repo root |
| A coding agent CLI (optimizer) | `claude`, `codex`, `gemini`, or any supported host |

> **First-time exgentic setup:** from `skillberry-benchmarks/exgentic/`, run:
> ```bash
> make install       # clones exgentic repo, creates .venv, installs package
> make setup-exgentic  # runs `exgentic setup --benchmark tau2 --agent smolagents_tool`
> ```
> After that the CLI is at `skillberry-benchmarks/exgentic/.venv/bin/exgentic`.

---

## Path A — let Claude do it for you (recommended)

This is the fastest path. You don't write the adapter yourself — you describe
the setup to Claude and it handles intake, adapter implementation, the check
gate, and the full optimize → finalize → report loop.

Open Claude Code at the cap-evolve repo root and paste this prompt (fill in
the `<PLACEHOLDERS>`):

```text
Follow RUN.md to run a cap-evolve optimization. Here is everything intake needs:

# 1. CAPABILITY TO OPTIMIZE
- type: system-prompt, tools
- local path: <PATH_TO_SKILLBERRY_BENCHMARKS>/exgentic/exgentic/src/exgentic/benchmarks/tau2/installation/tau2-bench/data/tau2/domains/airline/policy.md
- and also:   <PATH_TO_SKILLBERRY_BENCHMARKS>/exgentic/exgentic/src/exgentic/benchmarks/tau2/installation/tau2-bench/src/tau2/domains/airline/tools.py

# 2. BENCHMARK
- harness: skillberry-benchmarks exgentic wrapper
- exgentic CLI: <PATH_TO_SKILLBERRY_BENCHMARKS>/exgentic/.venv/bin/exgentic
- exgentic working dir: <PATH_TO_SKILLBERRY_BENCHMARKS>/exgentic/exgentic
- benchmark: tau2, subset: airline, agent: smolagents_tool
- tasks: task id(s) to evaluate, e.g. "9"  (or a comma-separated list for multi-task)
- splits: all-in-each (same task id(s) in train, val, and test) — fit metric

# 3. RUNNER + MODEL + CREDENTIALS
- model string: litellm_proxy/<YOUR_MODEL>   (e.g. litellm_proxy/openai/gpt-4o)
- LITELLM_PROXY_API_BASE: <YOUR_PROXY_URL>   (e.g. http://your-proxy:4000/)
- LITELLM_PROXY_API_KEY:  <YOUR_API_KEY>
- also set OPENAI_API_BASE, OPENAI_BASE_URL, OPENAI_API_KEY to the same values
  (some sub-calls use the OPENAI_* env vars directly)

# 4. SCORER
- metric: tau2 task reward in [0,1] from results.json (the "score" field)
- results location: <PATH_TO_SKILLBERRY_BENCHMARKS>/exgentic/exgentic/outputs/*/sessions/*/results.json
  (pick the file with the most recent mtime after each run)

# 5. OPTIMIZER
- optimizer: claude-code
- model: claude-opus-4-6   (or whichever Opus model your CLI accepts)

# 6. BUDGET
- algorithm: all-at-once
- max_iterations: 20
- num_trials: 5      (tau2 is stochastic — more trials = lower noise)
- gate: significant, k_se: 0.5
```

Claude will:
1. Run **intake** — scaffold `.capevolve/project/` with the adapter, capevolve.yaml, and split_ids.json
2. Run **implement-and-check** — implement all 4 adapter methods and verify with `cap-evolve check`
3. Run **baseline** — score the seed capability on val
4. Run **all-at-once** — propose edits, gate on val, commit accepted candidates to git
5. Run **finalize** and **report** — sealed test score + dashboard

When finished, open the printed `dashboard.html` in your browser.

---

## Path B — manual setup

Use this if you want to understand the wiring, customise it, or run the
pipeline step by step.

### 1. Create the project scaffold

```bash
cd <CAP_EVOLVE_ROOT>
python3 skills/phases/intake/scripts/run.py --base .capevolve
```

This creates `.capevolve/project/` with a stub `adapter.py` and
`capevolve.yaml`.

### 2. Copy the seed capability

```bash
EXGENTIC_TAU2=<PATH_TO_SKILLBERRY_BENCHMARKS>/exgentic/exgentic/src/exgentic/benchmarks/tau2/installation/tau2-bench

cp $EXGENTIC_TAU2/data/tau2/domains/airline/policy.md \
   .capevolve/project/seed_capability/

cp $EXGENTIC_TAU2/src/tau2/domains/airline/tools.py \
   .capevolve/project/seed_capability/
```

### 3. Write the adapter

Create `.capevolve/project/adapters/adapter.py`. The key pieces:

**Paths** — adjust the one variable and everything else derives from it:

```python
SKILLBERRY_BENCHMARKS = Path("<PATH_TO_SKILLBERRY_BENCHMARKS>")
HARNESS_ROOT  = SKILLBERRY_BENCHMARKS / "exgentic"
EXGENTIC_DIR  = HARNESS_ROOT / "exgentic"
VENV_EXGENTIC = HARNESS_ROOT / ".venv" / "bin" / "exgentic"

LIVE_POLICY = (
    EXGENTIC_DIR
    / "src/exgentic/benchmarks/tau2/installation/tau2-bench"
    / "data/tau2/domains/airline/policy.md"
)
LIVE_TOOLS = (
    EXGENTIC_DIR
    / "src/exgentic/benchmarks/tau2/installation/tau2-bench"
    / "src/tau2/domains/airline/tools.py"
)
```

**Model + credentials:**

```python
# "litellm_proxy/" prefix routes directly to the proxy URL without
# LiteLLM trying to resolve the model prefix locally.
_MODEL = "litellm_proxy/<YOUR_MODEL>"   # e.g. "litellm_proxy/openai/gpt-4o"

_EXGENTIC_ENV_OVERLAY = {
    "LITELLM_PROXY_API_BASE": "<YOUR_PROXY_URL>",   # e.g. "http://your-proxy:4000/"
    "LITELLM_PROXY_API_KEY":  "<YOUR_API_KEY>",
    "OPENAI_API_BASE":  "<YOUR_PROXY_URL>",
    "OPENAI_BASE_URL":  "<YOUR_PROXY_URL>",
    "OPENAI_API_KEY":   "<YOUR_API_KEY>",
    "LITELLM_LOG":          "ERROR",
    "LITELLM_DROP_PARAMS":  "true",
}
```

> If your model is standard OpenAI (no proxy), just set `_MODEL = "gpt-4o"` and
> `"OPENAI_API_KEY": "<YOUR_KEY>"` — no proxy prefix or extra vars needed.

**The exgentic evaluate call** (inside `run_target`):

```python
cmd = [
    str(VENV_EXGENTIC), "evaluate",
    "--agent",     "smolagents_tool",
    "--benchmark", "tau2",
    "--subset",    "airline",
    "--model",     _MODEL,
    "--task",      task.id,
    "--num-tasks", "1",
    "--overwrite",
    "--set", f"benchmark.user_simulator_model={_MODEL}",
    "--set", "agent.model_settings.num_retries=3",
    "--set", "agent.model_settings.retry_after=1.0",
]
```

**Parsing results** — after each run, find the freshest
`outputs/*/sessions/*/results.json` (by mtime) and read the `"score"` field.

**`apply()`** — copies `policy.md` and `tools.py` from the candidate directory
to `LIVE_POLICY` / `LIVE_TOOLS` so the next exgentic run picks them up:

```python
def apply(self, candidate_dir, edits=None):
    if edits:
        for fname, content in edits.items():
            (Path(candidate_dir) / fname).write_text(content)
    shutil.copy2(Path(candidate_dir) / "policy.md", LIVE_POLICY)
    shutil.copy2(Path(candidate_dir) / "tools.py",  LIVE_TOOLS)
```

### 4. Write `capevolve.yaml`

```yaml
# .capevolve/project/capevolve.yaml
capabilities:       [system-prompt, tools]
capability_path:    seed_capability
optimizer_skill:    claude-code           # or: codex | gemini-cli | opencode
optimizer_model:    claude-opus-4-6
algorithm_skill:    all-at-once
dataset_source:     adapter
split_ids_file:     "inputs/split_ids.json"
num_trials:         5
gate_mode:          significant
gate_k_se:          0.5
max_iterations:     20
stall:              5
store:              git
```

### 5. Write `split_ids.json`

```bash
mkdir -p .capevolve/project/inputs
```

For a **single task** (fit metric, no holdout):

```json
{"train": ["9"], "val": ["9"], "test": ["9"]}
```

For multiple tasks with explicit splits:

```json
{
  "train": ["1","2","3","4","5"],
  "val":   ["6","7"],
  "test":  ["8","9"]
}
```

> Single-task all-in-each runs are valid for iterative improvement.
> cap-evolve logs a `splits_warning` and the test number is labelled a
> **fit metric** (not held-out). Use a proper split for final reporting.

### 6. Run

```bash
export PYTHONPATH="$PWD/core:$PYTHONPATH"
export CAPEVOLVE_SKILLS_DIR="$PWD/skills"

# Gate check — must print {"ok": true} before spending any budget
python3 -m cap_evolve.cli check .capevolve/project

# Full pipeline
python3 -m cap_evolve.cli run \
    --spec    .capevolve/project/capevolve.yaml \
    --project .capevolve/project
```

---

## Reviewing results

| Artifact | Contents |
|---|---|
| `.capevolve/run_<ts>/dashboard.html` | KPI cards, score-over-iterations, accept/reject timeline, candidate leaderboard — open in any browser (works offline) |
| `.capevolve/run_<ts>/report.md` | Baseline → best-val → test in plain text |
| `.capevolve/run_<ts>/final.json` | Machine-readable result (`test_reward`, `best_id`, `pass_k`) |
| `.capevolve/run_<ts>/candidates/cand_XXXX/` | The winning `policy.md` and `tools.py` |

---

## Troubleshooting

### LiteLLM: "LLM Provider NOT provided"

Custom proxy prefixes like `rits/` are not recognized by LiteLLM's local
provider resolver. Fix: use `litellm_proxy/<model>` and set
`LITELLM_PROXY_API_BASE` / `LITELLM_PROXY_API_KEY` in the env overlay.
This tells LiteLLM to forward the model string directly to the proxy URL
without local resolution.

### Exgentic health-check fails on startup

If the exgentic process fails before the benchmark runs (health-check error
for unrecognized model prefix), add `"EXGENTIC_SKIP_MODEL_HEALTH_CHECK": "1"`
to `_EXGENTIC_ENV_OVERLAY` in the adapter — this bypasses the pre-flight
check while still running the actual benchmark.

### High variance / all candidates rejected

Increase `num_trials` (5 → 8) to reduce standard error, or relax the gate
(`gate_k_se: 0.3`). With a single task and a stochastic agent, variance is
expected — the optimizer converges over several accepted iterations.

### Verify the proxy is reachable

```bash
curl -s <YOUR_PROXY_URL>/v1/models | head -c 200
```
