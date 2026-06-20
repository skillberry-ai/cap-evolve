# Optimize the capability — make the largest improvement you can this iteration

{{FOCUS_SUMMARY}}

GOAL: maximize the eval score. Make the biggest, most generalizing improvement you
can this iteration. The prompt AND the tools are EQUALLY fair game — pick whatever
fixes the most failure clusters. Then STOP (the harness re-scores you; don't re-run
evaluation yourself).

EFFORT: scale your analysis depth and effort to the number and difficulty of the
failing trajectories. Few, easy failures → still address each one. Many or
hard failures → go deeper; if your agent supports parallel sub-agents / worktrees
(see `./guidance/optimizer/<name>.md`), spawn one per cluster to analyze concurrently,
then synthesize.

## STEP 0 — read before analyzing
Before you look at ANY trajectory or begin diagnosis, READ IN FULL:
- `./guidance/<cap>/SKILL.md` for EVERY selected capability — the edit space, the
  worked examples, the boundaries. (There may be more than one capability; read each.)
- `./guidance/optimizer/<name>.md` — YOUR OWN agent's feature doc (subagent /
  parallelism / worktree mechanics). You will need it for the two-phase plan below.
Do NOT begin diagnosis until you have read these in full. Skipping STEP 0 is how
prior iterations missed the in-code fix path and shipped prose-only patches.

## Read these first (everything is in this working directory)
- `./guidance/<cap>/SKILL.md` — the capability skill(s) you may edit. WHAT YOU CAN
  CHANGE is listed there, with worked examples and edit boundaries. Read it first.
- `./guidance/sources/` — supporting source files (data models / types the tools
  import). Read them before writing tool code so your code is correct.
- `./guidance/diagnose/SKILL.md` — the failure-clustering METHOD (reflective dataset,
  group failures by shared signature). Use it.
- `./guidance/optimizer/<name>.md` — your agent's subagent/parallelism/worktree doc.
- `./trajectories/` — the FULL, unmodified traces of the current best candidate's most
  recent evaluation (the step you build on). Your ground truth — don't rely on the
  short feedback lines alone.
- `./MEMORY.md` — accepted history + approaches that regressed (with per-task impact).
- `./STATE.md` — your scratchpad + handover; it carries across accepted iterations.
{{BENCH_REPO}}

