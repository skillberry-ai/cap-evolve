# Optimize the capability — ship several REAL, SAFE, VERIFIED prompt fixes this iteration

{{TARGET_READER}}

{{FOCUS_SUMMARY}}

{{EMPTY_SEED}}

GOAL: raise the eval score as much as you can THIS iteration, then STOP (the harness
re-scores you — don't run evaluation yourself). The capability under optimization is
PROSE: the agent's prompt / skill text. There are no tool implementations to edit here.

Make **AS MANY real fixes as you can this iteration — solve many issues across many
trajectories, not just the biggest one.** A timid one- or two-edit iteration is an
under-used iteration: diagnose EVERY failure cluster in `./trajectories/` and ship a fix
for each one that passes the three tests below. Breadth is the goal — the more distinct
failing clusters you fix in this ONE candidate, the larger the gain.

The ONLY brake on breadth is regression: every edit must pass all three tests, because a
single speculative edit that breaks a passing task can sink an iteration of good work (it
did in prior runs). So the discipline is "many fixes, each one real and safe" — NOT "few
fixes". Do not stop at the first cluster; work through them all.

## WHAT YOU MAY EDIT — and the two ways iterations get wasted here
Edit ONLY the capability files listed in `{{CAP_BRIEF}}` below (the prompt / skill text in
this working directory). Everything else you can see is READ-ONLY CONTEXT.

**You may NOT edit the adapter, the harness, the scorer, the benchmark, or the
environment** — not to make a task pass, not to fix a broken mount or a missing binary,
not "just to unblock the run". Those files are how your score is MEASURED; changing them
does not improve the capability, and a gain obtained that way is not a result. An
iteration that edits infrastructure has produced NOTHING measurable, however green the
number looks. **If the traces show an ENVIRONMENT fault** (permission denied, missing
binary, gateway/network error, timeout, container failure — the same error on nearly every
task, unrelated to the task's content), then the correct and complete action is:
1. do NOT edit the prompt to work around it (a prose workaround for a broken environment
   is a speculative edit that fails the REAL test — the prompt is not the defect), and
2. state the diagnosis in `PROCESS.md` and `JOURNAL.md` precisely — the exact error, how
   many tasks it hit, and what a human must fix — then STOP. Handing back an accurate
   "the environment is broken, here is the evidence" is a SUCCESSFUL iteration.

**The other way iterations get wasted: another prose rule for a behavior the agent already
knows.** When the agent has the rule and skips it anyway, adding a second sentence saying
the same thing changes nothing — you must change the STRUCTURE that makes it skippable
(see the levers below): make the step unavoidable and ordered, make the contract explicit,
or give a worked example it can pattern-match. Prose is for genuine KNOWLEDGE gaps (a
fact / format / criterion the agent cannot derive) and for STRUCTURE that changes what the
agent does — not for repetition or emphasis.

## The THREE TESTS every change must pass (this is the whole game)
Before you keep any edit, confirm all three. Drop any edit that fails even one.
1. **REAL** — it targets a cluster that is FAILING in THIS iteration's `./trajectories/`
   (reward 0, partial-credit, or communication/omission). Never edit for a hypothetical
   problem, and never edit on account of a task whose failure is an environment fault.
2. **SAFE (bounded blast radius)** — the real regression question is *behavioral*:
   **would this edit change what the agent DOES on ANY currently-passing task?** Two
   blast-radius classes:
   - **BOUNDED** — an ADDITIVE rule that applies only under a stated condition present in
     the failing cases, or a clarification of an output contract the passing tasks already
     satisfy. This is the SAFE default — prefer it.
   - **UNBOUNDED** — any edit to a GLOBAL decision/permission/refusal rule, or a rewrite /
     reordering / deletion that changes the instruction the agent follows on every task. It
     changes behavior across the ENTIRE class, including tasks where the original behavior
     was the gold answer. Allowed ONLY if the new behavior is correct for EVERY task in
     that class AND you have read the currently-passing tasks in the class and confirmed
     none relied on the old wording.
   Name the passing tasks in each edit's blast-radius class and state which class it is.
   A regression wastes the whole candidate (the gate rejects a net-zero), not one task.
3. **VERIFIED** — you have shown it actually fixes its target (see VERIFY-THE-FIX). An
   edit you cannot verify is a guess — drop it.

Quality AND breadth: ship every fix that passes the three tests — the more clusters you
cover safely, the bigger the gain. The only edits to leave out are the speculative ones
(an edit that fails a test), not real fixes you ran out of patience for. Don't re-add
anything `LEDGER.md` / `JOURNAL.md` show was already tried and rejected.

## Read these first (everything is in this working directory)
- **`./guidance/<cap>/SKILL.md` for EACH selected capability — READ IT IN FULL before you
  edit; it is the MENU of improvement TYPES available to you.** For a prompt capability it
  lists the concrete kinds of change you can make (role/contract, decision-rule narrowing,
  missing-rule, worked example, ordered procedure, consolidation of conflicting text). Do
  not invent change types from memory — take them from the skill, and deliberately apply
  MULTIPLE DIFFERENT types this iteration, matching each cluster to the strongest type the
  skill describes for it.
- `./guidance/diagnose/SKILL.md` — the failure-clustering method. Use it.
- `./trajectories/` — the FULL traces of the current best candidate (the step you build
  on). The `{{FAILURES}}` block below summarizes them with argument-level feedback — read
  the actual traces for the clusters you'll fix, don't rely on the summary alone.
- `./LEDGER.md` — FACTS (read-only): every prior iteration's outcome + the exact tasks it
  broke/fixed. Your SAFE test starts here — never re-introduce a change that broke a task.
- `./JOURNAL.md` — the accumulating handover. Each entry is the optimizer's INTENT, and
  directly below it the framework stamps a **RESULT** line (objective: ACCEPTED/REJECTED ·
  Δ · the exact tasks fixed/broke). The RESULT lines — not the intent — are the truth of
  what worked: read them all before proposing. If the most recent RESULT is **REJECTED**,
  its batch was reverted; read that entry's `./prior_iterations/<id>/diff.patch`, keep the
  edits that did NOT appear in its `broke={...}`, and DROP or REDESIGN the ones that did —
  do NOT resubmit the whole rejected batch, and do NOT abandon the cluster. APPEND your new
  entry (intent only) below the marker; never edit earlier entries or re-try a refuted idea.
- `./RUNMAP.md` + `./prior_iterations/<id>/` — EVERY prior iteration's (accepted AND
  rejected) PROCESS.md + diff.patch. Read the one(s) that touched a cluster you're about to
  work on, so you build on what worked and avoid repeating what regressed.
- `./PROCESS.md` — your REQUIRED explainability file for THIS iteration (template inside).
- `./guidance/optimizer/<name>.md` — your agent's subagent/parallelism features (optional).
{{BENCH_REPO}}

## Process (do this, then STOP)
**Parallelism:** {{PARALLEL_NOTE}}
1. Read your capability SKILL(s) + the diagnose method + the cross-iteration files
   (LEDGER facts, JOURNAL handover, RUNMAP for clusters you'll touch).
2. Diagnose THIS iteration's `./trajectories/` ONLY (not stale signatures). Cluster ALL
   failures by shared root cause — total, partial-credit, AND communication/omission.
   **First separate ENVIRONMENT faults from capability failures** (see above): a cluster
   whose every trace dies on the same infrastructure error is not yours to fix.
   RANK the remaining clusters by LEVERAGE = (# failing tasks × trials × score
   recoverable), biggest first — but plan to fix ALL of them this iteration.
3. For EACH cluster, pick the strongest improvement TYPE from the capability SKILL(s)
   (cross-check the FAILURE TYPE section next) and draft the edit. Across the iteration
   use MULTIPLE different types from the skills, not the same one repeatedly. Run each
   edit through the THREE TESTS; keep it only if it passes all three.
4. Ship every passing edit together in this ONE candidate — cover as many clusters as you
   can SAFELY (that is the win), and never include an edit that fails a test.
5. Fill `PROCESS.md` and APPEND your entry to `JOURNAL.md`. STOP.

## Choose the lever by FAILURE TYPE
Pick the strongest lever your capability's edit space offers (see `./guidance/<cap>/`).
Every lever below is a PROSE edit — the point is that they are not all the same edit.

- **OUTPUT-CONTRACT / FORMAT MISS** — the work is right but the graded artifact is wrong
  (written to the wrong place, wrong shape, wrong precision, formula instead of value,
  extra cells/keys touched). **Default strong lever: state the contract exactly, once, in
  imperative form, at the point of use** — the precise path/shape/type, what must NOT be
  touched, and the one-line check the agent can run before finishing. This is the
  highest-yield, lowest-regression prompt edit; reach for it first.
- **SKIPPED / OUT-OF-ORDER STEP (behavioral)** — the agent knows the rule and skips it, or
  acts before verifying. Do NOT restate the rule. **Make it structurally unavoidable:** an
  ORDERED, numbered procedure with the step as a precondition of the next one, or a
  short pre-finish checklist the agent must satisfy — phrased as work to perform, not as
  advice to remember.
- **CAPABILITY GAP / ACTION STALL** — the agent has no reliable way to do the thing, or it
  narrates a multi-step action then never executes it. Prose CANNOT invent a missing
  capability: what it can do is supply the concrete METHOD — a worked, copyable procedure
  (the exact sequence, API/idiom, and end-to-end example) that the agent can execute
  directly. If no wording could make the task achievable, say so in PROCESS.md rather than
  shipping a hopeful paragraph; a hard zero does not move on emphasis.
- **KNOWLEDGE GAP** — a format/criterion/fact the agent genuinely cannot derive → state it
  precisely, and only it. Don't restate a rule the agent already has; that's a skipped
  step (use structure), not a knowledge gap.
- **DECISION / PERMISSION (ACT vs REFUSE)** — the agent made the wrong call on a decision
  the prompt governs. **This is the most dangerous cluster to fix wrong.** NEVER loosen,
  broaden, or alter a GLOBAL decision/permission/refusal rule — a global change (e.g.
  "restricted records MAY now be modified") flips behavior for the WHOLE class and
  regresses every currently-passing task where the stricter behavior was the gold answer
  (this exact mistake sank a prior run). Instead add an ADDITIVE rule that NARROWS: state
  the exact discriminating CONDITION that separates the qualifying cases, so only those
  change.
- **CONFLICT / BLOAT** — two instructions disagree, or the rule that matters is buried in
  prose the agent skims. CONSOLIDATE: resolve the contradiction and hoist the decisive
  rule to where it is read. Deleting is allowed here — but only text you have shown to be
  redundant or contradicted, never a rule a passing task depends on.

Also fix **recovery guidance** — what the agent should do when its own attempt errors —
when a recoverable error stranded it mid-task. High leverage, low risk.

## VERIFY-THE-FIX (do this for EACH kept edit — it satisfies the VERIFIED + SAFE tests)
A prompt edit cannot be unit-tested, so verify it against the TRACES, concretely:
- **Point at the evidence:** quote the line(s) from the failing trace that the edit
  addresses, and state what the agent would have done differently had the edit been
  present. "It would have been clearer" is not verification.
- **Contract / format edit:** confirm the value you now state matches what the SCORER
  compares (read the answer/expected artifact in the trace or the benchmark source) — not
  merely what the old prompt said. A confidently-stated wrong contract is worse than none.
- **Structural edit (ordered procedure / checklist):** confirm the skipped step is now a
  precondition of a step the agent must take, not just mentioned earlier.
- **Decision / permission edit:** the SAFE check is BEHAVIORAL. Enumerate the
  currently-passing tasks in the SAME decision class and confirm the edit would NOT flip
  the agent's action on any of them — in particular that it does not make the agent newly
  ACT where a passing task's gold answer was to refuse. If you cannot enumerate and check
  that class, the edit is UNBOUNDED and unverified — rescope it to the qualifying cases.
- **Deletion / consolidation:** name the tasks whose traces show the removed text was
  unused or contradicted, and confirm no passing trace relies on it.

Record one line per edit in PROCESS.md, e.g.
`trace <task>: wrote formula not value → contract line "write literal values"; passing <ids> already write literals`.
An edit with no verification line is unverified — verify it or drop it.

## NON-OVERFITTING (every edit must GENERALIZE)
Every edit encodes a GENERAL rule that holds across the whole class of inputs — NEVER a
literal that special-cases one task (its id, target, name, or expected answer), and never
the answer itself. ALLOWED: constants the domain defines (a fixed threshold, a required
path shape, a domain enum). Use per-task specifics and any ground-truth in the traces ONLY
to understand the failure CLASS, then write the general fix.

## Handover (REQUIRED before you STOP)
- **PROCESS.md** (this iteration): the ranked cluster list (with leverage + CONTRACT/
  STRUCTURE/KNOWLEDGE/DECISION tag), every kept edit + its lever, the VERIFY-THE-FIX +
  blast-radius line per edit, any ENVIRONMENT fault you diagnosed and handed back, what you
  deliberately skipped and why, and (if you used subagents) that you did.
- **JOURNAL.md** (append ONE entry below the marker; never edit earlier entries). Write
  INTENT only — you cannot know your gate result; the framework stamps the RESULT below
  your entry: the changes I made (1 line/edit, naming the section + cluster) · the
  EXPECTED effect + why each is safe · which prior RESULTS I built on and which regressing
  edits I did NOT re-try (cite ids) · refuted hypotheses (a prior RESULT disproved — never
  re-test) · high-value clusters not yet cracked + designs already tried · plateau signal +
  which lever to switch to · focus next iteration.

{{FAILURES}}
{{PASSING}}
{{CAP_BRIEF}}
{{ALGO_BRIEF}}

## Self-check before STOP
- Every kept edit passes the THREE TESTS (REAL, SAFE, VERIFIED) and has its
  verify + blast-radius line in PROCESS.md. Drop any that doesn't.
- You edited ONLY the capability files in `{{CAP_BRIEF}}` — no adapter, harness, scorer,
  benchmark or environment file, and no shell command that mutates the environment.
- You read each selected capability's `./guidance/<cap>/SKILL.md` and applied MULTIPLE
  DIFFERENT improvement types it describes (not the same lever repeated).
- You addressed EVERY failing capability cluster you found this iteration (not just the
  top few), and separated out any ENVIRONMENT-fault cluster with its diagnosis handed back.
- No edit is a restatement of a rule the agent already has: every behavioral cluster is
  fixed by STRUCTURE (ordered/unavoidable step, explicit contract, worked example), not by
  another sentence of emphasis.
- For DECISION / PERMISSION clusters you did NOT loosen or alter a global decision/
  permission/refusal rule; you added the discriminating CONDITION and confirmed it does
  not flip the action on any passing task in the class.
- Every edit is ADDITIVE knowledge or structure the agent lacked — never a change to a
  decision the agent currently gets right — and any deletion is text you showed is unused.
- No edit hardcodes a task-specific id/value/date/answer, or the expected answer itself.
- PROCESS.md + JOURNAL.md are filled. Keep narration minimal; don't restate these
  instructions or explore unrelated files.
