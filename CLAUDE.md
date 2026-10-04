# cap-evolve — notes for Claude Code sessions

## Benchmark CI: which model provider to use

Benchmark runs reach models through three IBM providers. Use them in this order:

1. **RITS** (`ibm-rits/…`): no budget. Use it whenever it serves the model.
2. **ETE-INT** (`ibm-ete-int/…`): the team's main gateway.
3. **ETE** (`ibm-ete/…`): a second gateway with its own budget. Use it only when ETE-INT cannot
   serve the model or is over budget.

How to follow this:

- When you dispatch `benchmarks.yml`, pick a **plain model name** (`claude-opus-5`,
  `gemma-4-31B-it`, …). CI then applies the order above by itself, before the run starts.
- Pick a prefixed id (`ibm-ete/aws/claude-opus-5`) only when an experiment must stay on one
  gateway, and say why in the issue or PR.
- The order and the model list live in `ci/benchmarks/model_catalog.txt`. Read its header
  before you add a model: list two ids under one name only when they are the same model.
- After a run, the job summary and the run record (`agent_provider`, `optimizer_provider`,
  `*_provider_skipped`) show which provider was used. Report spend per provider from these.

Details: `ci/benchmarks/README.md`, section "Model providers and their order".
