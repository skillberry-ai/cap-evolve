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

If `./trajectories/` include ground-truth / expected actions / a reward breakdown
(some benchmarks copy these into the traces; you will NOT always have them), USE
them to localize the exact defect — which action / argument / value was expected vs
what the agent did. Ground truth is for UNDERSTANDING the failure class only; keep
your fix GENERAL (see the non-overfitting guardrail below) — never copy a gold
value into the prompt or tool code.

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
   Diagnose against THIS candidate's CURRENT trajectories ONLY — never against past
   clusters, prior-iteration notes, or stale signatures. The failures you fix must be
   the ones present in the traces in front of you. Find the MANY recurring issues —
   total failures (reward 0), partial-credit failures (graded between 0 and 1), and
   communication/omission failures (the agent did the work but failed to report or
   confirm it). Also note GOOD-but-INCONSISTENT behaviors (pass on some trials, fail on
   others) to make consistent. Name each cluster, its tasks, and its shared cause.
   RANK clusters by (# failing tasks × trials) — failure frequency — and spend effort
   top-down; the cluster that fails the most task×trial cells is worth the most.
   Do NOT add a guard for a cluster whose tasks already PASS in the current best
   (check the "Currently PASSING" block) — diagnosing a stale/already-passing cluster
   wastes the iteration and risks regressing a passing task. Every fix must target a
   task that is FAILING in the current trajectories.
4. Fix MANY root causes in this ONE candidate (see the mandate below). Address the
   ranked clusters top-down — start with the highest (# tasks × trials) cluster — and
   cover as many as you can, not just the biggest.
5. VERIFY each fix against the failing trace it targets (the VERIFY-THE-FIX gate below).
6. Write a short handover in `STATE.md` (sections below), apply the edits, and STOP.

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

## NON-OVERFITTING GUARDRAIL (every edit must GENERALIZE)
Every prompt/tool edit must encode a GENERAL rule/policy/validation that holds
across the whole CLASS of inputs — NEVER hardcode a literal that matches or
special-cases a SINGLE task (its specific id, target, name, or expected answer). A
guard must fire on the GENERAL condition (e.g. "payment_id not in the user's
profile", "reservation already flown", "amount not a multiple of the unit"), NOT
match a task-specific literal (NOT `if destination == "SEA"`, NOT
`if reservation_id == "ABC123"`, NOT returning a particular task's answer). A change
that only helps one task (a literal special-case) is FORBIDDEN — it overfits, gets
rejected by the held-out gate, and hurts other tasks.
ALLOWED (not overfitting): constants the GENERAL policy/domain defines — the current
date the policy states (e.g. `datetime(2024, 5, 15)` when the policy says "today is
…"), a fixed threshold/limit/fee, or an enum the domain defines. Encode those freely;
they apply to every task. The line is: task-specific literal (forbidden) vs
policy-defined constant (fine). Use any per-task specifics (and any ground-truth in
`./trajectories/`) ONLY to understand the failure CLASS, then write the general fix.

## VERIFY-THE-FIX gate (MANDATORY — do this for EACH fix before you finish)
A fix that does not change the failing trace is not a fix. For EACH fix, before
finishing, RE-CHECK it against the failing trace it targets: run the governing tool's
body (or a minimal harness around it) on the EXACT arguments taken from that
trajectory, and confirm your guard FIRES (raises the actionable error) / your
computation returns the corrected value / your composite executes the eligible-action
batch. If the guard does NOT trigger on the failing inputs (e.g. a precondition check
whose condition is never true for the failing task, a normalization that leaves the
bad value unchanged), it is dead code — DROP it or REDESIGN it until it fires on the
real trajectory. Do not ship a guard you have not seen fire on the trace it is for.

Record per fix in STATE.md, one line each, e.g.:
  - `trace <task-id> arg <x>=<bad-value> → guard now raises "<actionable msg>"`
  - `trace <task-id> arg <x> → computation now returns <corrected-y> (was <wrong>)`
A fix with no such verification line is not done.

## Two-phase parallel work — and you MUST leave a trace that it happened
Use your agent's subagent/worktree features (`./guidance/optimizer/<name>.md`) to do
this in two fan-out phases, then MERGE. **Do not describe a process that leaves no
trace.** STATE.md MUST record evidence the fan-out actually ran:

- **Phase 1 — DIAGNOSE (read-only, parallel).** Fan out one read-only subagent per
  trajectory-group / failure-cluster; each finds its issues concurrently and reports
  back. The MAIN agent assembles a single MASTER ISSUE LIST (each issue: cluster,
  governing tool, is-it-a-rule-violation, intended fix class). **Record the MASTER
  ISSUE LIST in STATE.md** — that list is the phase-1 evidence.
- **Phase 2 — IMPLEMENT (parallel).** Fan out one subagent per ISSUE. Each makes its
  ONE targeted edit — preferably an EXISTING-tool-body guard, else a new tool or a
  prose edit (knowledge gaps only). If edits would collide on the same file, give each
  subagent its OWN worktree. The MAIN agent then MERGES every subagent's edit into ONE
  candidate (resolve conflicts, keep all the guards), updates STATE.md, and STOPs.
  **Record, per issue, the edit made and how it was merged** — that is the phase-2
  evidence.

**If you CANNOT reliably fan out** (your agent lacks subagents/worktrees, or the
fan-out did not run), you MUST instead, in the main agent: diagnose ALL failing tasks
individually, RANK the clusters by (# failing tasks × trials), then fix the top-N —
and SAY SO explicitly in STATE.md ("fan-out unavailable; diagnosed N failing tasks
serially, ranked, fixed top-K"). Never claim a two-phase fan-out you did not run.

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

    ## Diagnosis + fan-out evidence
    - Clusters ranked by (# failing tasks × trials), top-down:
    - Two-phase evidence: phase-1 MASTER ISSUE LIST + phase-2 per-issue edits/merges
      (or: "fan-out unavailable; diagnosed N tasks serially, ranked, fixed top-K"):
    - VERIFY-THE-FIX, one line per fix (trace <task> arg <x> → guard raises/returns <y>):

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
  - EVERY fix has a VERIFY-THE-FIX line in STATE.md proving the guard fires / the
    computation returns the corrected value on the EXACT failing-trace arguments. A fix
    without a verification line is unverified — verify it or drop it.
  - Every fix targets a cluster that is FAILING in the CURRENT trajectories (ranked by
    # tasks × trials), not a stale/already-passing one.
  - Self-check: does any edit hardcode a task-specific id/value/date/answer? If so,
    generalize it or drop it.
  - STATE.md records the two-phase evidence (master issue list + per-issue edits), or
    explicitly says fan-out was unavailable and the serial fallback was used.
  - Restate the goal: fix as MANY clusters as possible THIS iteration for a large gain.
    Address the remaining clusters from your STATE.md list before you stop.
Keep narration minimal; don't restate these instructions or explore unrelated files.
