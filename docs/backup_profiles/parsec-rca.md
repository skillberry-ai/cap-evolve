# Backup profile: `parsec-rca` — `benchmarks/parsec/examples/rca_prompts`; CI `parsec`

Shared values from core: [`_core.md`](_core.md). Format and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: see [`INDEX.md`](INDEX.md).

| Key | Value |
|---|---|
| Reward | Harbor verifier `reward.json` (partial credit in [0, 1]: tool calls and answer, with a completion gate). Success: reward = 1.0 (convention). Group metric: per category. |
| Infra rule | published: drop. Detector: `_agent_failure` (dead agent). |
| Telemetry | `tokens` and `cost_usd` from parsec-live `usage` log lines; time window in `metadata.parsec_usage_window`. |
| Cost | agent: log-derived, 0 if the log is missing (`zero_means: unknown`). **Simulator LLMs:** not recorded (`aux_call` null). Merger (v6_t4): optimizer cost. |
| Splits | v6: pooled F / C / test (sealed dir). v4_t2_e1, h4, v6_t2: no holdout. |
| Baselines | seed |
| Gold | `<tree>/_run/tasks/*/tests/{verify.py,expected.json}`; trial `verifier/reward-detail.json`. Allowed: F-split verifier output. Forbidden: C / test material and `expected.json`. |
| Isolation | none |
| External state | `$PARSEC_V*N/_run/`: `jobs/`, `logs/sims/parsec-live.log` (**the cost source**), `h4-lanes/`, `v6-queue/`; `<proj>.sealed/`; the podman image. |
| Sources | cluster LSF logs (`$CCC_LOGS`); `skillberry-runs/parsec` (= `parsec-history`); `records/parsec-v6-g2-and-tmrg` (unmerged; two records whose content differs from the `benchmark-history` versions: archive both). |
| Reproduce | code commit **before `aeee7126d`**; private task bundles (MD5s in `build_v6_tree.py`); the podman image tar. |
| Licence | private; none stated. |
| Secrets | `config.local.yaml` LiteLLM key; `LLM_API_KEY`. |
