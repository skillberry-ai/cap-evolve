# Ablation switches (optimizer_config.py)

Set `optimizer.ablation.<name>: true|false` in capevolve.yaml, or env `CAPEVOLVE_<NAME>` (env wins).
Unknown keys and non-booleans raise.

| switch | default | off = |
| --- | --- | --- |
| dag_parallel | on | single parent (best_id), serial |
| active_eval | OFF | `probe --auto` means full val; no posterior allocator |
| smart_merge | on | `merge` refuses; use merge_search.py |
| cost_gating | on | paired gate instead of reward_gated |
| failure_clustering | on | per-task listing, no >= 2-task hypothesis rule |
| pregate | on | pre-gate skipped |
| context_digest | on | digest prints raw numbers, no suggestions |

All off = legacy mode (references/legacy.md). The new engine is dag_parallel AND active_eval: it drops the
mandatory null control and the 3-sibling minimum.
