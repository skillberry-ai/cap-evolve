# Focus schedules

All three schedules share the same loop body in `harness.hill_climb_loop`; they differ
only in how the per-iteration *focus set* is chosen. The focus set drives
`_focus_instructions`, which builds the optimizer prompt from the parent's failing
**val** tasks (actionable failures separated from infrastructure errors via the
structured `raw.errored` flag, not feedback substring matching).

The focus set is always drawn from **val ids** (`harness.py:2183`). That is not a
preference: `_focus_instructions` filters the parent's val per-task rows
(`harness.py:2011-2013`), and the splits are disjoint slices of one shuffled id list
(`splits.py:117-119`), so a focus set of train ids would intersect those rows in
nothing and the prompt would render `0 failing of 0 tasks` with no failure index at
all. Train tasks are never individually scored by this loop, so there is no per-task
signal about them to focus on.

## all (default)

- Focus set = every val task (no filtering).
- The prompt asks the optimizer to find the single edit that lifts the most tasks.
- Best when the capability has broad gaps rather than a few isolated ones.

## cyclic

- Iteration `i` focuses on `val[i % len(val)]` — one task at a time, round-robin.
- Useful when failures are heterogeneous: forcing attention onto each task in turn
  prevents the optimizer from over-fitting to whichever failure is loudest.

## hardest-first

- Val ids are sorted by the parent's per-task reward ascending (hardest first) once,
  at loop entry, from the `current_val` the loop already holds — no extra evaluation.
- Iteration `i` focuses on the `i`-th hardest task, then cycles.
- Useful when a small number of very hard tasks dominate the val gap and you want
  budget spent there first.
- The order is fixed at entry, so it reflects the parent at that moment, not the
  running best. Restart the loop (or `--resume`) to re-rank.

## Non-regression under a narrow focus

The *protect these passing tasks* block is built from the whole val split, not the
focus set (`harness.py:2016-2020`). An edit aimed at one task must still not break a
passing task outside the focus, so narrowing attention must never narrow the
constraint.

## Parent selection (all schedules)

The parent is always the current best candidate — a strict global hill-climb. A
per-task Pareto frontier that keeps specialists is a *different* algorithm (the `gepa`
skill), not a focus mode here.
