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

## Step 0 — Inspect before asking
Before any question, inspect the target so you can PROPOSE defaults instead of asking blind:
1. Look at the repo/benchmark/agent: entrypoint, how one eval runs, where traces/scores live.
2. Detect candidate metrics (what the scorer emits), a natural train/val/test split, and cost caps.
3. Run `gh auth status` to know whether GitHub is available.

Then ask the FEWEST questions — present detected metrics/splits/caps as multiple-choice
defaults with a free-text escape, keeping the ask-user-if-missing discipline for NEEDED
inputs. The metric / GitHub / stop-condition questions below feed directly into the
`capevolve.yaml` spec keys, so ask them here (after inspecting, before scaffolding).

### Metrics
- Which metrics should the dashboard show? (detected: `<list>`) — multiple choice + free text → `metrics_display`.
- Which ONE gates accept/reject? — single choice → `metric_primary`. (This is the only metric the gate uses.)
- For each shown metric, is higher or lower better? → `metric_directions` (parallel to `metrics_display`).

### GitHub integration
- `gh auth status` = authed? Offer: mirror the algorithm's work items as issues + ship winner as PR (`Closes #n`) → `github_integration: true`; else offer `gh auth login` or skip → `false`. WHAT gets mirrored is algorithm-specific (the `algorithm_skill` defines it — e.g. evo-graph → weaknesses). GitHub is mirror-only; the run dir stays authoritative.

### Stop condition (agent mode)
- Free-text halt rule re-read each round → `stop_condition`. Deterministic mode leaves it blank and uses budget knobs.

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
   - **Make `score()`'s feedback ARGUMENT-LEVEL — it IS the learning signal.** A
     tool-name-only signal ("action X was wrong") is too coarse for the optimizer to
     localize a fix; it pattern-matches to prose rules and the run plateaus. For EACH
     failing check, the feedback must point at the specific argument/value/step that
     was wrong: name the wrong ARGUMENT key and the **agent's OWN wrong value** (not
     the gold value), name the wrong target id, and for communication/omission misses
     name the value or field the agent failed to state **when it is derivable from the
     agent's own state** (e.g. an un-stated computed total). This is **gold-SAFE**:
     derive everything from the agent's own messages/tool-calls/observed state (and the
     user's own profile/db state the agent saw) — use the gold record ONLY to learn
     WHICH check/argument failed (key names are safe; gold VALUES must never be read or
     printed). When a piece is not safely derivable, fall back to the coarser
     tool-name message. Keep `score()` deterministic (the check gate requires it).
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
   - **The authored INSTRUCTIONS MUST encode all three of these (generic, capability-scoped):**
     1. **STEP-0 reading mandate.** Before diagnosing, the optimizer must READ
        `./guidance/<cap>/SKILL.md` (for EACH selected capability) and the optimizer
        features reference under `./guidance/optimizer/`. State this as an explicit
        first step.
     2. **The EXISTING-tool-code mandate** (when `tools` is selected). Demand: convert
        violated textual rules into in-code checks across MANY EXISTING tool bodies —
        most violated rules govern a tool that already exists, so the fix is an in-body
        guard there, not a new tool. State plainly: *a docstring-only iteration (or one
        that only adds a single new tool + rewords docstrings, leaving rules as prose)
        is under-used.*
     3. **The explicit TWO-PHASE subagent pattern.** Require: Phase 1 — diagnose
        fan-out (one read-only subagent per trajectory-group → tight issue list; main
        dedups into clusters); Phase 2 — implement fan-out (one edit-subagent per
        ISSUE, each in its own worktree, each PREFERRING to edit the EXISTING tool's
        code body to enforce its rule); then the main agent MERGES all edits into ONE
        candidate. Point at `./guidance/optimizer/<name>.md` for the agent's concrete
        trigger phrasing.
     4. **The NON-OVERFITTING guardrail.** Demand that every prompt/tool edit encode
        a GENERAL rule/policy/validation that generalizes across the whole class of
        inputs — NEVER hardcode a specific task's id/value/date/name/answer. A guard
        must fire on the general condition (e.g. "id not in the user's profile"), not
        match a literal value (NOT `if id == "<TASK_SPECIFIC_ID>"`). A literal special-case that
        only helps one task is forbidden — it overfits, fails the held-out gate, and
        hurts other tasks. Per-task specifics are for understanding the failure CLASS
        only; the fix must be general.
     5. **EXPLOIT ground-truth/eval present in the trajectories (diagnosis only).**
        Tell the optimizer that when `./trajectories/` include ground-truth /
        expected actions / a reward breakdown, it should USE them during diagnosis to
        localize the exact defect (expected vs actual action/argument/value) — and if
        not present, infer from the traces + feedback. State plainly that ground truth
        informs the failure class only; the resulting edit must still be GENERAL
        (guardrail 4) and never copy a gold value.
   - **Capability-scoping (the key rule):** reference `./guidance/<cap>/SKILL.md`
     and present the editable artifacts **for the selected caps only**. If only
     `tools` is selected, do NOT include any prompt-editing guidance, do NOT
     reference the `system-prompt` skill, and do NOT present the prompt/policy file
     as editable. If only `system-prompt` is selected, do not surface the tools file
     as editable. Each capability's "What you can change here" lives in its
     `./guidance/<cap>/SKILL.md` — point the optimizer there rather than restating it.
   - **Always include (capability-agnostic):** READ the four cross-iteration files in
     the working dir FIRST — `./LEDGER.md` (framework facts: each iteration's outcome +
     tasks broken/fixed), the whole `./JOURNAL.md` (the optimizer's append-only
     handover across the run), and `./RUNMAP.md` + `./prior_iterations/<id>/` (every
     prior iteration's PROCESS.md + capability diff) — and never re-propose an approach
     the journal/ledger shows was rejected *as implemented* (a better-designed version
     may still work — not a permanent ban); READ and USE the diagnose skill
     `./guidance/diagnose/SKILL.md` (incl. its KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP
     tags), the optimizer features reference `./guidance/optimizer/<name>.md`, this
     step's `./trajectories/`, and any `./guidance/sources/` data-model files. Each
     iteration the optimizer MUST: fill `./PROCESS.md` (the required explainability
     template — ranked issues + tags, every edit + class, verify-the-fix,
     subagents/features used, what to preserve, what was skipped) and APPEND its entry
     to `./JOURNAL.md` below the marker (what was tried / worked / regressed / refuted /
     plateau-signal / focus-next). Ship MULTIPLE edit classes and ADD a new
     code-bearing tool whenever a CAPABILITY-GAP/stall cluster is present.
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
   - `target_model` (+ optional `target_profile_file`) — the runtime/CONSUMING LLM the
     agent reads the capabilities with, DISTINCT from `optimizer_model`. A model id or a
     tier (`frontier|strong|mid|weak`); steers the optimizer prompt + capability guidance
     to optimize FOR that reader. Ask which model the agent runs at runtime; leave blank
     (profile-agnostic) if unknown. See `inputs/INPUTS.md` → `target_model`.

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
- **Bad:** authored INSTRUCTIONS that let an iteration pass by adding one tool +
  rewording docstrings (leaving violated rules as prose) — or that omit the STEP-0
  reading mandate, the existing-tool-code mandate, or the explicit two-phase
  (diagnose fan-out → implement fan-out → merge) subagent pattern.

## References
- `references/concepts.md` — the inputs contract, NEEDED vs RECOMMENDED
  rationale, the four adapter methods, and split/trial/budget guidance with
  sources.
