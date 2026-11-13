# Backup profile: `swebench-lite` — `benchmarks/swe_bench/template` (local only)

Shared values from core: [`_core.md`](_core.md). Format and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: see [`INDEX.md`](INDEX.md).

| Key | Value |
|---|---|
| Reward | resolved: binary. Success: resolved. Group metric: per `metadata.repo`. |
| Infra rule | published: drop. Detectors: `error_ids`, `incomplete_ids`, missing report (`raw.errored`). |
| Telemetry | `tokens`, `cost_usd`; single step; no latency or termination. |
| Cost | agent: litellm (`zero_means: unknown`). |
| Splits | core ratios 0.34 / 0.33 / 0.33 over HF `princeton-nlp/SWE-bench_Lite` test. |
| Baselines | seed |
| Gold | HF fields `patch`, `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`; `_oracle` dataset. `SWEBENCH_ORACLE=1` puts gold-derived text into `Task.input`: disclose it. |
| Isolation | none |
| External state | HF cache; Docker images `sweb.*` (built locally). |
| Reproduce | dataset snapshot and fingerprint; `swebench` package version; images saved. |
| Licence | code MIT; dataset licence unstated. |
