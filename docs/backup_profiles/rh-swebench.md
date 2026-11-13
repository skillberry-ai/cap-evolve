# Backup profile: `rh-swebench` — retired; Harbor on SWE-bench Verified

Shared values: [`_core.md`](_core.md). Format, and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: [`INDEX.md`](INDEX.md).

cap-evolve optimizing a Claude Code coding agent on 119 SWE-bench Verified tasks through Harbor. Values not listed here are as `swebench-verified-harbor`.

| Key | Value |
|---|---|
| Bench names | `rh-swebench`, `rh-swebench-v4`; runs `manual__full-rh-swebench-v4`, `manual__full-rh-swebench-v4__full-rh-swebench`; settings: `v4` |
| Code | as `swebench-verified-harbor`, at the run's commit (`unverified`: the commit is not in the record) |
| Reward | resolved, on 119 SWE-bench Verified tasks; the published result is val, a fit metric (0.580 → 0.765, branch `results/rh-swe-bench-image-and-reorder` README). Success: resolved |
| Infra rule | as `swebench-verified-harbor` |
| Telemetry | as `swebench-verified-harbor` |
| Cost | the record's `eval_usd` 0 is unknown, not $0 (`zero_means: unknown`); optimizer $60.75 (record) |
| Splits | 119 tasks; val only (fit) |
| Baselines | seed |
| Capability | skill package + system prompt |
| Gold | as `swebench-verified-harbor` |
| Isolation | as `swebench-verified-harbor` |
| Agent evidence | as `swebench-verified-harbor` |
| Models as used | agent `claude-sonnet-4-6`, optimizer `claude-opus-4-6` (record): confirm from trajectories |
| External state | the full run dir and Harbor job dirs on the owner's machine (`may_exist_at`) |
| Sources | `benchmark-history` `runs/manual__full-rh-swebench-v4/ui`, `runs/manual__full-rh-swebench-v4__full-rh-swebench/ui` (incl. `compare_ids_*`), `records/manual__full-rh-swebench-v4.json` (author `avalappi`); branch `results/rh-swe-bench-image-and-reorder` (`site/results.html`, `site/assets/rh_swe_bench.png`, `README.md`); ledgers: as `_core.md` |
| Reproduce | as `swebench-verified-harbor`; the RH SWE-bench image (named on the results branch): its digest |
| Licence | as `swebench-verified-harbor` |
| Secrets | as `_core.md` |
