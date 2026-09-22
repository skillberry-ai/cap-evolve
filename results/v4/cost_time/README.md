# results/v4/cost_time/ — T2's per-task cost and time

The cost/token/wall-clock accounting for **T2** (task-by-task optimization, `v4_t2_e1`), covering the
21 of 34 v4 tasks T2 actually ran on. Vendored verbatim from `parsec-intake_v4/.capevolve/` — not
retyped — in two byte-identical forms:

- [`v4_t2_e1_results_table.md`](v4_t2_e1_results_table.md) — the file
  [`scripts/build_v4_results_json.py`](../../../scripts/build_v4_results_json.py) parses to populate
  `results.json`'s `task_ledger` (`t2_*` fields) and `sections.task.cost_time`.
- `v4_t2_e1_results_table.xlsx` — the same two tables as a spreadsheet, kept for direct spreadsheet
  use. Confirmed identical data to the `.md` (same row counts per sheet, same task order); the
  generator reads the `.md` only.

## What's in the `.md`

Two tables, described in full at its own top:

1. **Summary** — one row per task: seed/iteration val scores with accept/reject, best candidate,
   held-out test reward vs. test baseline, delta, and **total Cost($)/Tokens** for that task's whole
   T2 run.
2. **Per-iteration detail** — one row per eval inside a task (`seed`, each `iterN(cand_000N)`,
   `FINAL`, `FINAL_seed`), splitting cost/tokens/seconds into the runner's **eval** cost vs. the
   **optimizer's own** cost of proposing that candidate. Summing a task's eval+opt cost across all its
   rows reproduces the Summary table's Cost($) for that task (verified to the cent); summing tokens
   reproduces it exactly. `build_v4_results_json.py` re-verifies this on every run and fails loudly if
   a future edit to the source table breaks the identity.

## Where the numbers end up

- `results/v4/results.json` — `task_ledger[].t2_cost_usd` / `t2_tokens` / `t2_time_s` (eval+opt
  totals) and `t2_eval_*` / `t2_opt_*` (the split), `null` for the 13 tasks T2 never targeted;
  `sections.task.cost_time` for the tranche-segmented aggregate.
- `results/v4/summary.md` — the "Cost + wall clock" narrative section.
- `reports/task-by-task/v4/*.md` — one added line per optimized task's auto block.

## Caveat this table carries forward

Tasks 13-15 (`platform-005-wrong-owner-trap`, `platform-007-directory-path-fetch`,
`platform-008-log-does-not-say`) each had a run interrupted by an unrelated infrastructure issue
(a team LLM API budget cap, since fixed) on 2026-09-20 and were re-run — see
[`../../../artifacts/README.md`](../../../artifacts/README.md)'s "v4's three multi-run tasks"
section and `results/v4/summary.md`'s data-quality caveats. The numbers here are from whichever of
each task's two runs `results.json` actually reports (the best held-out `test_reward`, not simply
the latest run) — the source `.md`'s own footnote says which run that is for each of the three.
