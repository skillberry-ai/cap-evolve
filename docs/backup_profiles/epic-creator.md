# Backup profile: `epic-creator` (retired) — no adapter in any cap-evolve branch

Shared values from core: [`_core.md`](_core.md). Format and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: see [`INDEX.md`](INDEX.md).

| Key | Value |
|---|---|
| Bench names | `epic-creator`; experiment `epic-intake-v1`. |
| Run | `benchmark-history/runs/203__full-epic-creator/`: `baseline.json`, `final.json`, `state.json`, `report.md`, `candidates/`, `work/`, `rollouts/`, `ui/`. Made on `/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_epic-intake-v1`. Owner: `avalappi`. |
| Reward | per case `score.raw.verdicts`: deterministic checks (`budget_check`, `artifact_contract`, `dag_valid`, `implementation_type_rules`, `mandated_acceptance_criteria`, `run_report_consistent`, `review_discipline`, …), combined into a reward in [0, 1]. Success: reward = 1. Group metric: per check (pass rate of each verdict). The first backup confirms the combination rule from the adapter. |
| Infra rule | published: drop (core default). |
| Telemetry | `cost_usd` per rollout; `tokens` = 0 (`not_recorded`); `metadata.{segments, exit_code, seed}`. |
| Cost | agent: `cost_usd`, CLI-reported (the agent is GLM 5.3 in a Claude Code harness; budget cap $40 per case). Optimizer: `state.json` `spent.optimizer_usd`. A judge, if one is used: not recorded (`aux_call` null). |
| Splits | `splits.json` in the run; test n = 21. |
| Baselines | seed |
| Capability | skill package |
| Gold | the test cases' expected artifacts and review criteria. **Location unknown**: in the adapter's project, which is not in the repo. |
| Isolation | none known |
| Models as used | agent GLM 5.3 (Claude Code harness); optimizer GLM 5.3 via the PriceTag AI Gateway (record). Confirm from transcripts. |
| External state, sources | the run dir and project on the owner's machine (`may_exist_at`: the path above, and the ACE repo); `benchmark-history` record `203__full-epic-creator`. The git copy has rollouts but no transcripts or adapter, so expect `partial-export`. |
| Reproduce | adapter and project code: gap until found. Agent and optimizer endpoints are unpinnable. |
| Licence | not recorded |
