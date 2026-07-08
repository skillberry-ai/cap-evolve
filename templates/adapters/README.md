# Adapter Templates

Ready-to-use cap-evolve adapter templates for common benchmarks. Each template
is a complete, working adapter — copy it to `.capevolve/project/adapters/`,
set your credentials, and run.

## Templates

| Template | Benchmark | What it optimizes | Provider support |
|---|---|---|---|
| [`tau2_bench/`](tau2_bench/) | [tau2-bench](https://github.com/sierra-research/tau2-bench) airline | System-prompt policy + tool implementations | Any litellm provider (OpenAI, Anthropic, Vertex AI, Ollama, RITS, …) |
| [`skillsbench/`](skillsbench/) | [SkillsBench](https://github.com/benchflow-ai/skillsbench) | Shared office-document Agent Skills (docx, pptx, xlsx, pdf) | Anthropic-compatible gateway |
| [`swe_bench/`](swe_bench/) | [SWE-bench / SWE-bench Lite](https://github.com/princeton-nlp/SWE-bench) | Coding agent system prompt | Any litellm provider |

## Shared helper

| File | Purpose |
|---|---|
| [`model_config.py`](model_config.py) | Reusable model-wiring for any litellm-supported provider via env vars |

## Quick start

### 1. Pick a template and copy it

```bash
# Example: tau2-bench
cp -r templates/adapters/tau2_bench/*  .capevolve/project/adapters/
cp templates/adapters/model_config.py  .capevolve/project/adapters/
```

### 2. Set credentials (`.env` at repo root)

```bash
# OpenAI
MODEL=gpt-4.1-mini
OPENAI_API_KEY=sk-…

# OR Anthropic
MODEL=anthropic/claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-…

# OR Ollama (local, free)
MODEL=ollama/qwen2.5:7b-instruct
API_BASE=http://localhost:11434

# OR Azure OpenAI
MODEL=azure/gpt-4o
AZURE_API_KEY=…
AZURE_API_BASE=https://….openai.azure.com

# OR Google Vertex AI (uses ADC)
MODEL=vertex_ai/claude-sonnet-4-6

# OR IBM RITS
MODEL=hosted_vllm/openai/gpt-oss-120b
RITS_API_KEY=…
API_BASE=https://…/v1

# OR LiteLLM Proxy (any model behind a proxy)
MODEL=litellm_proxy/my-model
LITELLM_PROXY_API_BASE=http://proxy:4000
LITELLM_PROXY_API_KEY=sk-…
```

### 3. Run

```bash
cap-evolve check     # gate check — must print {"ok": true}
cap-evolve run       # full optimization pipeline
```

---

## Template details

### tau2-bench (`tau2_bench/`)

Optimizes the **tau2-bench airline agent** — its system-prompt policy and tool
implementations. tau2 simulates customer-service conversations where an LLM agent
must perform correct actions (bookings, cancellations, modifications) and
communicate the right information.

**Prerequisites:**
- Clone & install tau2-bench: `git clone https://github.com/sierra-research/tau2-bench ../tau2-bench && pip install -e ../tau2-bench`
- Any litellm-compatible model endpoint

**Files:**
- `adapter.py` — the adapter (tasks → run_batch → score → apply)
- `capevolve.yaml` — cap-evolve config (5 trials for stochastic eval)

**Key env vars:**
| Variable | Required | Example |
|---|---|---|
| `MODEL` | Yes | `gpt-4.1-mini`, `anthropic/claude-sonnet-4-6` |
| `OPENAI_API_KEY` | For OpenAI | `sk-…` |
| `TAU2_MAX_CONCURRENCY` | No (default: 100) | `125` |

---

### SkillsBench (`skillsbench/`)

Optimizes the **four shared office-document Agent Skills** (docx, pptx, xlsx,
pdf) that SkillsBench hands its Claude agent. Each skill is a sub-package with
a `SKILL.md`; improving them moves many tasks at once.

**Prerequisites:**
- Install the `bench` CLI (BenchFlow): see https://github.com/benchflow-ai/bench
- Docker (tasks run in isolated containers)
- Anthropic-compatible gateway credentials

**Files:**
- `adapter.py` — the adapter (tasks → run_batch → score)
- `capevolve.yaml` — cap-evolve config

**Key env vars:**
| Variable | Required | Example |
|---|---|---|
| `ANTHROPIC_BASE_URL` | Yes | `https://api.anthropic.com` |
| `ANTHROPIC_AUTH_TOKEN` | Yes | `sk-ant-…` |
| `SKILLSBENCH_BENCH_BIN` | No | `/path/to/bench` |
| `SKILLSBENCH_CONCURRENCY` | No (default: 7) | `10` |

---

### SWE-bench (`swe_bench/`)

Optimizes a **coding agent's system prompt** for SWE-bench / SWE-bench Lite.
The agent reads a GitHub issue, generates a unified diff patch, and the
SWE-bench harness tests the patch against the repository's test suite in Docker.

**Prerequisites:**
- `pip install swebench datasets`
- Docker (evaluation runs patches in isolated containers)
- Any litellm-compatible model endpoint

**Files:**
- `adapter.py` — the adapter (tasks → run_target → score)
- `capevolve.yaml` — cap-evolve config

**Key env vars:**
| Variable | Required | Example |
|---|---|---|
| `MODEL` | Yes | `gpt-4.1-mini`, `anthropic/claude-sonnet-4-6` |
| `OPENAI_API_KEY` | For OpenAI | `sk-…` |
| `SWEBENCH_DATASET` | No (default: `princeton-nlp/SWE-bench_Lite`) | `princeton-nlp/SWE-bench` |
| `SWEBENCH_SPLIT` | No (default: `test`) | `dev` |
| `SWEBENCH_TIMEOUT` | No (default: 300s) | `600` |

---

## Writing your own adapter

If none of these templates fit, start from the stub at
[`templates/project/adapters/adapter.py`](../project/adapters/adapter.py) and
implement the three required methods:

1. **`tasks(split)`** — return your eval tasks
2. **`run_target(task, ctx, *, seed)`** — run the agent under test
3. **`score(task, rollout)`** — return reward in [0,1] + feedback

See [`core/cap_evolve/adapter.py`](../../core/cap_evolve/adapter.py) and
[`docs/ADAPTER_CONTRACT.md`](../../docs/ADAPTER_CONTRACT.md) for the full contract.
