# Focus schedules

All three schedules share the same loop body in `harness.hill_climb_loop`; they
differ only in how the per-iteration *focus set* of train tasks is chosen. The
focus set drives `_focus_instructions`, which builds the optimizer prompt from the
parent's failing val tasks (actionable failures separated from infrastructure
errors via the structured `raw.errored` flag, not feedback substring matching).

## all (default)
- Focus set = the whole train set (no filtering).
- The prompt asks the optimizer to find the single edit that lifts the most tasks.
- Best when the capability has broad gaps rather than a few isolated ones.

## cyclic
- Iteration `i` focuses on `train[i % len(train)]` — one task at a time, round-robin.
- Useful when failures are heterogeneous: forcing attention onto each task in turn
  prevents the optimizer from over-fitting to whichever failure is loudest.

## hardest-first
- Before the loop, the seed is scored on the **train** split once; train tasks are
  sorted by reward ascending (hardest first).
- Iteration `i` focuses on the `i`-th hardest task (then cycles).
- Useful when a small number of very hard tasks dominate the val gap and you want
  budget spent there first.

## Parent selection (all schedules)
The parent is always the current best candidate — a strict global hill-climb. A
per-task Pareto frontier that keeps specialists is a *different* algorithm
(the `gepa` skill, which keeps a per-instance Pareto frontier), not a focus mode here.
