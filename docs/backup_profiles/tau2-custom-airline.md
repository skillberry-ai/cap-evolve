# Backup profile: `tau2-custom-airline` (retired) — code at `5e570d29f^:examples/tau2_custom/{direct,blackbox}`

Shared values from core: [`_core.md`](_core.md). Format and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: see [`INDEX.md`](INDEX.md).

tau2 airline on the `skillberry-benchmarks` fork of tau2, with the `direct` and `blackbox` arms. Code:
`5e570d29f^:examples/tau2_custom/`. CI tiers: `8860d243a^:ci/benchmarks/tau2_custom/`.

| Key | Value |
|---|---|
| Bench names | `tau2_custom_direct`, `tau2_custom_blackbox`, `tau2_custom_spa`, `skillberry_tau2_direct`, `skillberry_tau2_spa`. `spa` and `blackbox` name the same arm. `<setting>` = the arm, `direct` or `blackbox`. |
| Reward | as `tau2-airline` (tau2 reward, binary per trial; pass^k). |
| Infra rule | as `tau2-airline`. |
| Telemetry, cost | as `tau2-sierra-airline`; the blackbox arm's agent cost is not measured. |
| Splits | `split_ids.json` 25 / 12 / 13 (seeded 0.5 / 0.25 / 0.25 over the 50 airline tasks); `smoke_split.json`; `split_ids_task9.json`. CI smoke: 10 tasks. |
| Baselines | seed |
| Capability | `tools` (the agent's tool surface); blackbox: the store skill `my_skill` + `primitive_tools/`. |
| Gold | `runner_repo_path: ../../vendor/skillberry-benchmarks` (tau2 fork): task definitions and reward checks are readable by the optimizer (allowed by design for train/val, as in [`tau2-sierra-airline.md`](tau2-sierra-airline.md)). Forbidden: test ids. |
| Isolation | none |
| Models as used | native results `info.*.llm`. The yaml says optimizer `claude-opus-4-6`; the CI records say `claude-opus-4-8`: a B2 item. |
| External state | `vendor/skillberry-benchmarks` (at `BENCH_REF`, recorded as `BENCH_SHA` by `setup.sh`), blackbox services as in [`tau2-sierra-airline.md`](tau2-sierra-airline.md). |
| Sources | `benchmark-history` `records/*tau2_custom*`, `*skillberry_tau2*`; `runs/*/ui`; `live/<run_id>__<tier>-<bench>/data` (live-monitor snapshots, partial exports); branches `ci_skillberry_benchmarks_tau2*`, `rename_intervention_spa_to_blackbox`, `remove_ci_all`, `blackbox_require_make`. All are CI runs, so the owner is the workflow's triggering actor. |
| Reproduce | the code commit of the run (`runmeta.sha`); `skillberry-ai/skillberry-benchmarks` at `BENCH_SHA`; store and SPA SHAs as in [`tau2-sierra-airline.md`](tau2-sierra-airline.md). |
| Licence | not recorded |
| Secrets | as [`tau2-sierra-airline.md`](tau2-sierra-airline.md). |

`tau2_blackbox` (branch `tau2_vanilla_blackbox`; CI tier at `8860d243a^:ci/benchmarks/tau2_blackbox`)
is the blackbox arm on **vanilla** tau2, with tailoring applied from outside. It is
profiled as `tau2-sierra-airline`, setting `blackbox`.
