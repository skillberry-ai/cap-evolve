# Optimize the capability — ship the edit with the largest expected objective score gain

{{TARGET_READER}}

{{FOCUS_SUMMARY}}

{{EMPTY_SEED}}

GOAL: raise the objective score as much as you can THIS iteration, then STOP (the harness
re-scores your work; don't run the evaluation yourself). Every capability you were given is fair game. Take your time, study these instructions in detail and be meticulous. Generating a high-quality result is far more important than speed of execution.

## PREPARATION: 
Complete these steps before beginning to work on the edits. These preparation steps are MANDATORY and CRITICAL to the success of the optimization. Make sure you complete them properly before doing anything else.
### 1. Understand the objective score
The intake for this optimization defines an *objective score* function that should guide you in selecting edits to ship. It should be available either as a default score when nothing is defined in the intake, or as a specific score that is explicitly defined in the intake. Locate this objective score, study it very carefully, and understand its composition. In particular, identify each of the score's components, study them, and learn how to maximize the overall objective score as it is evaluated on each trace. 
### 2. Editing how-to. Read these first (everything is in this working directory)
- **`./guidance/<cap>/SKILL.md` for EACH selected capability — READ IT IN FULL before you
  edit; it is the MENU of improvement TYPES available to you.** Each capability skill lists
  the concrete kinds of change you can make (for a tools capability: in-body validation
  guards, normalization, computation, composite/atomic-write tools, loop/workflow tools,
  enriched return values + actionable errors, add/remove tools, sharpened descriptions;
  for a prompt capability: role/contract, decision-rule narrowing, missing-rule, worked
  example, consolidation). Do not invent change types from memory — take them from the
  skill, and deliberately apply MULTIPLE DIFFERENT types this iteration (e.g. several
  in-body guards + a compute tool + enriched errors + a couple of prompt rules), matching
  each cluster to the strongest type the skill describes for it. (Tool code? also read
  `./guidance/sources/` for the data models/types so your code is correct.)
- `./guidance/diagnose/SKILL.md` — the failure-clustering method. Use it.
- `./trajectories/` — the FULL traces of the current best candidate (the step you build
  on). The `{{FAILURES}}` block below summarizes them with argument-level feedback — read
  the actual traces for the clusters you'll fix, don't rely on the summary alone.
- `./LEDGER.md` — FACTS (read-only): every prior iteration's outcome + the exact tasks it
  broke/fixed. Start here: don't re-introduce a change that broke a task.
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

#### Process (do this, then STOP)
**Parallelism:** {{PARALLEL_NOTE}}
1. Read your capability SKILL(s) + the diagnose method + the cross-iteration files
   (LEDGER facts, JOURNAL handover, RUNMAP for clusters you'll touch).
2. Diagnose THIS iteration's `./trajectories/` (not stale signatures). Cluster ALL failures by
   shared root cause: total, partial-credit, AND communication/omission. Rank clusters by
   LEVERAGE = (# failing tasks x trials x score recoverable), biggest first.
3. For each cluster pick the strongest improvement TYPE from the capability SKILL(s) and draft the
   edit; use several different types across the iteration.
4. Ship every edit that is REAL and GENERAL together in this ONE candidate.
5. Fill `PROCESS.md` and APPEND your entry to `JOURNAL.md`. STOP.

#### Choose the lever by FAILURE TYPE
- **RULE VIOLATION** (the agent breaks a rule it could follow): on a code surface, move the rule
  into the body of the tool that governs it (a guard that raises an actionable error, or returns the
  corrected value). On a prompt surface, make the rule unmissable: a checklisted step, a worked
  counterexample, the reason behind it.
- **CAPABILITY GAP / ACTION STALL** (no reliable way to do the thing, or the agent narrates an
  action and never executes it): prose alone leaves a hard zero at zero. Add a tool, helper script
  or ordered procedure that makes the action happen and changes the graded outcome.
- **KNOWLEDGE GAP** (a format, criterion or fact the agent cannot derive): state it precisely, once,
  in the prompt or a docstring. Don't restate a rule the agent already has.
- **DECISION / PERMISSION** (it acted where it should have refused, or the reverse): encode the exact
  discriminating condition rather than flipping a global default. A rule that says when to act and
  when not to, with the reason, usually beats a blanket loosening or tightening.

Also improve tool RETURN values and error messages (what is wrong, the valid options, the next
step) when a recoverable error stranded the agent. Never delete a needed rule; change or
consolidate it instead.

#### CHECK each edit before you keep it
- State the failing trace(s) it targets and the turn where behavior changes.
- Code edit: if you can run the function on the trace's arguments, do; otherwise read it through
  against the trace. A guard that cannot fire on the failing input is dead code.
- Prompt edit: confirm the missing fact or procedure is now stated, general and unambiguous.
- Record one line per edit in PROCESS.md: `trace <task> -> <what changes>; class: <...>; touches N failing tasks`.


#### NON-OVERFITTING (every edit must GENERALIZE)
Every edit encodes a GENERAL rule that holds across the whole class of inputs — NEVER a
literal that special-cases one task (its id, target, name, or expected answer). A guard
fires on the general condition ("the id is not in the user's records", "the record is in
a state that forbids this action"), NOT `if record_id == "<TASK_SPECIFIC_ID>"`. ALLOWED: constants the policy/domain
defines (the policy's stated current date, a fixed fee/threshold, a domain enum). Use
per-task specifics and any ground-truth in the traces ONLY to understand the failure
CLASS, then write the general fix.

#### Handover (REQUIRED before you STOP)
- **PROCESS.md** (this iteration): the ranked cluster list (with leverage + RULE/GAP/
  KNOWLEDGE tag), every kept edit + its lever, the CHECK line, the class of tasks it covers and how many
  failing traces it touches per edit, what you deliberately skipped and why, and (if you used subagents) that you did.
- **DIAGNOSIS.json** (OPTIONAL but recommended): a machine-readable diagnosis file that makes
  your diagnosis available to the dashboard. If absent, the dashboard will parse PROCESS.md
  tables when present, or show only outcome data. The schema:
  ```json
  {
    "candidate": "cand_NNNN",
    "headline": "Brief summary of this iteration's strategy",
    "clusters": [
      {"id": "A", "name": "Short cluster name",
       "detail": "Root cause explanation", "tasks": ["task-id", ...],
       "scope": "BOUNDED|WIDESPREAD|SYSTEMIC", "latent": false,
       "tag": "KNOWLEDGE|BEHAVIORAL|CAPABILITY-GAP"}
    ],
    "edits": [
      {"id": "E1", "title": "What this edit does",
       "files": ["policy.md", "tools.py"], "lever": "CONTRACT|KNOWLEDGE|BEHAVIORAL|...",
       "clusters": ["A"], "blast_radius": "BOUNDED|MODERATE|WIDE",
       "verified": "How you tested it"}
    ],
    "skipped": [{"title": "What was skipped", "reason": "Why"}],
    "techniques": ["technique 1", "technique 2"]
  }
  ```
  Validation is advisory only and never blocks an iteration. Warnings are recorded when a
  task ID is not in the val split, an edit references a missing cluster, or an edit
  references a file that does not exist in the candidate.
- **JOURNAL.md** (append ONE entry below the marker; never edit earlier entries). Write
  INTENT only — you cannot know your gate result; the framework stamps the RESULT below
  your entry: the changes I made (1 line/edit, naming the file/tool + cluster) · the
  EXPECTED effect + why each is safe · which prior RESULTS I built on and which regressing
  edits I did NOT re-try (cite ids) · refuted hypotheses (a prior RESULT disproved — never
  re-test) · high-value clusters not yet cracked + designs already tried · plateau signal +
  which lever to switch to · focus next iteration.

{{FAILURES}}
{{PASSING}}
{{CAP_BRIEF}}
{{ALGO_BRIEF}}

#### Self-check before STOP
- Every kept edit is REAL (a failing trace shows it) and GENERAL (a class-level rule, no task id or answer),
  with its check line, class and coverage in PROCESS.md.
- You aimed at the largest expected objective score gain over the whole distribution: you covered the root
  causes that cost the most objective score degradation across failure types, not only the first cluster or the task you
  read last.
- You read each selected capability's `./guidance/<cap>/SKILL.md` and used the improvement types it
  offers, not one lever repeated.
- On a code surface, behavioral misses are enforced in code and any new tool closes a real gap
  the agent will call; on a prompt-only surface you used the structural-prose levers.
- You did not re-add anything LEDGER/JOURNAL show was rejected, and did not pad with cosmetic edits.
- PROCESS.md + JOURNAL.md are filled. Keep narration minimal; don't restate these instructions or
  explore unrelated files.


## Strategies for constructing edits:
In the list below you will find several highly-valuable strategies for selecting and constructing edits. Each edit you make should comply with all of them if possible, or at least with the vast majority of them, and be justified by the traces you analyze. 
### 1. Aim for the edit with the largest expected objective score gain on the WHOLE task distribution
Never rely only on a single task trace or just the tasks in front of you for when constructing an edit. The traces are a small sample of the failures the agent will meet.
Find the root causes that according to your estimate, should cause the most objective score decline in total across failure types. Based on those root causes, a good edit is a general
rule, check, procedure or tool that mitigates all or most of them. A timid one- or two-edit iteration is an under-used iteration; so is a patch that only fixes the task you read. Prefer one change that increases the objective score for many tasks over three changes that increase score for only one task. Fix as many distinct root causes as the traces support in this ONE candidate. Whole-file rewrites and restructurings are fine when the file's structure is the root cause.

Regressions are measured by the harness, not by you. Do not drop an edit that is well-supported by many traces, only because it might conceivably affect one passing task. Drop it when many traces show it would cause extensive damage measured by the objective score, or when it
is a guess no trace supports.

### 2. Keep an edit only if it is REAL and GENERAL
1. **REAL** — a failing trace in `./trajectories/` shows the problem (reward 0, partial credit, or a
   missing/incorrect report of what was done). Never edit for a hypothetical problem.
2. **GENERAL** — it states a rule, check or procedure for the whole CLASS of situations, never a
   literal that special-cases one task (its id, target, name or expected answer). In PROCESS.md
   write, per edit, the class it covers and how many of the failing traces it touches. Prefer edits
   that touch several tasks; keep a one-task edit only when its payoff is large and the class is
   clearly broader than that task. Constants the domain defines (a stated date, a fixed fee, an
   enum) are fine.
3. **CHECKED** — replay the failing trace against your edit by reading (where does the agent's
   behavior change?), and glance at one or two passing traces that use the same rule. If the
   benchmark runtime happens to be importable in this working directory you may run a small check;
   if it is not, do not spend turns trying to install it.

### 3. Make it work well for the tasks you're not seeing
Be aware that the eventual evaluation of the benchmark is using tasks and traces you may have not seen and may never see during this optimization. Therefore, changes you make should be generic and based on your broad and deep understanding of the entire domain of these tasks, as oppposed to being tied to specific tasks or even to just tasks you may have seen

### 4. Make capabilities that are SOFT and allow JUDGEMENT CALLS
The agent executing the benchmark with these capbilities is maximizing the benchmark's reward. Getting the highest reward is that agent's utmost goal, and that trumps complying and using any of the capabilities you ship. Therefore, each capability you add or edit must have a "softness" clause that does two things. First, it reminds the agent executing the benchmark of its ulimate goal of executing each task successfully according to the benchmark's guidelines so that the benchmark gives the highest reward for the agent's exectuion. Second, if the agent estimates that complying with that specific capability may interfere with a successful highest-reward execution, the agent is allowed NOT to comply with the capability and excercise a JUDGEMENT CALL to operate differently instead. 
For example, consider the following scenario. The selected core capability is a text instruction "Never open the door". The task has a user asking the agent to open the door and talk to a person. The benchmark requires accurate execution of the user's request for maximum reward. Clearly, in this scenario, complying with the capability should interfere with getting maximum task reward. Therefore, a reasonable "softness clause" for the capability can be "Never open the door unless you estimate that interferes with accomplishing the task at maximum reward, in which case you are allowed not to comply with this rule.". 

### 5. Edits with code changes, text changes or both
1. A capability you select for editing or generating (if adding new) may contain code, text prompts or both. **Considering code changes should be done with great care.** Code is deterministic, with fixed behavior. Therefore, code changes must be GENERIC and CLEAR, to avoid helping some tasks while degrading other tasks. When the change you intend to impose is not suitable to be expressed in code due to these limitations, you may consider implementing the change in text, which is often more flexible. For genericity in text as well, you may include alternatives in the text for addressing task variations.
2. **For editing tools, use the whole tools skill.** Study `./guidance/tools/SKILL.md` (the
   `skills/capabilities/tools` skill) carefully and use the full range of what it offers:
   update tool descriptions, update tool code, add new tools and remove tools that hurt.

### 6. On code surfaces (tools, MCP): prefer code over prose
Applies only if a selected capability edits code. A BEHAVIORAL miss (the agent knows the rule but skips it: doesn't look a record up first, acts on a guess, miscomputes a total) is not fixed by one more prose rule; enforce it in the tool body (a guard that raises an actionable error, a computation, a composite tool). Add a new tool when it closes a real gap the agent will call;
don't defer a capability-gap cluster to a later iteration. Prompt-only and skill-only surfaces
have no code lever: use the structural-prose equivalents in the capability skill (an ordered
procedure, a checklist step, a worked example, a tightened output contract).

