# Benchmarks

One directory per benchmark. Each holds a `template/` (copy-and-run adapter — the
common case: config, not code) and/or an `examples/<variant>/` (a full worked run
against the real benchmark, with its own `setup.sh`/`run.sh` and, for some, a
committed `run_full/` showing real numbers).

New to a benchmark here? Start with its template if it has one; otherwise copy the
closest `examples/<variant>/`. See [`ADDING_A_BENCHMARK.md`](ADDING_A_BENCHMARK.md)
to onboard one that isn't here yet.

| Benchmark | `template/` | `examples/` | What it optimizes | Task source |
|---|---|---|---|---|
| [`generic/jsonl_litellm`](generic/jsonl_litellm/template) | yes | — | A system prompt | A local `tasks.jsonl` |
| [`generic/huggingface_litellm`](generic/huggingface_litellm/template) | yes | — | A system prompt | `datasets.load_dataset(...)` |
| [`generic/harbor`](generic/harbor/template) | yes | — | A skill package, via Harbor's Claude Code agent | Harbor's own dataset/harness |
| [`tau2`](tau2) | [`template`](tau2/template) ([tau2-bench](https://github.com/sierra-research/tau2-bench)) | [`airline`](tau2/examples/airline), [`sierra_airline`](tau2/examples/sierra_airline) (direct + blackbox delivery arms) | System-prompt policy + tools | tau2's own runner |
| [`skillsbench`](skillsbench) | [`template`](skillsbench/template) ([SkillsBench](https://github.com/benchflow-ai/skillsbench)) | [`shared_skills`](skillsbench/examples/shared_skills) | Shared Agent Skills | BenchFlow `bench eval run` |
| [`swe_bench`](swe_bench/template) | yes ([SWE-bench / Lite](https://github.com/swe-bench/SWE-bench)) | — | Coding-agent prompt | HuggingFace + Docker harness |
| [`spreadsheetbench`](spreadsheetbench/template) | yes ([SpreadsheetBench](https://github.com/RUCKBReasoning/SpreadsheetBench)) | — | Spreadsheet-agent system prompt | Fetched dataset + Docker/Jupyter harness |
| [`rfe_creator`](rfe_creator/template) | yes ([RFE-Creator](https://github.com/opendatahub-io/rfe-creator)) | — | 7 Claude Code skills (RFE create/review/split/submit pipeline) | Fetched dataset + [agent-eval-harness](https://github.com/opendatahub-io/agent-eval-harness) |
| [`appworld`](appworld/examples/react_agent) | — | [`react_agent`](appworld/examples/react_agent) ([AppWorld](https://appworld.dev)) | Agent prompt + REPL helpers + API notes | AppWorld's own task suite |
| [`parsec`](parsec/examples/rca_prompts) | — | [`rca_prompts`](parsec/examples/rca_prompts) | Multi-agent RCA system prompts | Authored RCA scenarios (external runtime) |
| [`toy`](toy/examples) | — | [`calc`](toy/examples/calc), [`skill`](toy/examples/skill) | Nothing real — zero-API proof of the loop | Mocked |

## Shared helpers

| Path | Purpose |
|---|---|
| [`_shared/model_config.py`](_shared/model_config.py) | Provider-agnostic model wiring for **any** litellm provider, via env vars |
| [`_scaffold/project`](_scaffold/project) | The generic project scaffold `cap-evolve init` and the `intake` skill copy from |
| [`_scaffold/skill`](_scaffold/skill) | The scaffold for a new **cap-evolve skill** itself (see `CONTRIBUTING.md`) — unrelated to the benchmarks above |

## Quick start (generic `jsonl_litellm`)

```bash
# 1. Copy the template + shared helper into your project
cp -r benchmarks/generic/jsonl_litellm/template/*  .capevolve/project/adapters/
cp    benchmarks/_shared/model_config.py           .capevolve/project/adapters/
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

Full per-template env-var tables, provider matrix, and the "write your own" guide:
[`docs/ADAPTER_TEMPLATES.md`](../docs/ADAPTER_TEMPLATES.md).

## Writing your own adapter

If none of the above fit, start from the stub at
[`_scaffold/project/adapters/adapter.py`](_scaffold/project/adapters/adapter.py) and
implement the three required methods — see
[`docs/ADAPTER_CONTRACT.md`](../docs/ADAPTER_CONTRACT.md):

1. **`tasks(split)`** — return your eval tasks
2. **`run_target(task, ctx, *, seed)`** — run the agent under test
3. **`score(task, rollout)`** — return reward in `[0,1]` + feedback

To turn a one-off adapter into a benchmark that lives here, see
[`ADDING_A_BENCHMARK.md`](ADDING_A_BENCHMARK.md).
