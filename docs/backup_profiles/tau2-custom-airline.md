# Backup profile: `tau2-custom-airline` — retired; code at `5e570d29f^:examples/tau2_custom/{direct,blackbox}`

Shared values: [`_core.md`](_core.md). Format, and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: [`INDEX.md`](INDEX.md).

tau2 airline on the `skillberry-benchmarks` fork of tau2, with a direct and a blackbox arm.

| Key | Value |
|---|---|
| Bench names | `tau2_custom_direct`, `tau2_custom_blackbox`, `tau2_custom_spa`, `skillberry_tau2_direct`, `skillberry_tau2_spa`, `spa`; `spa` and `blackbox` name the same arm; settings: `direct`, `blackbox` |
| Code | `5e570d29f^:examples/tau2_custom/` (`PROMPT.md`, `{direct,blackbox}/adapters/{adapter.py,gateway.py}`, `capevolve*.yaml`, `optimizer/INSTRUCTIONS.md`, `setup.sh`, `run.sh`, split files, `seed_capability/`); CI tiers `8860d243a^:ci/benchmarks/tau2_custom/{direct,blackbox}/{smoke,full,integration}/` |
| Reward | as `tau2-airline` |
| Infra rule | as `tau2-airline` |
| Telemetry | as `tau2-sierra-airline` |
| Cost | as `tau2-sierra-airline` |
| Splits | `split_ids.json` 25 / 12 / 13 (seeded 0.5 / 0.25 / 0.25 over the 50 airline tasks); `smoke_split.json`; `split_ids_task9.json`; CI smoke: 10 tasks |
| Baselines | seed |
| Capability | direct: tools (`tools/tools.py`, with read-only `reference/`); blackbox: the store skill `my_skill` + `primitive_tools/` |
| Gold | `runner_repo_path: ../../vendor/skillberry-benchmarks` (task definitions and reward checks, readable by design for train/val, as `tau2-sierra-airline`). Forbidden: test ids |
| Isolation | none |
| Agent evidence | as `tau2-sierra-airline` |
| Models as used | native results `info.*.llm`; the yaml says optimizer `claude-opus-4-6`, the CI records say `claude-opus-4-8` (a B2 item) |
| External state | `vendor/skillberry-benchmarks` (at `BENCH_REF`; `setup.sh` prints `BENCH_SHA`); `native_sims/`; blackbox services and `/tmp` logs as `tau2-sierra-airline` |
| Sources | `benchmark-history` `records/*tau2_custom*`, `records/*skillberry_tau2*`, `runs/*tau2_custom*/ui`, `runs/*skillberry_tau2*/ui`, `live/<run_id>__<tier>-<bench>/data/` (live-monitor snapshots); branches `ci_skillberry_benchmarks_tau2`, `ci_skillberry_benchmarks_tau2_2`, `ci_skillberry_benchmarks_tau2_2_intervention`, `ci_skillberry_benchmarks_tau2_2_intervention_review`, `rename_intervention_spa_to_blackbox`, `remove_ci_all`, `blackbox_require_make`; CI artifacts of those workflow runs (if not expired); owners: each run's triggering actor; ledgers: as `_core.md` |
| Reproduce | code at the run's `runmeta.sha`; `skillberry-ai/skillberry-benchmarks` at `BENCH_SHA`; store and SPA SHAs as `tau2-sierra-airline`; unpinnable: gateway backends |
| Licence | `unverified`: read from the `skillberry-benchmarks` clone |
| Secrets | as `tau2-sierra-airline` |
