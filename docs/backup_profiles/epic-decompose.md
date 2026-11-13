# Backup profile: `epic-decompose` — retired; no adapter in any cap-evolve branch

Shared values: [`_core.md`](_core.md). Format, and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: [`INDEX.md`](INDEX.md).

Epic decomposition into sub-epics, by a GLM 5.3 agent, scored by checks and a judge.

| Key | Value |
|---|---|
| Bench names | `epic-decompose`; experiment `epic-glm53-v5`; settings: none |
| Code | `unverified`: no adapter in any cap-evolve branch. `may_exist_at`: `/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/project/` and the ACE repo on the owner's machine |
| Reward | checks plus a judge (record note "judge overflow fixed in this run"); test n = 10. Success: reward = 1 (`unverified`) |
| Infra rule | as `_core.md` |
| Telemetry | as `epic-creator` |
| Cost | as `epic-creator`; judge: `unverified`. The optimizer hit GLM 5.3's 275k context limit (record): a C4 truncation item |
| Splits | `unverified`: no `splits.json` in the git copy; test n = 10 |
| Baselines | seed |
| Capability | skill package `epic-decompose/SKILL.md` with `prompts/{decompose,fetch,review}-agent.md` |
| Gold | as `epic-creator` |
| Isolation | as `epic-creator` |
| Agent evidence | as `epic-creator` |
| Models as used | as `epic-creator` |
| External state | the run dir `/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_epic-glm53-v5/` on the owner's machine (`may_exist_at`) |
| Sources | `benchmark-history` `runs/202__full-epic-decompose/` (`candidates/`, `work/`, `rollouts/`, `ui/`, `epic-run/`; no `state.json` or `final.json`) and `records/202__full-epic-decompose.json` (author `avalappi`); ledgers: the PriceTag gateway (`may_exist_at`) |
| Reproduce | as `epic-creator` |
| Licence | not recorded |
| Secrets | as `_core.md` |
