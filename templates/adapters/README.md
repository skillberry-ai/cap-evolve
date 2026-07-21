# Adapter Templates

Ready-to-use cap-evolve adapter templates. Onboarding a benchmark should be
**config, not code** — for the common cases you set env vars and run; you only
write code when your task loading or scoring is genuinely custom.

Copy a template into `.capevolve/project/adapters/`, drop `model_config.py` next
to it, set credentials in a `.env`, and run `cap-evolve check && cap-evolve run`.

## Templates

| Template | Best for | What it optimizes | Task source |
|---|---|---|---|
| [`jsonl_litellm/`](jsonl_litellm/) | **The common case** — start here | A system prompt | A local `tasks.jsonl` |
| [`huggingface_litellm/`](huggingface_litellm/) | Any HuggingFace eval dataset | A system prompt | `datasets.load_dataset(...)` |
| [`tau2_bench/`](tau2_bench/) | [tau2-bench](https://github.com/sierra-research/tau2-bench) airline | System-prompt policy + tools | tau2's own runner |
| [`skillsbench/`](skillsbench/) | [SkillsBench](https://github.com/benchflow-ai/skillsbench) | Shared Agent Skills | BenchFlow `bench eval run` |
| [`swe_bench/`](swe_bench/) | [SWE-bench / Lite](https://github.com/swe-bench/SWE-bench) | Coding-agent prompt | HuggingFace + Docker harness |

The first two are **generic** — point them at your data with env vars, no code
edits. The last three are **worked benchmark adapters** you copy and run.

## Shared helper

| File | Purpose |
|---|---|
| [`model_config.py`](model_config.py) | Provider-agnostic model wiring for **any** litellm provider, via env vars |

## Quick start (generic `jsonl_litellm`)

```bash
# 1. Copy the template + shared helper into your project
cp -r templates/adapters/jsonl_litellm/*  .capevolve/project/adapters/
cp    templates/adapters/model_config.py  .capevolve/project/adapters/
mv    .capevolve/project/adapters/seed_capability  .capevolve/project/seed_capability

# 2. Point it at your tasks + pick a scoring mode + set a model (.env at repo root)
cat >> .env <<'EOF'
TASKS_FILE=/path/to/tasks.jsonl     # {"id","input","target"} per line
SCORING=exact                       # exact | contains | regex
MODEL=gpt-4.1-mini
OPENAI_API_KEY=sk-…
EOF

# 3. Run
cap-evolve check     # gate check — must print {"ok": true}
cap-evolve run       # baseline → optimize → sealed test → dashboard.html
```

## Providers — one line to switch (`model_config.py`)

Set `MODEL` and the matching credentials; **no adapter code changes**.

```bash
MODEL=gpt-4.1-mini                         OPENAI_API_KEY=sk-…            # OpenAI
MODEL=anthropic/claude-sonnet-4-6          ANTHROPIC_API_KEY=sk-ant-…     # Anthropic
MODEL=vertex_ai/claude-sonnet-4-6                                         # Vertex AI (ADC — no key)
MODEL=azure/gpt-4o    AZURE_API_KEY=…      AZURE_API_BASE=https://….openai.azure.com   # Azure
MODEL=ollama/qwen2.5:7b-instruct           API_BASE=http://localhost:11434  # Ollama (local, free)
MODEL=litellm_proxy/my-model  LITELLM_PROXY_API_BASE=http://proxy:4000  LITELLM_PROXY_API_KEY=sk-…  # any proxy/gateway
MODEL=openai/my-model  OPENAI_API_KEY=…    OPENAI_API_BASE=http://my-endpoint/v1        # any OpenAI-compatible
```

Full per-template env-var tables, provider matrix, and the "write your own"
guide: [`docs/ADAPTER_TEMPLATES.md`](../../docs/ADAPTER_TEMPLATES.md).

## Writing your own adapter

If none fit, start from the stub at
[`templates/project/adapters/adapter.py`](../project/adapters/adapter.py) and
implement the three required methods — see
[`docs/ADAPTER_CONTRACT.md`](../../docs/ADAPTER_CONTRACT.md):

1. **`tasks(split)`** — return your eval tasks
2. **`run_target(task, ctx, *, seed)`** — run the agent under test
3. **`score(task, rollout)`** — return reward in `[0,1]` + feedback
