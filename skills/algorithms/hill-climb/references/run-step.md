# The shared iteration step (`harness.run_step`)

The contract every algorithm in this repo reuses for one propose → gate → commit
iteration (`core/cap_evolve/harness.py:1409`). `hill-climb/SKILL.md` states the
mechanism at the level needed to run it; this file is the verbatim contract, for
writing or debugging an algorithm that calls `run_step` directly.

`gepa`, `skillopt`, `agent-optimize` and `evograph` differ only in **which parent
they pick** and **which tasks they focus** — not in anything below.

## Signature and what varies

```
run_step(adapter, *, run_dir, parent_dir, optimizer, instructions, current_val,
         n_trials=1, gate_kwargs=None, candidate_id=None, parent_id=None,
         no_regression=False, rejected=None, history=None, store=None,
         capabilities=None, eval_split="val", optimizer_name=None,
         capability_sources=None, project_dir=None, protected_patterns=None) -> dict
```

`parent_dir` is the algorithm's parent-selection decision — the only place a
different search strategy enters. hill-climb passes `candidate_dir(best_id)`; gepa
passes a candidate sampled from its per-instance Pareto frontier. `instructions` is
the algorithm's focus decision. Everything else is fixed machinery.

The returned dict carries `candidate_id`, `accepted`, `decision`, `candidate_val`,
`parent_val`, `regressions`, the optimizer's seconds/usd/tokens, `optimizer_error`,
and `workdir` (`harness.py:1614-1626`).

## Cross-iteration files, and who owns each

Written into the workdir before the optimizer runs, with a prompt pointer to all four
(`harness.py:1062-1094`):

| file | owner | lifetime |
|---|---|---|
| `LEDGER.md` | framework, read-only to the optimizer | regenerated each iteration; every prior outcome plus the exact tasks it broke/fixed |
| `JOURNAL.md` | the optimizer, append-only | run-level handover; earlier entries must not be edited |
| `PROCESS.md` | the optimizer, required | fresh each iteration; **snapshotted with the candidate** and surfaced per-iteration by the dashboard |
| `RUNMAP.md` + `prior_iterations/<id>/` | framework | manifest plus every prior iteration's `PROCESS.md` and capability diff |

`_reconcile_journal` folds the optimizer's appended entry into the run-level journal
for accepted *and* rejected iterations, and reuses it as the candidate's lineage note
(`harness.py:1586-1588`).

## Memory across iterations

`_init_memory_store` (`harness.py:1631-1646`) creates `RejectedMemory` and `History`
and initializes the version store (git by default, with a `seed` commit on a fresh
run only). `_augment_instructions` injects both into every prompt, so the optimizer
sees what was already refuted and what already worked.

A **rejected** step records the candidate, the gate's reason, and the per-task
broke/fixed impact (`harness.py:1607-1608`). An **indecisive** step — tamper, or
coverage/infra void — is deliberately *not* recorded as a rejection
(`harness.py:1598-1605`): the edit was never evaluated, so filing it would teach the
optimizer to avoid a change nothing is known about. It also leaves the stall counter
untouched (`harness.py:1560-1564`).

## Snapshot and store

Every candidate is snapshotted, accepted or not, so any iteration can be diffed
(`harness.py:1557`). `_SNAPSHOT_IGNORE` (`harness.py:1842-1845`) excludes injected
read-context — `trajectories/`, `guidance/`, `prior_iterations/`, `LEDGER.md`,
`JOURNAL.md`, `RUNMAP.md`, and the per-agent skill dirs / always-on instruction files
— so stored candidates stay capability-only and diffs show the real edit.
`PROCESS.md` is deliberately kept. The store then commits the iteration, tagging
`best` on accept (`harness.py:1609-1612`).

## Protected paths → indecisive, never zero

With `protected_patterns` set, the protected files are hashed *after* context
injection (so the framework's own scratch never reads as tampering), marked
read-only, and re-verified **before any rollout is paid for**
(`harness.py:1467-1514`). On tamper the step is indecisive: `candidate_val` is None,
no reward is recorded, the stall counter is untouched, and best is unchanged. Scoring
such a candidate 0.0 would be wrong in the other direction — the number would
describe a compromised harness, not the edit.
