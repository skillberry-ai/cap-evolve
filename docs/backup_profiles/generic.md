# Backup profile: `generic` — `benchmarks/generic/{jsonl_litellm,huggingface_litellm}/template` (ids `generic-jsonl`, `generic-hf`)

Shared values: [`_core.md`](_core.md). Format, and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: [`INDEX.md`](INDEX.md).

A system prompt over user-supplied tasks (a JSONL file, or a HuggingFace dataset), with one litellm call per task.

| Key | Value |
|---|---|
| Bench names | `jsonl_litellm` → `generic-jsonl`; `huggingface_litellm` → `generic-hf`; settings: `SCORING` (`exact`, `contains`, `regex`) |
| Code | `benchmarks/generic/jsonl_litellm/template/` (`adapter.py`, `capevolve.yaml`, `tasks.jsonl`, `seed_capability/`), `benchmarks/generic/huggingface_litellm/template/` (same); `benchmarks/_shared/model_config.py` (must be copied next to the adapter) |
| Reward | `SCORING` exact / contains / regex against the target: binary. Success: reward = 1. Group metric: `not applicable: no grouping` |
| Infra rule | as `_core.md` (an LLM error sets `Rollout.error`) |
| Telemetry | tokens: litellm `usage.total_tokens`; latency, steps, termination: `not-produced` |
| Cost | agent: litellm `response_cost`, 0 when unpriced (`zero_means: unknown`) |
| Splits | core ratios (0.5 / 0.25 / 0.25 by default); HF: `HF_SPLIT` (default `test`) is re-split by core: name both; HF ids default to `<HF_SPLIT>-<i>` (unstable across revisions) |
| Baselines | seed |
| Capability | system prompt |
| Gold | jsonl: the `target` field of `TASKS_FILE`; HF: `TARGET_FIELD` (default `answer`). Feedback quotes the output, not the target |
| Isolation | none |
| Agent evidence | not applicable: one litellm call |
| Models as used | rollout `metadata.model` |
| External state | `TASKS_FILE` (any path); HF cache `~/.cache/huggingface/datasets/` |
| Sources | the local project only |
| Reproduce | data: copy `TASKS_FILE`, or snapshot the HF dataset with its fingerprint (no `revision=` pin); unpinnable: the model endpoint |
| Licence | user data, or the HF dataset card: `unverified` until read |
| Secrets | provider keys in `.env` (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, …) |
