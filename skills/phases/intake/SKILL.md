---
name: intake
description: Phase 1 of the pipeline — collect inputs and scaffold the run. Use at the very start of any optimization. Interviews the user to decide what capability to optimize, which runner/optimizer/algorithm to use, and where the data is; scaffolds .agentcapo/project/ (adapter stub, acapo.yaml, PROJECT.md); and for every NEEDED input that is missing, asks the user (quoting path, how to retrieve it, alternatives) rather than fabricating it.
component: phase
argument-hint: "--base .agentcapo"
allowed-tools: Read, Write, Edit, Bash
provides: [project, tasks]
needs: []
sources: []
---

# intake — collect inputs, scaffold the project

The first phase. Its job is to turn a vague wish ("make this agent better at X")
into a concrete, runnable project: a filled `acapo.yaml`, an adapter ready to
implement, and **every NEEDED input resolved before any budget is spent**. Intake
is cheap; a botched intake is not — an unresolved input discovered three phases
later means a wasted optimization run and a meaningless number.

## Inputs / outputs (manifest tokens)
- **needs:** *(nothing)* — intake is the pipeline entry point.
- **provides:** `project` (the scaffolded `.agentcapo/project/`) and `tasks` (the
  evaluation dataset, resolved either to a path or to the adapter's `tasks()`).

Downstream, `implement-and-check` consumes `project`; `baseline` consumes
`project` + `tasks`. If intake under-delivers either token, the hard gate in
`implement-and-check` fails loudly rather than silently optimizing against a stub.

## What it does
1. **Interview** (driven by this SKILL.md): pick the capability skill (*what* is
   optimized), the optimizer (*which* coding agent proposes edits), the algorithm
   (*the search loop*), the dataset, the splits, and the budget.
2. **Scaffold** `.agentcapo/project/` from the template (`scripts/run.py`):
   adapter stub, `inputs/`, `acapo.yaml`, `PROJECT.md`.
3. **Resolve inputs** per `inputs/INPUTS.md` — the contract below.

## Ask-the-user-if-missing (mandatory — the core discipline)
Read `inputs/INPUTS.md`. It classifies every input as **NEEDED** or
**RECOMMENDED**. For each **NEEDED** input that is not already present:

> **ASK THE USER.** Quote (a) the exact path where it is expected, (b) the
> command or option that produces it, and (c) any alternatives. Then wait.

**Never invent a NEEDED input.** Fabricating a dataset, a scorer, or a gold
answer does not unblock the run — it produces a number that measures nothing and
hides that fact. A missing tasks file is a *question for the user*, not a gap for
you to paper over. This is the single most important behavior of this phase.

**RECOMMENDED** inputs have sane defaults and may be skipped — but log every skip
in `PROJECT.md` (e.g. "num_trials defaulted to 1 — scores will be single-trial,
so the significance gate will correctly reject marginal gains"), so the honesty
cost of each default is visible at report time.

### Why a contract, not a guess
The classic failure mode of "auto-optimize my agent" tooling is to start running
with whatever it can find and backfill assumptions. That yields a green run and a
worthless result. Splitting inputs into NEEDED (blocking → ask) vs RECOMMENDED
(default → log) makes the *only* legitimate way to proceed-without-an-input an
explicit, recorded default — never a silent fabrication. Treat `INPUTS.md` as the
spec; this SKILL.md is just the procedure for honoring it.

## How to run
```
python scripts/run.py --base .agentcapo        # scaffold .agentcapo/project
```
The script is purely mechanical: it copies the template and prints the next
steps. The *judgment* — interviewing, choosing components, and running the
ask-if-missing loop — is yours, driven by this SKILL.md and `inputs/INPUTS.md`.

Then implement `adapters/adapter.py`, fill `acapo.yaml`, and proceed to
`implement-and-check`.

## What good vs bad intake looks like
- **Good:** every NEEDED input resolved to a real path or `"adapter"`; splits and
  budget chosen deliberately; each defaulted RECOMMENDED input logged in
  `PROJECT.md`; `acapo.yaml` fully filled; the user answered every blocking
  question before the scaffold was declared done.
- **Bad:** a tasks file that "looked plausible" was synthesized; the scorer leaks
  the gold answer into feedback; test == train with no note; budget left at a
  default that cannot possibly find a gain; the run proceeded past a missing
  NEEDED input "to keep moving".

## References
- `references/concepts.md` — the inputs contract, NEEDED vs RECOMMENDED
  rationale, the four adapter methods, and split/trial/budget guidance with
  sources.
