# Adapter templates

Onboarding a benchmark into cap-evolve should be **config, not code**. Writing an
adapter from scratch every time is a bottleneck for automated pipelines, so
`templates/adapters/` ships ready-to-use adapters plus a provider-agnostic
model-wiring helper. For the common cases you set env vars and run; you only
write code when task loading or scoring is genuinely custom.

Every template is copy-and-run:

```bash
cp -r templates/adapters/<template>/*  .capevolve/project/adapters/
cp    templates/adapters/model_config.py  .capevolve/project/adapters/
# move the seed prompt where the spec expects it
mv    .capevolve/project/adapters/seed_capability  .capevolve/project/seed_capability
# set MODEL + credentials in a repo-root .env, then:
cap-evolve check && cap-evolve run
```

## Which template?

| Template | Best for | What it optimizes | Task source | Extra deps |
|---|---|---|---|---|
| [`jsonl_litellm/`](../templates/adapters/jsonl_litellm/) | **The common case** — start here | A system prompt | local `tasks.jsonl` | `litellm` |
| [`huggingface_litellm/`](../templates/adapters/huggingface_litellm/) | Any HuggingFace eval dataset | A system prompt | `datasets.load_dataset(...)` | `litellm`, `datasets` |
| [`tau2_bench/`](../templates/adapters/tau2_bench/) | tau2-bench airline | System-prompt policy **+ tool code** | tau2's runner | tau2-bench |
| [`skillsbench/`](../templates/adapters/skillsbench/) | SkillsBench | Shared Agent Skills | BenchFlow `bench eval run` | `bench` CLI, Docker |
| [`swe_bench/`](../templates/adapters/swe_bench/) | SWE-bench / Lite | Coding-agent prompt | HuggingFace + Docker harness | `swebench`, `datasets`, Docker |

The first two are **generic** — point them at your data with env vars, no code
edits. The last three are **worked benchmark adapters** you copy and run.

## Providers — one line to switch

All templates wire the model through [`model_config.py`](../templates/adapters/model_config.py),
which resolves credentials from env vars based on the `MODEL` prefix (the same
routing litellm does). Switching providers is a one-line `MODEL=` change — **no
adapter code edits** — and it is **lazy**: no network at import, so `cap-evolve
check` stays offline.

| Provider | `.env` |
|---|---|
| OpenAI | `MODEL=gpt-4.1-mini` · `OPENAI_API_KEY=sk-…` |
| Anthropic | `MODEL=anthropic/claude-sonnet-4-6` · `ANTHROPIC_API_KEY=sk-ant-…` |
| Google Vertex AI | `MODEL=vertex_ai/claude-sonnet-4-6` (uses ADC — no key) |
| Azure OpenAI | `MODEL=azure/gpt-4o` · `AZURE_API_KEY=…` · `AZURE_API_BASE=https://….openai.azure.com` |
| Ollama (local) | `MODEL=ollama/qwen2.5:7b-instruct` · `API_BASE=http://localhost:11434` |
| LiteLLM proxy / gateway | `MODEL=litellm_proxy/my-model` · `LITELLM_PROXY_API_BASE=http://proxy:4000` · `LITELLM_PROXY_API_KEY=sk-…` |
| Any OpenAI-compatible | `MODEL=openai/my-model` · `OPENAI_API_KEY=…` · `OPENAI_API_BASE=http://my-endpoint/v1` |

