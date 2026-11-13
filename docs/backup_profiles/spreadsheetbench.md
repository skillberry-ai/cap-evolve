# Backup profile: `spreadsheetbench` — `benchmarks/spreadsheetbench/template`; CI `spreadsheetbench`

Shared values from core: [`_core.md`](_core.md). Format and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: see [`INDEX.md`](INDEX.md).

| Key | Value |
|---|---|
| Reward | `SPREADSHEETBENCH_SCORING` (soft / hard) × `REWARD_RECALC`; name in `runmeta.reward_metric`. Success: hard = 1. Group metric: hard vs soft over the 3 cases (912/200 only); `instruction_type`. |
| Infra rule | published (exp895 campaign): infra retried, never scored 0, candidate errors score 0. Core: drop. Detector: `metadata.error_kind`. |
| Telemetry | `tokens` (sum over turns); steps from the `trace`; no latency or termination. Campaign: phase totals in `results/usage.json` (`phase_total`). |
| Cost | agent: litellm `response_cost` (`zero_means: unknown`). |
| Splits | smoke: fit; pilot 5/50/5; full 182/91/639; full_verified 80/40/280 (`split_source.json`). |
| Baselines | seed, `no_skill`, `warm_seed` (`seed_capability_warm`), empty seed (`SB_EMPTY_SEED`), reused-from-slot (`SB_REUSE_LATEST_BASELINE`). Find which from the seed snapshot, not from runmeta. |
| Gold | `<DATA>/spreadsheet/<id>/*_answer.xlsx`, `*golden.xlsx` in `~/.cache/capevolve-ci/spreadsheetbench-data/`; `third_party/spreadsheetbench/evaluation/`. |
| Isolation | none for the optimizer. |
| Agent evidence | gold-free agent view; `$OUT/gold_separate_from_agent_mount`. |
| External state | the data cache; kept slot `~/.cache/capevolve-latest/spreadsheetbench-slots/` (**volatile**, overwritten); `outputs/*.xlsx`; Docker executor. |
| Sources | `skillberry-runs/spreadsheetbench` (= `spreadsheet-history`): 11 systems × 3 seeds, each `results/<system>/s<k>/{search,test}`. Raw data stated at `cap-evolve-archive/spreadsheetbench-exp895/` (not found in any repo or on this host on 2026-11-11). Cluster workareas named in `run_meta.txt`. |
| Reproduce | data fetched from raw `main` (unpinned; hash the tree); harness @ `0d9dc14`; `recipes/<system>/` from the results repo. |
| Licence | CC BY-SA 4.0 (data); split ids MIT. |
| Secrets | `.env`. |
