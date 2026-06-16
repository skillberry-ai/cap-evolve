---
name: orchestrate
description: Drive the entire cap-evolve pipeline end to end, autonomously. Use when the user wants the whole optimization run with minimal hand-holding. Sequences intake → implement-and-check → baseline → the chosen algorithm loop → finalize → report, enforces the cap-evolve-check hard gate before spending budget, decides when to stop (budget/stall), and surfaces the honest test number at the end. Reads capevolve.yaml; respects the ask-user-if-missing rule for inputs.
component: orchestrate
argument-hint: "--spec .capevolve/project/capevolve.yaml [--execute]"
allowed-tools: Read, Write, Edit, Bash
provides: [report]
needs: [project]
sources: [evo]
---

# orchestrate — the whole pipeline, end to end

orchestrate is the autonomous driver: it runs every phase in order and enforces
the guardrails so a full optimization run needs little supervision. It does not
add new logic — it *sequences* the phase skills and refuses to let the run skip a
safety check. Its value is that the honesty discipline (ask-if-missing, hard gate,
val-only acceptance, sealed test) is applied automatically rather than relying on
the operator to remember each one.

## Inputs / outputs (manifest tokens)
- **needs:** `project` — resolved from `capevolve.yaml` (which capability / optimizer /
  algorithm / budget).
- **provides:** `report` — the end-to-end result: baseline → best val → sealed
  test, with the winner named.

## The sequence (and the guardrail at each step)
1. **intake** — collect inputs, scaffold the project, **ask for any missing NEEDED
   input** (never fabricate one).
2. **implement-and-check** — implement the adapter; **`cap-evolve check` must be green**
   (HARD GATE — do not advance until `{"ok": true}`).
3. **baseline** — freeze the split (once, seeded), score the seed on val, check
   **headroom** (stop early if the seed already saturates val).
4. **\<algorithm\>** — run the loop named in `capevolve.yaml` (default `all-at-once`):
   propose → evaluate(val) → diagnose → gate → accept/reject, until budget/stall.
   Acceptance is **always on val**, by significance (Δ > k·SE).
5. **finalize** — score the best candidate on the **sealed test split, once**.
6. **report** — baseline vs test; name the winner; surface pass^k and uncertainty.

The wiring is validated structurally: each step's `needs` must be satisfied by an
upstream `provides` in the manifest, so a misordered or incompatible pipeline is
caught before it runs.

## How to run
```
python scripts/run.py --spec .capevolve/project/capevolve.yaml            # print the plan
python scripts/run.py --spec .capevolve/project/capevolve.yaml --execute  # run it (cap-evolve run)
```
Without `--execute` it prints the ordered plan (sequence, components, gate mode,
budget) for inspection — run this first to confirm the pipeline before spending
anything. Or, host-agnostic, follow `RUN.md` step by step; or `cap-evolve run --spec`.

## Stopping rules
Stop when **any** holds:
- **budget exhausted** — `max_iterations`, `max_metric_calls`, or `max_usd` hit.
- **stall** — N consecutive rejects (the search has plateaued; more tries just
  burn budget chasing noise the gate will keep rejecting).
- **no headroom** — the baseline already saturates val.

Whatever the stop reason, **always finish with finalize + report** so the honest,
sealed-test number is recorded. An optimization run with no finalize has no result.

## What good vs bad looks like
- **Good:** the plan inspected before `--execute`; every guardrail enforced
  automatically; the run ends with a sealed-test number and a named winner, even
  when the answer is "no significant gain".
- **Bad:** advancing past a red `cap-evolve check`; gating on train; finalizing more
  than one candidate; declaring success on val without ever scoring test.

## References
- `references/concepts.md` — the phase sequence as a needs/provides DAG, where
  each honesty guardrail lives, and the stop rules, with sources.
