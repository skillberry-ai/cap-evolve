---
name: intake
description: Starts a cap-evolve optimization run. Interviews the user to decide what capability to optimize, which runner/optimizer/algorithm to use, and where the tasks and the scoring source live, then scaffolds .capevolve/project/ (adapter stub, capevolve.yaml, PROJECT.md). Use when someone asks to optimize or improve an agent capability against an eval and no project exists yet — "set up a run", "start optimizing X", "make X score higher on this benchmark". This is Phase 1 of the pipeline. For every NEEDED input that is missing it asks the user — quoting the expected path, how to retrieve it, and the alternatives — instead of fabricating it. Not for a project that already exists: when .capevolve/project/ is present, go to implement-and-check or the algorithm loop instead.
component: phase
argument-hint: "--base .capevolve --workdir ."
allowed-tools: Read, Write, Edit, Bash
provides: [project, tasks]
needs: []
sources: []
---

# intake — collect inputs, scaffold the project

Turn a vague wish ("make this agent better at X") into a runnable project: a filled
`capevolve.yaml`, an adapter ready to implement, and **every NEEDED input resolved
before any budget is spent**. Intake is cheap; an unresolved input found three phases
later is a wasted run and a meaningless number.

## Ask, never fabricate — the core discipline of this phase

`inputs/INPUTS.md` classifies every input **NEEDED** or **RECOMMENDED**. For each
**NEEDED** input that is not already present, do not proceed:
- **Interactive / chat mode — ASK THE USER and wait.** Quote all three, they are in
  `INPUTS.md` per input: (a) the exact path the input is expected at, (b) the command
  or option that produces it, (c) the alternatives. Say what breaks without it.
- **Non-interactive** (`cap-evolve run` / the `orchestrate` skill, nobody to ask) —
  write `BLOCKED: <input> — why it is needed — how to provide it` into `PROJECT.md`
  and exit non-zero. A blocked-but-honest stop is correct; a green run on a guessed
  input is not.

A fabricated dataset, scorer, trajectories path or gold answer does not unblock the run
— it produces a number that measures nothing and hides that fact. A missing tasks file
is a *question for the user*, not a gap for you to paper over.

