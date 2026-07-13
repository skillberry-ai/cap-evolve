---
name: hill-climb
description: Runs a global hill-climb optimization loop where the parent is always the current best candidate and the val significance gate decides acceptance. Use as the algorithm for most runs. Pick how each iteration's reflection is focused with --focus all (whole train set), cyclic (one task at a time), or hardest-first (lowest-scoring tasks first). Replaces the former all-at-once, cyclic, and hardest-first skills.
component: algorithm
argument-hint: "--run-dir DIR --project DIR --optimizer CMD [--focus all|cyclic|hardest-first]"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: [scores, traces, candidate]
---

# hill-climb — one loop, three focus schedules

Every iteration: take the current best candidate, ask the optimizer to propose an
edit (its prompt emphasizes a *focus set* of train tasks), score the result on
val, and accept only if it clears the significance gate. The accepted candidate
becomes the new best. The test split is never touched here — that is `finalize`.

The three former hill-climb skills were byte-identical except for one constant;
they are now one skill with `--focus`:

| `--focus` | what each iteration emphasizes | when to use |
|---|---|---|
| `all` (default) | the whole train set — find the single edit that lifts the most tasks | broad capability gaps; the usual choice |
| `cyclic` | one train task at a time, cycling through them | many distinct, unrelated failure modes |
| `hardest-first` | train tasks ranked by baseline score ascending (lowest first), then cycling | a few very hard tasks dominate the gap |

Why only the focus changes: the parent-selection rule (always the current best),
the gate, and the honesty guarantees are identical across schedules — only the
*attention* differs. Keeping one loop means a fix to the gate or memory wiring
can never drift between variants.

## Inputs / outputs (manifest tokens)
- **needs:** `scores` + `traces` (the per-task val results to reflect on) and
  `candidate` (the parent to extend).
- **provides:** `candidate` (the accepted best).

## Standalone use

```bash
python scripts/run.py --run-dir .capevolve/run_X --project .capevolve/project \
  --optimizer 'python .../run-optimizer/scripts/run.py --name mock --workdir {workdir} --prompt {prompt}' \
  --focus hardest-first --max-iterations 10 --n-trials 4
```

`--resume` continues from the run's current best (reading its val from rollouts)
instead of the baseline. `--no-regression` adds a SWE-bench-style dual gate:
reject a candidate that breaks any val task the parent already passed, even if the
mean improves.

Back-compat: `--focus all-at-once` is accepted and treated as `all`.

## Agent-mode loop
When `orchestration_mode: agent`, drive hill-climb yourself: from the baseline best, each iteration — propose ONE edit to the capability (per `--focus`: all / cyclic / hardest-first), evaluate the candidate on **val** via cap-evolve (writes rollouts+results), gate Δ>k·SE, accept→snapshot via the store / reject→revert. Log each iteration to the run dir's event log. Re-read `stop_condition`; stop on it or on stall/budget. Between iterations, confirm the run dir got this iteration's rollouts + event so the dashboard stays current. Seal once with `cap-evolve finalize`, then `report`.

## References
- `references/focus-schedules.md` — how each schedule builds its focus set.
