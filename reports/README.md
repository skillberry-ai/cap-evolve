# reports/ — per-task reports (level 3)

One file per task answering: **what did we change, what worked, what didn't, and what can we
(or can't) learn from this task.** These are the bottom level of a three-level drill-down:

| level | what | where |
|---|---|---|
| 1 | headline numbers for the whole sweep, next to other benchmarks | the `task-by-task` row on the dashboard (`benchmark-history`) |
| 2 | per-task scores across candidates, as a heatmap | [`ui/heatmap.html`](../ui/heatmap.html) |
| **3** | **why a task moved, and what it teaches** | **`reports/task-by-task/<task>.md`** |

When a task's story outgrows one file — it needs journals, diffs, run reports, or side-by-side
run comparison — it graduates to a full bundle in [`evidence/`](../evidence/), and its report
becomes the short version plus a pointer. [`shock-analysis-demand`](task-by-task/shock-analysis-demand.md)
is the worked example of that split.

## The auto block

Each report opens with a block delimited by `<!-- BEGIN:auto -->` / `<!-- END:auto -->`. That
block is **generated** from `results/results.json` and `artifacts/task-by-task/MANIFEST.json` by
[`scripts/build_task_reports.py`](../scripts/build_task_reports.py) — status, category, source
run, the candidate score table, and links to whatever material exists for that task.

Everything below the block is hand-written and the script never touches it. So:

```bash
python3 scripts/build_task_reports.py           # create missing reports, refresh auto blocks
python3 scripts/build_task_reports.py --check    # exit 1 if any auto block is stale (CI-friendly)
python3 scripts/build_task_reports.py --stats     # coverage: how many reports, how many analysed
```

**Do not hand-edit inside the auto block** — edits there are overwritten on the next run. This
split exists because transcribed numbers drift: it is what produced the heatmap's 63/87-vs-64/87
disagreement and `summary.md`'s wrong 0.825 mean best. Numbers stay derived; narrative stays human.

## Status

87 reports, one per task. Not all are written — and that is deliberate rather than pending:

- **21 tasks were already at 1.0 on seed.** Their report says so and stops. There is nothing to
  learn about the optimizer from a task it never got to touch, and padding these would be inventing
  content.
- **4 of the 10 NO_SIGNAL tasks are infrastructure failures** (the container built, the agent
  recorded no `tool_calls`). Their 0.0 is an absence of measurement, not a measurement of failure,
  and their reports say that. The infra-vs-genuine split is transcribed from
  [`results/task-by-task-87/summary.md`](../results/task-by-task-87/summary.md) — it cannot be
  derived from the data, and it must not be inferred from `MANIFEST` run-dir names
  (`seismic-phase-picking` is an infra failure whose run dir says `DONE`).
- **3 are written as worked exemplars** — see below.
- **The rest carry `_Not yet analysed._`** markers. Filling them in is ordinary follow-on work;
  the 52 tasks with a `best/PROCESS.md` have most of the raw material already written by the
  optimizer itself.

Run `--stats` for the current count.

## Where the material comes from

| source | covers | what it gives |
|---|---|---|
| `results/results.json` | 87/87 | per-candidate val rewards, status, held-out test, delta |
| `artifacts/task-by-task/MANIFEST.json` | 87/87 | originating run dir, best candidate id, iteration count |
| `artifacts/task-by-task/<task>/seed/` | 87/87 | the seed skill package |
| `artifacts/task-by-task/<task>/best/PROCESS.md` | **52/87** | the optimizer's own write-up: per-trial ground truth, ranked failure clusters with root causes, the kept edit, and what it deliberately skipped |
| `artifacts/task-by-task/<task>/best/` | 52/87 | the winning skill package — diff against `seed/` to see the change |
| `results/task-by-task-43/per-task-logs/<task>.md` | 43/87 | per-trial reward vectors, from the earlier 43-task sweep |
| `evidence/<task>*/` | 2/87 | full bundle: journals, diffs, run reports |

`best/PROCESS.md` is the highest-value input and the reason these reports are mostly
consolidation rather than fresh analysis. `best/INSTRUCTIONS.md` also exists for those 52 tasks
but is near-identical boilerplate across all of them — low value, skip it.

## Two cautions when writing one

**Say which run a number came from.** Several tasks were run more than once, and the numbers
differ a lot. `shock-analysis-supply` has best-val of 0.9, 0.3 and 0.667 across three runs, and
`results.json` records the lowest. The 43-task per-task-logs are a *different run* from the
87-task sweep, so their numbers will legitimately disagree with the auto block above them.

**A rejected candidate is not a regression.** A rejected candidate reverts to the champion, so a
low score on a later candidate does not undo an earlier accepted fix. A candidate sequence reading
`0.667, 0.4, 0.0, 0.0` is one accepted fix followed by three reverted experiments — not decay. The
`best` column is the one that means anything.

## Exemplars

Three reports are written out in full, chosen because each shows a different thing:

- **[`shock-analysis-supply`](task-by-task/shock-analysis-supply.md)** — run-to-run variance.
  Three runs, best-val 0.9 / 0.3 / 0.667, with the recorded number being the worst. Also the
  clearest instance of "a read-but-ignored instruction needs an executable gate, not better
  wording," and of the optimizer correctly *refusing* to re-attempt a refuted lever.
- **[`flink-query`](task-by-task/flink-query.md)** — a real, oracle-verified fix found once
  (0.9) and lost on re-run (0.2), where the re-run pulled the same wrong lever five times.
- **[`shock-analysis-demand`](task-by-task/shock-analysis-demand.md)** — the same lost-fix
  pattern with the mechanism *proven*: the re-run's seed is diffed against the prior run's
  winning skill to show the fix was never merged back. Pairs with its
  [evidence bundle](../evidence/shock-analysis-demand-optimizer-regression/).
