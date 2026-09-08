# Parsec Intake v2

Sibling to `parsec-intake_v1`. See v1's PROJECT.md for shared history.

## Delta vs v1

1. **Task set**: 10 new authored `bench-aap2-*` tasks under
   `/Users/boazc/workarea/Python/rhdp-parsec/tasks_v2/` — each ships its own
   `seed.json` (correlated with its assertions). Uses `bench/v2` verifier schema.
2. **Simulator isolation**: one kaegis process per task, seeded from that task's
   `seed.json`. Never shared. See `scripts/start-sims-v2.sh`.
3. **Only aap2**: all 10 tasks call `query_aap2` only. github / babylon /
   provisions_db sims are not needed for this baseline.

## First deliverable

Baseline mean/stdev over the 10 v2 tasks with the unchanged v1 SKILL.md, for
comparison against v1's 0.240 mean (on a different task set — the numbers are
not directly comparable, but the distribution shape is).