`TEMPERATURE` (default `0.0`) and `MAX_TOKENS` (optional output cap — set it high for
reasoning models or long outputs like patches) apply to every provider. For a provider
not listed, set the generic `API_BASE` / `API_KEY` (or that provider's own litellm vars).

## `jsonl_litellm` — the common case

Tasks are one JSON object per line: `{"id": "...", "input": "...", "target": "..."}`.
The agent's **system prompt** (`seed_capability/prompt.txt`) is what the optimizer edits.

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MODEL` + credentials | yes | `gpt-4.1-mini` | see the provider table |
| `TASKS_FILE` | no | `tasks.jsonl` next to the adapter | path to your JSONL |
| `SCORING` | no | `exact` | `exact` \| `contains` \| `regex` (for `regex`, `target` is the pattern) |

## `huggingface_litellm` — any HuggingFace dataset

Same as above, but tasks come from `datasets.load_dataset(...)`. Map your dataset's
columns with env vars — no code changes:

| Variable | Required | Default | Notes |
|---|---|---|---|
| `HF_DATASET` | yes | — | e.g. `openai/gsm8k` |
| `HF_CONFIG` | no | — | dataset config, e.g. `main` |
| `HF_SPLIT` | no | `test` | dataset split |
| `INPUT_FIELD` | no | `question` | column used as the prompt input |
| `TARGET_FIELD` | no | `answer` | column used as the gold target |
| `ID_FIELD` | no | row index | column used as the task id |
| `SCORING` | no | `exact` | `exact` \| `contains` \| `regex` |

## `tau2_bench` — airline policy + tools

Optimizes the tau2-bench airline agent's **system-prompt policy and tool
implementations** via tau2's own batch runner and reward. tau2 is stochastic, so
the config uses `num_trials: 5`.

- **Prerequisites:** `git clone https://github.com/sierra-research/tau2-bench && pip install -e tau2-bench`; the seed policy/tools come from the benchmark (see [`examples/tau2_airline/`](../examples/tau2_airline/)).
- **Key env vars:** `MODEL` + credentials; `TAU2_MAX_CONCURRENCY` (default 100).

## `skillsbench` — shared Agent Skills

Optimizes the shared Agent Skills SkillsBench hands its Claude agent, via BenchFlow's
`bench eval run` in Docker.

- **Prerequisites:** the `bench` CLI (BenchFlow), Docker, and Anthropic-gateway credentials.
- **Key env vars:** `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`; `SKILLSBENCH_MODEL` (the in-sandbox agent model as your gateway names it, default `claude-sonnet-4-6`), `SKILLSBENCH_AGENT`, `SKILLSBENCH_SANDBOX` (`docker`|`modal`), `SKILLSBENCH_BENCH_BIN`, `SKILLSBENCH_CONCURRENCY` (default 7).

## `swe_bench` — coding-agent prompt

The agent reads a GitHub issue and emits a unified-diff patch; the SWE-bench Docker
harness tests it. Binary reward per instance. Optimizes `seed_capability/prompt.md`.

- **Prerequisites:** `pip install swebench datasets`; Docker.
- **Keep it cheap:** evaluation is a Docker build per instance. Pin a small subset with
  `SWEBENCH_INSTANCE_IDS` (comma-separated) so the split ratios partition just that subset.

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MODEL` + credentials | yes | — | see the provider table |
| `SWEBENCH_DATASET` | no | `princeton-nlp/SWE-bench_Lite` | any SWE-bench dataset |
| `SWEBENCH_SPLIT` | no | `test` | dataset split |
| `SWEBENCH_INSTANCE_IDS` | no | (whole split) | comma-separated subset — the cheap-run knob |
| `SWEBENCH_MAX_WORKERS` | no | `4` | parallel evaluations |
| `SWEBENCH_TIMEOUT` | no | `1800` | per-instance timeout (s); first-run image builds are slow |
| `SWEBENCH_NAMESPACE` | no | `none` | `none` builds images locally (arm64/Mac-safe); `swebench` pulls prebuilt x86 |

## Writing your own adapter

If none fit, start from the stub at
[`templates/project/adapters/adapter.py`](../templates/project/adapters/adapter.py)
and implement the three required methods; the full contract (including `materialize`
/ `live` and the per-trial `seed`) is in [ADAPTER_CONTRACT.md](ADAPTER_CONTRACT.md):

1. **`tasks(split)`** — return your eval tasks (deterministic per split)
2. **`run_target(task, ctx, *, seed)`** — run the agent under test (forward `seed` if stochastic)
3. **`score(task, rollout)`** — return reward in `[0,1]` + natural-language feedback

Splits, trials, gating, pass^k, the sealed test, and the dashboard are provided by
the core — never reimplement them in an adapter; that is what keeps evaluation honest.
