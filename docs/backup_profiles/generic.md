# Backup profile: `generic-jsonl`, `generic-hf` — `benchmarks/generic/{jsonl_litellm,huggingface_litellm}/template`

Shared values from core: [`_core.md`](_core.md). Format and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: see [`INDEX.md`](INDEX.md).

| Key | Value |
|---|---|
| Reward | exact / contains / regex: binary. |
| Cost | litellm `response_cost`, 0 when unpriced (`zero_means: unknown`). |
| Telemetry | `tokens` only. |
| Splits | core ratios. For HF, `HF_SPLIT` (default `test`) is re-split by core: name both. |
| Gold | the `target` field (`TASKS_FILE`, or `TARGET_FIELD`). |
| External state | the HF cache. |
| Reproduce | dataset revision is not pinned: snapshot the dataset with its fingerprint. |
| Licence | user data, or the dataset card. |
