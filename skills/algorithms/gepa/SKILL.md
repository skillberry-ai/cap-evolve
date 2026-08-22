---
name: gepa
description: Runs the GEPA optimization loop (arXiv:2507.19457) — sample-efficient reflective Pareto search. A cheap train-minibatch pre-gate decides whether a proposal is worth an expensive val evaluation, and parents are sampled from a per-instance frontier so specialists survive instead of being averaged away. Use when rollouts are expensive and the scorer returns informative per-task feedback, and you want the most quality per evaluation. Use hill-climb instead for a first baseline run or for feedback-poor binary pass/fail tasks.
component: algorithm
argument-hint: "--run-dir DIR --project DIR --optimizer 'CMD {workdir} {prompt}' [--max-metric-calls N --minibatch-size 4 --component-selector round_robin|all --max-merges 2 --resume]"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: [scores, traces, reflective_dataset, candidate]
sources: [gepa]
---

# gepa — sample-efficient reflective Pareto search

`algorithms/hill-climb` owns the mechanics every algorithm shares: parent →
proposal → val gate → commit. Read it first. This page states only what GEPA
(Agrawal et al., 2025) does **differently**, and why those differences are the
paper's actual contribution rather than decoration. A thin wrapper over
`cap_evolve.gepa.gepa_loop`.

## The two mechanisms, and why removing either turns GEPA back into hill-climb

**1. The parent is sampled from per-instance winners, not from the global best.**
A mean is a lossy summary. A candidate that fixes one genuinely hard task while
regressing three easy ones has a *worse* mean than the incumbent, so a
best-parent rule discards it — and with it the only text in the pool that has
ever solved that task. GEPA instead scores per val instance and samples
frequency-weighted over candidates that (co-)win at least one, so specialists and
stepping-stones stay reachable as parents while their mean is still behind. That
is the quality-diversity argument (MAP-Elites): keep the *set* that covers the
task distribution, not the single champion. Sampling is stochastic and seeded, so
the exploration is reproducible.

**2. A cheap train minibatch pre-gates the expensive val evaluation.** Rollouts
dominate cost and a full-val eval costs `|val| · n_trials` of them. Most
proposals are bad; paying full price to find that out is what makes naive
reflective search unaffordable, and GEPA's headline "~35× fewer rollouts" comes
almost entirely from *not* paying it. So parent and child are evaluated on the
**same** small train minibatch (`2 · minibatch-size` rollouts, eval-cached) and
the child is dropped unless `sum(child) > sum(parent)`. The minibatch never
*decides* acceptance — it decides whether acceptance is worth measuring.

A side benefit of (2): reflection reads **train** traces, so the proposer never
sees the split its gate is computed on.

## What differs from hill-climb, step by step

1. **Parent** — frequency-weighted sample over per-instance (co-)winners
   (`--selection-strategy`, default `pareto_per_instance`), not the current best.
2. **Signal** — a minibatch of `--minibatch-size` (default 4) **train** ids,
   evaluated with traces, instead of the whole train focus set.
3. **Reflective dataset** — `REFLECTION.md` in the optimizer workdir, over the
   parent's failing minibatch tasks (`phases/diagnose` owns what one is and what
   shape it takes). "Failing" is the hard threshold `reward < 1.0`, so with a
   graded scorer that never reaches 1.0 every sampled task is listed and the
   header always reads `0/N pass` — read it as "sampled tasks, worst first". Each
   entry is truncated to ~800 chars and at most 12 tasks are written: a summary,
   not an archive; untruncated rollouts stay in `rollouts/train/`. The prompt also
   carries the run's cross-iteration files (`LEDGER.md`, `PROCESS.md`, `RUNMAP.md`
   + `prior_iterations/`) so a proposal builds on prior work.
4. **Local gate** — child on the same minibatch, `sum(child) > sum(parent)`, else
   dropped with no val spend. This is the extra stage; everything after it is
   hill-climb's.
5. **Merge** — every `--merge-cadence` accepts, find two strict-frontier
   dominators sharing a common ancestor both beat and recombine them
   component-by-component (each component from whichever descendant changed it),
   then minibatch-gate and val-gate the result like any other child.

Note the word "frontier" covers two different sets here: the *sampling pool* in
step 1 is every candidate with ≥1 instance win, which can include dominated
candidates; the strict per-task Pareto frontier (`selection.pareto_frontier`) is
a subset of it and is what the merge and the reported `frontier_size` use.

## Component selection

