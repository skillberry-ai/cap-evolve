# Backup profile: `epic-decompose` (retired) — no adapter in any cap-evolve branch

Shared values from core: [`_core.md`](_core.md). Format and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: see [`INDEX.md`](INDEX.md).

As `epic-creator` ([`epic-creator.md`](epic-creator.md)), except:

| Key | Value |
|---|---|
| Bench names | `epic-decompose`; experiment `epic-glm53-v5`. |
| Run | `benchmark-history/runs/202__full-epic-decompose/`: `candidates/`, `work/`, `rollouts/`, `ui/`, `epic-run/` (candidate skills `epic-decompose/SKILL.md` with `prompts/{decompose,fetch,review}-agent.md`). Made on `/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_epic-glm53-v5`. No `state.json` or `final.json` in the git copy. |
| Reward | checks plus a judge ("judge overflow fixed in this run", record note). Test n = 10. |
| Cost | as [`epic-creator.md`](epic-creator.md). The record notes the optimizer hit GLM 5.3's 275k context limit: a C4 (truncation) item. |