**RECOMMENDED** inputs may take their default, but log every default in `PROJECT.md`
with its honesty cost (e.g. "num_trials=1 — single-trial scores, so the significance
gate will correctly reject marginal gains"), so the cost is visible at report time.

## Step 0 — mine, then inspect, then ask once
1. **Mine the conversation first.** Anything the user already said is an answer you
   must not re-ask — "optimize my airline policy on the flight-change tasks" already
   fixed the capability, the artifact and the task subset. Harvest that, and any
   correction the user made, before asking anything.
2. **Run the miner.** `python scripts/run.py --base .capevolve --workdir <repo-root>`
   scaffolds and returns `discovered` — task files, capability artifacts, existing
   adapters. Reuse what it found; never re-author it.
3. **Inspect what `discovered` leaves open**: the entrypoint, how one eval runs, where
   traces and scores land, candidate metrics, a natural train/val/test split, cost caps.
   Run `gh auth status`. Fan subagents out over the benchmark repo (entrypoint, scorer,
   trace dir, task schema) *while* the user answers instead of serializing — come
   prepared, so the user carries as little of the research as possible.
4. **Then ask the FEWEST questions, as ONE numbered batch**, each with the detected
   value pre-filled as a default plus a free-text escape — including the ones only a
   human can answer: which metric gates accept/reject and each shown metric's
   direction, GitHub mirroring, deterministic vs agent orchestration (plus
   `stop_condition` in agent mode), splits, trials, budget, and `memory_skill`
   (default `md-files`; offer `wiki` — the weakness-graph format, see
   `inputs/INPUTS.md` — when the user wants weaknesses tracked as a persistent graph
   rather than an append-only journal). `inputs/INPUTS.md` → RECOMMENDED is the
   authority on each key; SKILL.md only fixes *when* to ask. Define jargon in a
   clause before using it ("pass^k — how often it succeeds on all k tries"); the user
   may be a domain expert, not an ML one.
5. **Confirm before scaffolding.** Echo the resolved spec back as one block —
   capability, optimizer, algorithm, dataset, splits, budget, every RECOMMENDED input
   you are defaulting — and get a yes. A misread is cheapest to fix here.

## What it does
The interview settles the capability skill (*what* is optimized), the optimizer (*which*
coding agent proposes edits), the algorithm (*the search loop*), dataset, splits, budget.
1. **Scaffold** `.capevolve/project/` via `scripts/run.py`: adapter stub, `inputs/`,
   `capevolve.yaml`, `PROJECT.md`, and `optimizer/INSTRUCTIONS.md`. The whole
   `templates/project/` tree is copytree'd verbatim — confirm the files landed.
2. **Resolve inputs** per `inputs/INPUTS.md`, honoring the ask-never-fabricate rule.
3. **Record** the resolved trajectories path and the scoring source in `PROJECT.md`, so
   `implement-and-check` wires `trajectories()` and `score()` against real inputs rather
   than guesses. `inputs/INPUTS.md` → **scorer** specifies exactly what the feedback must
   be (argument-level, gold-safe) and that `score()` must be deterministic — follow it
   literally, that feedback is the learning signal. Note in `PROJECT.md` if you
   deliberately return `None` from `trajectories()` (cap-evolve then falls back to its
   own per-rollout JSON).
4. **Customize the scaffolded `optimizer/INSTRUCTIONS.md`** for THIS benchmark. The
   shipped template already carries the depth mandate, the non-overfitting guardrail,
   the STEP-0 reading mandate and the cross-iteration file protocol — do not
   re-author any of them. Your three jobs:
   a. keep every `{{...}}` placeholder intact (`{{FOCUS_SUMMARY}}`, `{{FAILURES}}`,
      `{{CAP_BRIEF}}`, `{{ALGO_BRIEF}}`, `{{BENCH_REPO}}` — the harness fills them per
      iteration; `implement-and-check`'s pipeline self-test fails if one is deleted,
      and rendering must leave no `{{` behind);
   b. **scope it to the selected capabilities** — delete the sections for capabilities
      not listed in `capevolve.yaml: capabilities`, so a run never presents an
      artifact as editable that this run does not own. Point the optimizer at
      `./guidance/<cap>/SKILL.md` for each selected capability's own edit space, and
      at `./guidance/diagnose/SKILL.md` for the failure taxonomy — both are
      materialized into its working dir. When a selected capability ships one, also
      point at `./guidance/<cap>/references/optimizer-playbook.md`;
   c. add the benchmark-specific facts the template cannot know: where the runner
      writes traces, what the scoring source is, which data-model files the
      capability's code imports.
5. **Set the spec keys** in `capevolve.yaml` — `runner_repo_path`,
   `optimizer_instructions_file`, `capability_sources` (the module(s) a selected
   capability's code imports, copied into the optimizer's `./guidance/sources/`),
   `target_model`. `inputs/INPUTS.md` defines each one.
   - **Caution (issue #252):** a *relative* `optimizer_instructions_file` resolves
     project-relative under `check` but cwd-relative under `run`, which then silently
     falls back to the generic template. Write it absolute, or verify `run` actually
     picks up the customized file — intake authors it, so intake is the cheapest place
     to get it right.

## How to run
```
python scripts/run.py --base .capevolve --workdir .   # mine, then scaffold
```
The script is purely mechanical; the *judgment* — interviewing, choosing components, the
ask-if-missing loop — is yours. Then implement `adapters/adapter.py`, fill
`capevolve.yaml`, and hand off to `implement-and-check`: together the two phases are the
*full integration* (scaffold → the 3 required adapter methods → `cap-evolve check` green)
and no budget is spent until that gate passes.

> **Onboarding transcript (one example):** `examples/tau2_airline/setup.sh` clones and
> installs a benchmark and wires the adapter until `cap-evolve check` is green, and its
> `run.sh` runs the optimization. Read it only when onboarding a benchmark you have not
> integrated before.

## Good vs bad intake
- **Good:** every NEEDED input resolved to a real path or `"adapter"`; splits and budget
  chosen deliberately; each defaulted RECOMMENDED input logged; spec confirmed by the user.
- **Bad:** a synthesized tasks file that "looked plausible"; a scorer that leaks the gold
  answer into feedback; test == train with no note; a budget too small to find a gain;
  the run proceeded past a missing NEEDED input "to keep moving".

## References
- `inputs/INPUTS.md` — the binding contract: every input classified NEEDED vs RECOMMENDED
  with the path / how-to-retrieve / alternatives you must quote, plus the meaning and
  default of every spec key. Read it during the interview.
- `references/concepts.md` — why the contract is shaped this way, the 3 required adapter
  methods, split/trial/budget guidance with sources. Read it if this phase is new to you.
