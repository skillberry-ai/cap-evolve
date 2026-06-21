# How to run cap-evolve against Exgentic / tau2-bench

Optimize the **airline `policy.md` (system prompt) and `tools.py`** jointly, using
the [exgentic](https://github.com/skillberry-ai/skillberry-benchmarks) harness as
the runner and tau2-bench as the benchmark. The optimizer (Claude Code or equivalent)
proposes edits each iteration; exgentic evaluates them; cap-evolve gates and records
only the edits that genuinely improve the val score.

---

## Prerequisites

| What | Where / how to get it |
|---|---|
| `cap-evolve` installed | `pip install ./core && ./install.sh` (repo root) |
| `exgentic` repo cloned and its venv built | See exgentic README; venv must contain the `exgentic` CLI |
| `tau2-bench` installed inside the exgentic venv | Installed by the exgentic setup — airline `policy.md` and `tools.py` must exist at the paths below |
| A **LiteLLM proxy** (or compatible OpenAI endpoint) | Any endpoint that accepts `POST /v1/chat/completions` |
| An optimizer CLI (`claude`, `codex`, `gemini`, …) | Whichever host you use for the optimizer |

## Directory layout

Everything cap-evolve needs lives under `.capevolve/project/` inside your working
directory (the cap-evolve repo root, or any project folder):

```
.capevolve/
└── project/
    ├── capevolve.yaml             # run spec
    ├── adapters/
    │   └── adapter.py             # 4-method adapter (see below)
    ├── inputs/
    │   └── split_ids.json         # which task ids go in train / val / test
    └── seed_capability/
        ├── policy.md              # copy of the airline policy you want to optimize
        └── tools.py               # copy of the airline tools.py you want to optimize
```

Copy the current live files into `seed_capability/` once:

```bash
cp <EXGENTIC_DIR>/src/exgentic/benchmarks/tau2/installation/tau2-bench/data/tau2/domains/airline/policy.md \
   .capevolve/project/seed_capability/

cp <EXGENTIC_DIR>/src/exgentic/benchmarks/tau2/installation/tau2-bench/src/tau2/domains/airline/tools.py \
   .capevolve/project/seed_capability/
```

---

## Step 1 — write the adapter

Create `.capevolve/project/adapters/adapter.py` with the content below.
Replace every `<PLACEHOLDER>` with your values:

```python
"""Adapter: tau2-bench airline via exgentic, optimizing policy.md + tools.py."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

# ── paths ────────────────────────────────────────────────────────────────────
HARNESS_ROOT  = Path("<ABSOLUTE_PATH_TO_EXGENTIC_REPO>")
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

# ── model + env ──────────────────────────────────────────────────────────────
# Use the "litellm_proxy/" prefix so LiteLLM forwards the model name directly
# to the proxy URL without trying to resolve it as a known local provider.
_MODEL = "litellm_proxy/<YOUR_MODEL_NAME>"   # e.g. "litellm_proxy/openai/gpt-4o"

_EXGENTIC_ENV_OVERLAY = {
    "LITELLM_PROXY_API_BASE": "<YOUR_PROXY_URL>",   # e.g. "http://my-proxy:4000/"
    "LITELLM_PROXY_API_KEY":  "<YOUR_PROXY_API_KEY>",
    # Keep these for any sub-calls that use OPENAI_* env vars directly.
    "OPENAI_API_BASE":  "<YOUR_PROXY_URL>",
    "OPENAI_BASE_URL":  "<YOUR_PROXY_URL>",
    "OPENAI_API_KEY":   "<YOUR_PROXY_API_KEY>",
    "LITELLM_LOG":      "ERROR",
    "LITELLM_DROP_PARAMS": "true",
}

# Which task id(s) to evaluate. For a single-task run use the task's id string.
# For multi-task runs, tasks() returns one Task per id found in the split file.
_TASK_IDS = ["<TASK_ID>"]   # e.g. ["9"]  or  ["1", "5", "9"]

_TIMEOUT = 600  # seconds per trial


class Adapter(CapabilityAdapter):

    def tasks(self, split: str) -> list[Task]:  # noqa: ARG002
        return [Task(id=tid) for tid in _TASK_IDS]

    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        if edits:
            for fname, content in edits.items():
                (Path(candidate_dir) / fname).write_text(content, encoding="utf-8")
        candidate_dir = Path(candidate_dir)
        policy_src = candidate_dir / "policy.md"
        tools_src  = candidate_dir / "tools.py"
        if policy_src.exists():
            shutil.copy2(policy_src, LIVE_POLICY)
        if tools_src.exists():
            shutil.copy2(tools_src, LIVE_TOOLS)

    def run_target(self, task: Task, candidate_dir: Path, split: str) -> Rollout:
        outputs_dir = EXGENTIC_DIR / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        t_before = time.time()

        env = {**os.environ, **_EXGENTIC_ENV_OVERLAY}
        cmd = [
            str(VENV_EXGENTIC),
            "evaluate",
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

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True, text=True,
                env=env, cwd=str(EXGENTIC_DIR),
                timeout=_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return Rollout(
                task_id=task.id,
                error=f"exgentic timed out after {_TIMEOUT}s",
                metadata={"tau2_score": 0.0},
            )

        tau2_score, details, error = _parse_results(
            outputs_dir, t_before, proc.returncode, proc.stderr
        )
        return Rollout(
            task_id=task.id,
            output=proc.stdout[-3000:] if proc.stdout else None,
            trace=proc.stderr[-1000:]  if proc.stderr else None,
            error=error,
            metadata={"tau2_score": tau2_score, "returncode": proc.returncode, "details": details},
        )

    def score(self, task: Task, rollout: Rollout) -> Score:
        reward  = float(rollout.metadata.get("tau2_score", 0.0))
        details = rollout.metadata.get("details", {})

        if rollout.error and reward == 0.0 and not details:
            return Score(task_id=task.id, reward=0.0,
                         feedback=f"Run failed (infra/timeout): {rollout.error[:300]}")

        if reward >= 1.0:
            feedback = "Task completed successfully — all constraints satisfied."
        elif reward > 0.0:
            feedback = (
                f"Partial success (score={reward:.2f}). "
                "Review which constraints were missed and whether tools returned "
                "accurate information."
            )
        else:
            status = str(details.get("status", ""))
            if details.get("is_finished") is False:
                feedback = (
                    "Agent did not finish (hit step limit or got stuck). "
                    "Clarify policy steps or ensure tools provide enough information."
                )
            elif status:
                feedback = (
                    f"Task failed (status={status}). "
                    "Review the airline policy for missing rules, ambiguous constraints, "
                    "or tools that may return incorrect data."
                )
            else:
                feedback = (
                    "Task failed with score 0. "
                    "Check that the policy clearly states the correct procedure and "
                    "that tools return accurate, well-formatted information."
                )
        return Score(task_id=task.id, reward=reward, feedback=feedback)


def _parse_results(
    outputs_dir: Path, t_before: float, returncode: int, stderr: str
) -> tuple[float, dict, str | None]:
    error = f"exgentic rc={returncode}: {stderr[:500]}" if returncode != 0 else None

    candidates: list[tuple[float, Path]] = []
    for p in outputs_dir.rglob("sessions/*/results.json"):
        try:
            mtime = p.stat().st_mtime
            if mtime >= t_before:
                candidates.append((mtime, p))
        except OSError:
            continue

    if candidates:
        candidates.sort(reverse=True)
        try:
            data = json.loads(candidates[0][1].read_text(encoding="utf-8"))
            score_val = data.get("score")
            if score_val is not None:
                return float(score_val), data, error
        except Exception as e:
            error = (error or "") + f" | parse error: {e}"

    return 0.0, {}, error or "No results.json found after run"
```

---

## Step 2 — write `capevolve.yaml`

```yaml
# .capevolve/project/capevolve.yaml
capabilities:       [system-prompt, tools]
capability_path:    seed_capability           # relative to .capevolve/project/
optimizer_skill:    claude-code               # swap: codex | gemini-cli | opencode | ibm-bob
optimizer_model:    claude-opus-4-6           # model your optimizer CLI accepts
algorithm_skill:    all-at-once
dataset_source:     adapter
split_ids_file:     "inputs/split_ids.json"
num_trials:         5                         # >=3 for a stochastic agent; more = less noise
gate_mode:          significant
gate_k_se:          0.5                       # accept if Δ > 0.5 × SE (relaxed for noisy tasks)
max_iterations:     20
stall:              5                         # stop after 5 consecutive rejections
store:              git
```

> **gate_k_se tuning:** `0.5` is relaxed (accepts more candidates under noise). Use
> `1.0` for a stricter gate once your eval is less noisy or you have more trials.

---

## Step 3 — write `split_ids.json`

For a **single task** (fit metric, no holdout):

```json
{"train": ["<TASK_ID>"], "val": ["<TASK_ID>"], "test": ["<TASK_ID>"]}
```

For **multiple tasks** with an explicit split:

```json
{
  "train": ["1", "2", "3", "4", "5"],
  "val":   ["6", "7"],
  "test":  ["8", "9"]
}
```

> When `train = val = test`, cap-evolve logs a `splits_warning` and the test number
> is reported as a **fit metric** (not a held-out result). This is fine for
> exploration; use a proper split before reporting final numbers.

---

## Step 4 — run the pipeline

These are the exact commands. Run them from the cap-evolve repo root.

```bash
# Make sure cap-evolve-core is on the Python path
export PYTHONPATH="$PWD/core:$PYTHONPATH"
export CAPEVOLVE_SKILLS_DIR="$PWD/skills"

# 1. Check the adapter wiring (hard gate — must print {"ok": true})
python3 -m cap_evolve.cli check .capevolve/project

# 2. Run the full pipeline (baseline → optimize → finalize → report)
python3 -m cap_evolve.cli run \
    --spec    .capevolve/project/capevolve.yaml \
    --project .capevolve/project

# The run directory is printed; open the dashboard when done:
#   open .capevolve/run_<timestamp>/dashboard.html
```

Or drive it **phase-by-phase** (useful for debugging or resuming):

```bash
# Baseline only
python3 skills/phases/baseline/scripts/run.py \
    --project .capevolve/project

# Optimize (runs the algorithm loop)
python3 skills/algorithms/all-at-once/scripts/run.py \
    --project .capevolve/project \
    --run-dir .capevolve/run_<timestamp>

# Finalize + report
python3 skills/phases/finalize/scripts/run.py \
    --run-dir .capevolve/run_<timestamp>

python3 skills/phases/report/scripts/run.py \
    --run-dir .capevolve/run_<timestamp>
```

---

## Step 5 — review the results

After the pipeline finishes:

| Artifact | What it contains |
|---|---|
| `.capevolve/run_<ts>/dashboard.html` | KPI cards, score-over-iterations, accept/reject timeline, candidate leaderboard — open in any browser |
| `.capevolve/run_<ts>/report.md` | Baseline → best-val → test in plain text |
| `.capevolve/run_<ts>/final.json` | Machine-readable result (`test_reward`, `best_id`, `pass_k`) |
| `.capevolve/run_<ts>/candidates/cand_XXXX/` | The winning `policy.md` and `tools.py` |

---

## Troubleshooting

### LiteLLM: "LLM Provider NOT provided"

LiteLLM's local client doesn't recognize custom proxy prefixes like `rits/` or
`watsonx/`. The fix is to use the `litellm_proxy/` prefix:

```python
_MODEL = "litellm_proxy/<YOUR_MODEL_NAME>"
```

and set `LITELLM_PROXY_API_BASE` / `LITELLM_PROXY_API_KEY` in the env overlay (done
above). This tells LiteLLM to forward the model name directly to the proxy URL
without local provider resolution.

### Exgentic health-check fails for unrecognized model prefix

If exgentic's startup health check also fails, patch
`exgentic/src/exgentic/integrations/litellm/health.py` to skip the health check
when `EXGENTIC_SKIP_MODEL_HEALTH_CHECK=1` is set, or add
`"EXGENTIC_SKIP_MODEL_HEALTH_CHECK": "1"` to `_EXGENTIC_ENV_OVERLAY` in the adapter.

### `cap-evolve check` hangs or times out

The check runs one trial end-to-end. If exgentic hangs, reduce `_TIMEOUT` in the
adapter or check that the proxy endpoint is reachable:

```bash
curl -s <YOUR_PROXY_URL>/v1/models | head -c 200
```

### High variance / all candidates rejected

Increase `num_trials` (5 → 8) to reduce stderr, or relax the gate (`gate_k_se: 0.3`).
With a single task and 5 trials, variance is expected — the optimizer still converges
over several accepted iterations.
