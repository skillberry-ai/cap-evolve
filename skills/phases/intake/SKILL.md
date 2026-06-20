---
name: intake
description: Phase 1 of the pipeline — collect inputs and scaffold the run. Use at the very start of any optimization. Interviews the user to decide what capability to optimize, which runner/optimizer/algorithm to use, and where the data is; scaffolds .capevolve/project/ (adapter stub, capevolve.yaml, PROJECT.md); and for every NEEDED input that is missing, asks the user (quoting path, how to retrieve it, alternatives) rather than fabricating it.
component: phase
argument-hint: "--base .capevolve"
allowed-tools: Read, Write, Edit, Bash
provides: [project, tasks]
needs: []
sources: []
---

# intake — collect inputs, scaffold the project

The first phase. Its job is to turn a vague wish ("make this agent better at X")
into a concrete, runnable project: a filled `capevolve.yaml`, an adapter ready to
implement, and **every NEEDED input resolved before any budget is spent**. Intake
is cheap; a botched intake is not — an unresolved input discovered three phases
later means a wasted optimization run and a meaningless number.

## Inputs / outputs (manifest tokens)
- **needs:** *(nothing)* — intake is the pipeline entry point.
- **provides:** `project` (the scaffolded `.capevolve/project/`) and `tasks` (the
  evaluation dataset, resolved either to a path or to the adapter's `tasks()`).

Downstream, `implement-and-check` consumes `project`; `baseline` consumes
`project` + `tasks`. If intake under-delivers either token, the hard gate in
`implement-and-check` fails loudly rather than silently optimizing against a stub.

## What it does
1. **Interview** (driven by this SKILL.md): pick the capability skill (*what* is
   optimized), the optimizer (*which* coding agent proposes edits), the algorithm
   (*the search loop*), the dataset, the splits, and the budget.
2. **Scaffold** `.capevolve/project/` from the template (`scripts/run.py`):
   adapter stub, `inputs/`, `capevolve.yaml`, `PROJECT.md`, and the optimizer-prompt
   template `optimizer/INSTRUCTIONS.md` (the whole `templates/project/` tree is
   copytree'd verbatim, so this file is already in place — confirm it exists).
3. **Resolve inputs** per `inputs/INPUTS.md` — the contract below.
4. **Wire trajectories + scoring into the adapter.** From the *trajectories path*
   and *metric extraction / scoring source* inputs:
   - implement `adapter.trajectories(split)` to RETURN the runner's native trajectory
     directory for the last eval of `split` (any structure/format; it is copied
     verbatim into the optimizer's `./trajectories/`). Return `None` only if there is
     genuinely no separate native store (cap-evolve then falls back to its per-rollout
     JSON) — note that choice in `PROJECT.md`.
   - implement `score()` to extract the OBJECTIVE metric from a rollout, matching the
     benchmark's own scoring source; verify it reproduces the benchmark's number.
5. **Author the optimizer instructions for THIS benchmark — SCOPED TO THE SELECTED
   CAPABILITIES.** Customize the scaffolded `.capevolve/project/optimizer/INSTRUCTIONS.md`.
   Keep the `{{...}}` placeholders intact (`{{FOCUS_SUMMARY}}`, `{{FAILURES}}`,
   `{{CAP_BRIEF}}`, `{{ALGO_BRIEF}}`, `{{BENCH_REPO}}` — the harness fills them per
   iteration). Keep the authored static guidance **short on meta-narration, explicit
   and DEMANDING on iteration depth**, and make it **capability-scoped**: include
   guidance, skill references, and edit-space ONLY for the capabilities actually
   listed in `capevolve.yaml: capabilities`.
   - **DEPTH MANDATE — address ALL failure clusters each iteration.** The authored
     instructions must demand a substantial multi-root-cause pass. Produce this
     target snippet:
     > "Each iteration is a substantial, multi-root-cause pass. Diagnose ALL clusters
     > and fix as many as possible in ONE candidate — improve multiple tools' code,
     > validation, and return values/errors; add new tools; sharpen many tool docs;
     > and fix the prompt — together. Scope each fix to protect passing tasks; do NOT
     > trade breadth for caution. A single small edit is an under-used iteration."
   - **State the GOAL up front:** maximize the eval score — make the largest
     improvement you can this iteration, grounded in the trajectories.
   - **Capability-scoping (the key rule):** reference `./guidance/<cap>/SKILL.md`
     and present the editable artifacts **for the selected caps only**. If only
     `tools` is selected, do NOT include any prompt-editing guidance, do NOT
     reference the `system-prompt` skill, and do NOT present the prompt/policy file
     as editable. If only `system-prompt` is selected, do not surface the tools file
     as editable. Each capability's "What you can change here" lives in its
     `./guidance/<cap>/SKILL.md` — point the optimizer there rather than restating it.
   - **Always include (capability-agnostic):** READ `./MEMORY.md` FIRST and never
     re-propose an approach recorded as rejected *as implemented* (a better-designed
     version may still work — it is not a permanent ban); READ and USE the diagnose
     skill `./guidance/diagnose/SKILL.md`, the optimizer features reference
     `./guidance/optimizer/<name>.md`, this step's `./trajectories/`, `./STATE.md`,
     and any `./guidance/sources/` data-model files; understand the prior run-dir
     layout (`<run_root>/candidates/<id>/`, `/work/<id>/`,
     `/rollouts/<split>/<task>__<cand>__t<k>.json`, `/events.jsonl`,
     `/rejected.jsonl`, per-iteration git diffs); write the rich
     `## Handover for next iteration` STATE.md section (Approaches tried — 1 line
     each, Lessons learned, Recommendation, and What-regressed-as-implemented — NOT
     a permanent ban-list).
6. **Set the spec keys** in `capevolve.yaml`:
   - `runner_repo_path` — the benchmark/runner source, surfaced read-only to the
     optimizer.
   - `optimizer_instructions_file` — point at the customized template (default
     `optimizer/INSTRUCTIONS.md`).
   - `capability_sources` — the benchmark's data-model / types source files that the
     tools import (resolved relative to the project dir; copied verbatim into the
     optimizer's `./guidance/sources/`), so the optimizer can write correct code
     against the real types. Set this whenever a selected capability's code imports a
     shared types/data-model module; leave the default `[]` when there is none.

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

### Block on a missing NEEDED input (never fabricate)
The action when a NEEDED input is absent depends on the run mode:
- **Interactive / chat mode** — ASK THE USER and wait: quote *what* is needed, *why*
  it is needed (what breaks without it), and *how* to provide it (the exact path /
  command / option / alternatives from `INPUTS.md`). Do not proceed past the missing
  input.
- **Non-interactive mode** (`cap-evolve run` / orchestrate, no human to ask) — do NOT
  fabricate. WRITE a clearly delimited section into `PROJECT.md`:
  `BLOCKED: <input> — why it is needed — how to provide it`, then STOP with a non-zero
  exit. A blocked-but-honest stop is correct; a green run on a guessed input is not.

This extends the ask-if-missing discipline above — it is the same rule, with an
explicit non-interactive fallback so a headless run fails loud and recorded instead
of silently inventing a dataset, scorer, trajectories path, or scoring source.

### Why a contract, not a guess
The classic failure mode of "auto-optimize my agent" tooling is to start running
with whatever it can find and backfill assumptions. That yields a green run and a
worthless result. Splitting inputs into NEEDED (blocking → ask) vs RECOMMENDED
(default → log) makes the *only* legitimate way to proceed-without-an-input an
explicit, recorded default — never a silent fabrication. Treat `INPUTS.md` as the
spec; this SKILL.md is just the procedure for honoring it.

## Dual-mode
This phase runs two ways from the **same** SKILL.md: standalone as the slash command `/cap-evolve:intake` (the `argument-hint` shows its run.py args), and orchestrator-callable — `cap-evolve run` / the `orchestrate` skill invokes the same `scripts/run.py` headlessly and threads the run dir between phases.

## How to run
```
python scripts/run.py --base .capevolve        # scaffold .capevolve/project
```
The script is purely mechanical: it copies the template and prints the next
steps. The *judgment* — interviewing, choosing components, and running the
ask-if-missing loop — is yours, driven by this SKILL.md and `inputs/INPUTS.md`.

Then implement `adapters/adapter.py`, fill `capevolve.yaml`, and proceed to
`implement-and-check`. Together, **intake → implement-and-check** is the *full
integration*: scaffold → implement the 4 adapter methods → `cap-evolve check` green,
before any budget is spent. The using-agent (e.g. the chosen optimizer) can run
this whole integration autonomously.

> **Worked example (onboard a new benchmark from a prompt):** see `examples/` for
> an end-to-end onboarding. The intake/onboarding step **installs the benchmark**
> (clones + installs it) and the **optimizer agent** wires the adapter from the
> stub until `cap-evolve check` passes, then optimizes the selected capability. The
> example's `setup.sh` is the executable transcript of that onboarding; `run.sh`
> runs the full optimization with the live dashboard.

## What good vs bad intake looks like
- **Good:** every NEEDED input resolved to a real path or `"adapter"`; splits and
  budget chosen deliberately; each defaulted RECOMMENDED input logged in
  `PROJECT.md`; `capevolve.yaml` fully filled; the user answered every blocking
  question before the scaffold was declared done.
- **Bad:** a tasks file that "looked plausible" was synthesized; the scorer leaks
  the gold answer into feedback; test == train with no note; budget left at a
  default that cannot possibly find a gain; the run proceeded past a missing
  NEEDED input "to keep moving".

## References
- `references/concepts.md` — the inputs contract, NEEDED vs RECOMMENDED
  rationale, the four adapter methods, and split/trial/budget guidance with
  sources.
