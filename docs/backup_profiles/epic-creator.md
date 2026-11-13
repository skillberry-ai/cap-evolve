# Backup profile: `epic-creator` — retired; no adapter in any cap-evolve branch

Shared values: [`_core.md`](_core.md). Format, and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: [`INDEX.md`](INDEX.md).

Epic creation from intake documents, by a GLM 5.3 agent in a Claude Code harness, scored by deterministic checks.

| Key | Value |
|---|---|
| Bench names | `epic-creator`; experiment `epic-intake-v1`; settings: none |
| Code | `unverified`: no adapter in any cap-evolve branch. `may_exist_at`: the owner's project `/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/project/` and the ACE repo on the owner's machine |
| Reward | per case `score.raw.verdicts`: deterministic checks (`budget_check`, `artifact_contract`, `dag_valid`, `implementation_type_rules`, `mandated_acceptance_criteria`, `run_report_consistent`, `review_discipline`, …) combined into a reward in [0, 1] (`unverified`: the combination rule is in the adapter). Success: reward = 1. Group metric: pass rate per check |
| Infra rule | as `_core.md` |
| Telemetry | tokens: `not_recorded` (0); latency, steps, termination: `not-produced`; rollout `metadata.{segments, exit_code, seed}` |
| Cost | agent: `Rollout.cost_usd` (`reported`, per-case cap $40); optimizer: `state.json` `spent.optimizer_usd`; judge: `unverified` |
| Splits | the run's `splits.json`; test n = 21 |
| Baselines | seed |
| Capability | skill package |
| Gold | `unverified`: the cases' expected artifacts and review criteria live in the adapter's project |
| Isolation | `unverified`: none known |
| Agent evidence | `unverified` |
| Models as used | agent GLM 5.3 (Claude Code harness), optimizer GLM 5.3 via the PriceTag AI Gateway (record): confirm from transcripts |
| External state | the run dir `/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_epic-intake-v1/` and its project, on the owner's machine (`may_exist_at`) |
| Sources | `benchmark-history` `runs/203__full-epic-creator/` (`baseline.json`, `final.json`, `state.json`, `report.md`, `dashboard.html`, `candidates/`, `work/`, `rollouts/`, `ui/`) and `records/203__full-epic-creator.json` (author `avalappi`); no transcripts in git; ledgers: the PriceTag gateway (`may_exist_at`) |
| Reproduce | adapter and project: a gap until found; unpinnable: agent and optimizer endpoints |
| Licence | not recorded |
| Secrets | as `_core.md` |