A **component** is one editable file of the candidate. (Unrelated to
hill-climb's `--focus`, which selects *tasks*; this selects *files*.)

- **`--component-selector round_robin`** (default): one component per iteration,
  cycled, written to `FOCUS.md`. Small attributable changes are exactly the unit
  the merge can later recombine — a sprawling multi-file rewrite cannot be.
- **`--component-selector all`**: list every component; the optimizer may edit
  anywhere. Use for monolithic capabilities or genuinely cross-cutting changes.

For a single-file capability the two coincide and the merge skips gracefully
(`gepa_merge_skip`) rather than emitting a degenerate child.

## Key hyperparameters

- `--max-metric-calls` (default 0 = unlimited): PRIMARY budget, checked
  **between** iterations. An in-flight iteration runs to completion, so actual
  spend can exceed it by up to `2·minibatch-size + |val|·n-trials` (one more
  minibatch on a merge iteration). Set it below your hard ceiling.
- `--max-iterations` (default 50): secondary cap on propose→gate iterations.
- `--minibatch-size` (default 4): train ids per cheap local gate.
- `--n-trials` (default 1): rollouts/task on the full-val eval (raise under noise
  so the significance gate is trustworthy). Minibatch evals are always 1 trial.
- `--max-merges` (default 2): cap on merge **attempts that built a candidate** —
  a merge rejected at either gate consumes one. A skip (no eligible pair) is free.
- `--merge-cadence` (default 3): accepts between merge attempts.
- `--protected-paths` (empty = off; `default` = the built-in globs): seals the
  eval surface (scorer/gold/tasks/tests).
  A child that edits one is **INDECISIVE** — no reward recorded, not remembered
  as rejected, stall counter untouched — because scoring a gold-hacking edit at
  all would teach the optimizer that it worked.
- `--workers` (default 1): pools the minibatch rollouts. Only safe when the
  adapter's `run_target` is thread-safe.
- `--store` / `--store-commit-cmd` (default `git`): where accepted candidates are
  committed.
- `--gate-mode` / `--k-se`, `--no-regression`, `--seed`: as hill-climb.
- `--resume`: rebuild pool/lineage/frontier from `gepa_state.json` + each
  accepted candidate's rollouts and continue the search. Preserved spend keeps
  the budget honest; the parent-sampling RNG stream restarts, so a resumed run is
  not byte-identical.

## Known gaps (present tense — the shipped loop, not the paper)

- The reflective dataset does **not** carry the task input, though `gepa.py`'s
  docstring claims it does — the optimizer sees a bad answer to an unknown
  question. And on an eval-cache hit only `{reward, feedback}` were stored, so
  `Agent output:` comes out empty; re-sampled parents hit the cache routinely
  (#111, PR #210).
- Candidate snapshots keep the loop's own scratch (`REFLECTION.md`/`FOCUS.md`/…)
  because the snapshot call omits the ignore list every other algorithm passes
  (#110, PR #350). Those are excluded from the component list, but the
  optimizer-agent dotfiles (`.claude/`, `CLAUDE.md`, `AGENTS.md`) are **not**, so
  round-robin can burn an iteration on one.
- Iterations are charged against budget while no `step` event is emitted, so
  consumers counting iterations from `step` records see zero (#216/#224, PR #356).
- Optimizer context reaching GEPA has been narrower than hill-climb's (#109,
  PR #355). `JOURNAL.md` is injected as the cross-run handover but never
  accumulates here, which is why step 3 above leaves it out of the list.
- If `splits.train` is empty the minibatch silently falls back to **val** ids,
  putting the gate split in front of the proposer, with no warning. Do not run
  GEPA with a zero-size train split.

## How to run

```bash
python scripts/check.py    # behavioral, offline (mock optimizer + synthetic adapter)
python scripts/run.py --run-dir .capevolve/run_X --project .capevolve/project \
  --optimizer 'python .../run-optimizer/scripts/run.py --name mock --workdir {workdir} --prompt {prompt}' \
  --max-metric-calls 400 --minibatch-size 4 --component-selector round_robin
```

Requires `baseline` first (reads the seed's full-val result from `baseline.json`).
Reports the pool, `frontier_size`, best candidate, accepts, merges, and
metric-calls spent.

## Agent-mode loop

When `orchestration_mode: agent`, follow `orchestrate/orchestrate` §Agent-mode
loop for the shared rules, and make each round GEPA-shaped: pick the parent by
per-instance win count; sample `minibatch-size` **train** ids; evaluate parent
then child on that same minibatch and drop the child unless `sum(child) >
sum(parent)`; only then pay for a full **val** eval and its gate. Reflect on the
train minibatch, never on val — val is the judge, not the teacher.

## References

- `references/concepts.md` — the paper's thesis (language as a richer learning
  medium than a scalar), the frequency-weighted per-instance frontier, the
  system-aware merge and its tie-breaking, the metric-call/eval-cache accounting,
  and how the pieces relate to the hill-climb / skillopt siblings. Load when you
  need the reasoning behind a knob rather than its value. Cites arXiv:2507.19457.