## Process (do this, then STOP)
1. STEP 0 above (read SKILL.md for every capability + your optimizer's feature doc).
2. Read the current capabilities, the guidance above, and MEMORY/STATE to understand
   what has happened so far.
3. Analyze THIS step's trajectories in `./trajectories/` with the diagnose method.
   Find the MANY recurring issues — total failures (reward 0), partial-credit failures
   (graded between 0 and 1), and communication/omission failures (the agent did the
   work but failed to report or confirm it). Also note GOOD-but-INCONSISTENT behaviors
   (pass on some trials, fail on others) to make consistent. Name each cluster, its
   tasks, and its shared cause; biggest first.
4. Fix MANY root causes in this ONE candidate (see the mandate below). Address EVERY
   failure cluster you found, not just the biggest.
5. Write a short handover in `STATE.md` (sections below), apply the edits, and STOP.

## Fix MANY root causes — the DEFAULT fix is IN-CODE, in EXISTING tools
For each cluster, ask: "Is the agent VIOLATING a rule/precondition/formula that the
tools already imply?" If yes (the common case), the DEFAULT fix is to move that rule
INTO THE CODE BODY of the EXISTING tool it governs — an in-body validation /
normalization / computation that raises an ACTIONABLE error (telling the agent exactly
what to do) or returns the corrected value. Do NOT restate the rule in a docstring or
the prompt and call it fixed: a rule the agent can already read but breaks will keep
being broken until the code enforces it.

**Editing the CODE of MANY existing tools is the expected shape of a strong iteration;
adding one new tool while leaving rules as prose is the failure mode this instruction
prevents.** Prose / docstring / prompt edits are reserved for genuine KNOWLEDGE gaps —
a format, criterion, or fact the agent CANNOT derive from what it already has. Rule
VIOLATIONS go in code; KNOWLEDGE gaps go in prose.

A strong iteration ships, together: (a) for each rule-violation cluster, an in-body
guard added to the EXISTING tool that governs it (validate/normalize/compute → raise
an actionable error or return the fixed value); (b) where a behavioral cluster needs a
new safe path, a validation/workflow/composite tool with REAL code (then REMOVE_TOOLS
the raw primitive via the safe wrapper-swap); (c) enriched tool RETURN values +
actionable error messages so the agent can recover; (d) corrected tool code where a
handler is wrong; (e) sharpened docs / prompt rules ONLY for genuine knowledge gaps.
Ground every change in the trajectories; never drop a needed rule
(change/consolidate/add — don't delete). Build on the current best (keep its wins).

## Two-phase parallel work
Use your agent's subagent/worktree features (`./guidance/optimizer/<name>.md`) to do
this in two fan-out phases, then MERGE.

- **Phase 1 — DIAGNOSE (read-only, parallel).** Fan out one read-only subagent per
  trajectory-group / failure-cluster; each finds its issues concurrently and reports
  back. The MAIN agent assembles a single MASTER ISSUE LIST (each issue: cluster,
  governing tool, is-it-a-rule-violation, intended fix class).
- **Phase 2 — IMPLEMENT (parallel).** Fan out one subagent per ISSUE. Each makes its
  ONE targeted edit — preferably an EXISTING-tool-body guard, else a new tool or a
  prose edit (knowledge gaps only). If edits would collide on the same file, give each
  subagent its OWN worktree. The MAIN agent then MERGES every subagent's edit into ONE
  candidate (resolve conflicts, keep all the guards), updates STATE.md, and STOPs.

See `./guidance/optimizer/<name>.md` for the exact subagent / worktree mechanism your
agent provides.

## Steering — protect the wins, don't freeze
Use the "Currently PASSING" block and the "Per-task impact of prior candidates" block
(appended below) as STEERING, not as a reason to avoid editing:
  - Don't re-introduce a change that BROKE a passing task (a task a prior candidate
    dropped from passing). For each currently-passing task, make sure your edit doesn't
    change the code path / rule / tool it exercises.
  - A net gain that breaks as many tasks as it fixes is rejected — protect the passing
    set, but keep editing boldly everywhere else.
  - Non-regression is a design constraint on each INDIVIDUAL fix (scope each in-body
    guard so it only fires on the violating inputs, not on a passing task's path) — NOT
    a reason to make fewer fixes. Many well-scoped in-code guards that each protect the
    passing set is the target; one timid fix is a failure.

## Handover
Your `STATE.md` MUST end with:

    ## Handover for next iteration
    - Approaches tried this iteration (1 concrete line each):
    - Lessons learned (general):
    - Recommendation / what to focus on next:
    - Rules still living as prose that SHOULD become in-code checks next iteration:
    - Approaches that regressed AS IMPLEMENTED (a better-designed version may still
      work — don't permanently abandon a high-value cluster):

{{FAILURES}}
{{PASSING}}
{{CAP_BRIEF}}
{{ALGO_BRIEF}}

## Self-check before STOP
Before finishing, count your changes:
  - If you edited the CODE BODY of fewer than ~3 EXISTING tools, OR converted fewer
    than half the rule-violations you found into in-code checks, you UNDER-USED the
    iteration — go back and convert more. **New tools and docstring/prompt edits do NOT
    count toward this bar** (they are tracked separately); only edits to the BODY of an
    EXISTING tool count.
  - Restate the goal: fix as MANY clusters as possible THIS iteration for a large gain.
    Address the remaining clusters from your STATE.md list before you stop.
Keep narration minimal; don't restate these instructions or explore unrelated files.
