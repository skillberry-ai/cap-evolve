# reports/ — per-task reports (level 3)

One file per task answering: **what did we change, what worked, what didn't, and what can we
(or can't) learn from this task.** These are the bottom level of a three-level drill-down:

| level | what | where |
|---|---|---|
| 1 | headline numbers for the whole benchmark, next to other benchmarks | the `parsec` row on the dashboard (`benchmark-history`) |
| 2 | per-task scores across candidates and runs, as a heatmap | [`ui/heatmap.html`](../ui/heatmap.html) |
| **3** | **why a task moved, and what it teaches** | **`reports/task-by-task/<task>.md`** |

## Naming

Two experiments share one directory, so the experiment is part of the filename:

| experiment | pattern | count |
|---|---|--:|
| v1 (trace-extracted) | `v1-aap2-<NNNN>.md` | 30 |
| v2 (hand-authored) | `v2-<task>.md` | 10 |

v1's task ids are all of the form `traces_parsec-aap2-<NNNN>`, so the shared prefix is dropped
and only the number kept — `v1-aap2-0047.md`. v2's ids are already readable
(`bench-aap2-004-failing-task-and-host`) and are used whole. The mapping is not a convention to
re-derive by hand: every task row in `results/results.json` carries a `report` field with the exact
path, and [`scripts/build_task_reports.py`](../scripts/build_task_reports.py) reads it.

## The auto block

Each report opens with a block delimited by `<!-- BEGIN:auto -->` / `<!-- END:auto -->`. That block
is **generated** from `results/results.json` by
[`scripts/build_task_reports.py`](../scripts/build_task_reports.py) — status, experiment, category,
run, prompt, contract shape, flags, the measurement table, and links to whatever material exists for
that task.

Everything below the block is hand-written and the script never touches it.

```bash
python3 scripts/build_task_reports.py           # create missing reports, refresh auto blocks
python3 scripts/build_task_reports.py --check    # exit 1 if any auto block is stale (CI-friendly)
python3 scripts/build_task_reports.py --stats     # coverage: how many written, how many analysed
```

**Do not hand-edit inside the auto block** — edits there are overwritten on the next run.
Numbers stay derived; narrative stays human.

## Where this departs from `skillsbench-history`

The scheme is copied from `skillsbench-history`'s `reports/` and three things are deliberately
different, all for the same reason: parsec's measurements are **not** comparable across cells the way
skillsbench's were.

**1. The measurement table is vertical, not horizontal.** skillsbench-history renders one row per
task with a column per candidate, which is readable because every candidate there was measured at
the same trial count. Parsec's were not. v1's baseline sweep is `n=1` and its pilot is `n=30`; v2's
`seed` is a *reused* `n=3` measurement while everything else in that run is `n=9`. A horizontal row
would silently invite comparing an `n=3` number with an `n=9` number — which is exactly the mistake
that produced v2's headline. So each report lists one row per distinct measurement, with its `n` and
its split, and **omits rows for measurements that do not exist** rather than printing a null. The
length of the table is itself information: a 1-row table means the optimizer never ran on that task.

**2. Narrative is pre-filled for more classes.** skillsbench-history leaves most reports at
`_Not yet analysed._` and says so honestly, because for a task the optimizer improved, the story
needs a human reading of the diff. Here, 28 of the 30 v1 tasks were never seen by the optimizer at
all, and for those "what happened" genuinely *is* the contract plus one trial — which is derivable.
The generator pre-fills seven v1 classes (vacuous-assertion contract, solved-at-baseline,
trajectory-matched, capped-at-0.5, zero-at-baseline, partial-assertions, and gate-failed, the last
of which stays a placeholder because a gate failure needs a rollout read). This is not padding: each
pre-filled report states a task-specific, derived fact, and none of them claim an optimizer result
that does not exist.

**3. The "a rejected candidate is not a regression" caution is conditional.** skillsbench-history
prints it on every report. Here it appears only when a candidate was actually evaluated on that task
(`status == OPTIMIZED` and a `cand_0001` measurement exists) — otherwise it would be filler on 28 of
30 v1 reports and would train the reader to skip the italics. Note that once a report's hand section
is written, the author's own narrative supersedes it; the in-block caution *"Read no cell without the
`n` beside it"* is inside the auto block and therefore survives on all 40 reports regardless.

## Status

**40 reports, 40 fully analysed, 0 placeholders.** Run `--stats` for the live count.

That is unusual for a first pass and it is worth saying why it was achievable: parsec's optimizer ran
on only 12 of the 40 tasks, so most reports are an account of a *contract* and a single trial rather
than of an optimization. The contracts are all committed here (`results/v1/tasks.json`,
`results/v2/tasks.json`), the per-trial vectors are committed
(`results/v{1,2}/per_task_scores.json`), and v2's ten scenarios each ship a hand-written
`provenance.md` in the source tree recording why the scenario exists and every defect fixed in it.
There was more written material per task than there were tasks to write about.

## Where the material comes from

| source | covers | what it gives |
|---|---|---|
| `results/results.json` | 40/40 | every number in every auto block: rewards per tag per split, `n`, errored-trial counts, contract shape, flags |
| `results/v1/tasks.json` | 30/30 | v1 contracts: the demanded tool-call sequence and every `answer_contains` string |
| `results/v2/tasks.json` | 10/10 | v2 contracts: expected calls, required/derived/forbidden facts, per-task weights |
| `results/v{1,2}/per_task_scores.json` | 40/40 | **per-trial reward vectors** for every task in every run, errored trials as `null` |
| `results/v2/per_task_scores.csv` | 10/40 | the hand-maintained per-task analysis, one note per task per iteration |
| `recipes/v1/PROJECT.md` | 30/40 | the dated decision log for v1 — including the simulator tool-coverage note that explains 25 of the 30 `trajectory: 0.000` rows |
| `results/v1/runs/run_20260814_214843/JOURNAL.md` | 2/40 | the optimizer's own hypotheses, refutations and next-lever notes — the single richest source for v1 |
| `results/v2/runs/*/JOURNAL.md` | 10/40 | same for v2, but see the caveat below |
| `<source>/harbor-tasks-v2.1/<task>/provenance.md` | 10/40 | why the scenario exists, its discrimination axis, and a dated edit log for every defect fixed |
| `artifacts/` | 40/40 | the skill packages themselves — diff `seed/` against `best/` and the rejected candidates |

**The v2 journal caveat:** the headline run's optimizer wrote **no handover at all** — its entry
reads `## Iteration cand_0001 — (no handover written by the optimizer)`, and `events.jsonl` records
an `optimizer_error` for that candidate. Six edits shipped together with no statement of intent, so
every per-task attribution in the v2 reports is inference from the reward decomposition, not from the
record. The iter-1 run (`run_20260816_202942`) *does* have a full journal entry and is the better
read for how the optimizer was reasoning.

## Four cautions when writing one

**Say which run and which `n` a number came from.** This branch's central finding is that the same
byte-identical seed skill measures anywhere from 0.000 to 0.367 in v1 and 0.643 to 1.000 in v2
depending only on the trial count and the run. A number without its `n` is not a result. The
`ui/heatmap.html` ladder table lists all 24 seed measurements side by side.

**Check `mean_valid` against `mean_all` before quoting.** Errored trials are written with
`reward: 0.0` and are distinguishable from genuine zeros only via `rollout.error`. Both denominators
are carried everywhere in the ledger. They differ materially: v2's headline `seed_train` is `0.822`
with errored trials dropped and `0.749` with them counted as zero. `results/v2/per_task_scores.csv`
uses the **errored-as-zero** convention, so its numbers legitimately disagree with the auto block
above them.

**On a v1 report, check the reachability line before reading `trajectory` as a skill measurement.**
When the 30-task sweep ran, two simulators were up and 25 of the 30 contracts demand a tool neither
served. Under a `subset` match one uncallable op fails the whole containment, so those 25 rows have
`trajectory: 0.000` by construction and a reward capped at 0.5 — a fact about the harness, not the
skill. Every affected report says so in its auto block and carries the
`trajectory-unreachable-tool-gap` flag; the ledger carries
`trajectory_tools_missing_at_baseline` per task. The two optimized tasks (`-0047`, `-0048`) are the
exception worth knowing: their baseline rows are flagged, but by the 2026-08-14 pilot the tool *had*
become callable, and their reports are the only record of that change.

**A rejected candidate is not a regression, and an accepted one is not necessarily an improvement.**
Both halves matter here. v1's `cand_0002` was rejected and is the only artifact that ever produced a
trajectory match on either of the two tasks it ran on. v2's accepted `cand_0001` is recorded as
having *broken* two tasks, and at equal `n` one of them is flat to six decimal places and the other
improved by `+0.133`. Re-derive per-task verdicts from `seed_train` rather than reading them off
`report.md`.

## Worked examples

Four reports carry the most, and are the best entry points:

- **[`v1-aap2-0047`](task-by-task/v1-aap2-0047.md)** and
  **[`v1-aap2-0048`](task-by-task/v1-aap2-0048.md)** — the only two tasks v1's optimizer ever ran on.
  Two candidates, both rejected, and between them the only two trajectory matches ever recorded in
  the whole experiment. The case that a mean-based gate made the right call for the champion and the
  wrong call for the knowledge.
- **[`v2-bench-aap2-001`](task-by-task/v2-bench-aap2-001-single-job-outcome.md)** — the one large,
  clean, mechanistically explained win in the branch (`+0.500` at equal `n`), and the argument that
  what it fixed was a **documentation defect** in the seed skill rather than a reasoning failure.
- **[`v2-bench-aap2-006`](task-by-task/v2-bench-aap2-006-log-root-cause.md)** — recorded by
  cap-evolve as broken by the champion; identical to the seed at `n=9` to six decimal places. The
  cleanest counterexample to trusting the run's own `fixed`/`broke` lists.

- **[`v1-aap2-0052`](task-by-task/v1-aap2-0052.md)** is the shortest and the most damning: its
  contract demands **zero** assertions, an empty list scores a vacuous `1.000`, and half of its
  `0.500` baseline measures nothing at all.
