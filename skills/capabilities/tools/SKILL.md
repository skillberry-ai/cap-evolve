---
name: tools
description: Optimize an agent's OWN tool surface (tools it implements, not an external MCP server). Use when the agent mis-selects tools, fills arguments wrong, or has a confusing/redundant toolset. You may edit tool names, descriptions, parameter docs, in-description examples, the JSON schema/API, the tool code itself, ADD tools (including composite tools that call existing tools), and REMOVE tools — all under an action policy so risky edits can be locked off.
component: capability
argument-hint: "--path DIR"
allowed-tools: Read, Write, Edit, Bash
provides: [candidate]
needs: []
sources: [gepa, tau2bench]
---

# Capability: tools (full control)

This capability treats the agent's **entire tool surface as the optimizable
artifact**. When an agent *owns* its tools — it implements the handlers, defines
the wire schema, and controls every caller — then names, descriptions, parameter
docs, in-description examples, the JSON Schema, *and the implementation code* are
all fair game.

Use this capability when the agent OWNS its tools — it implements the handlers and
controls the wire schema, so the code itself is editable. (When the tools come from an
external server you can only re-describe, not re-implement, the action policy here is
tightened to documentation-only edits.)

## What you can change here

**The tool's docstring AND its return value are what the agent SEES — make both
clear and recovery-oriented.** The doc surface (description, important-notes,
per-param, `Raises:`, examples) drives *which* tool the model calls and *how* it
fills the arguments; the return value (and especially the error text) steers the
*next* turn. Each lever below is an edit class; in ONE pass, apply EVERY edit class
the traces call for — a validation wrapper AND a loop tool AND enriched
returns/errors AND doc fixes across all implicated tools can and should all ship in
the same candidate. (1-line generic examples; worked bodies in
[`references/examples.md`](references/examples.md), depth below and in
[`references/concepts.md`](references/concepts.md).)

**Read this skill in full before editing. Ship MULTIPLE fixes per iteration — but
every one must be REAL (targets a currently-failing task), SAFE (cannot change a
passing task's behavior), and VERIFIED (proven to fix its target).** Several such fixes
beat a long list that includes a speculative edit: one edit that regresses a passing
task can sink the whole candidate at the gate. Quality over churn — never add an edit
to hit a count, and never re-add a rule/tool the run already tried and rejected.

**Per-change SAFETY (the rule that makes multi-change work).** Scope every guard to fire
ONLY on the exact violating condition, and check its blast radius: run it on the args of
1–2 currently-PASSING tasks that use the same tool and confirm it does NOT fire. A guard
that fires on a passing task is a regression — rescope or drop it. This is how you ship
many changes without net-zero churn.

**Pick the lever by failure type — the in-body guard is the DEFAULT strong move:**
- **Edit the BODY of an EXISTING tool (reach for this FIRST for a rule violation).** When
  the agent VIOLATES a rule a tool already owns (a wrong field value, an id not on file,
  an action on a record whose state forbids it), convert the prose rule into a scoped
  in-body guard. This is the highest-yield, lowest-regression edit; expect to touch
  SEVERAL existing bodies in one iteration.
- **ADD a NEW code-bearing tool — for a genuine CAPABILITY GAP or action STALL.** A
  composite atomic-WRITE tool for a multi-step action the agent narrates/confirms then
  fails to execute is the canonical case (the primitive is what it skips; the composite
  makes the action un-skippable; then REMOVE the raw primitives). New tools are
  available and encouraged WHEN they close a real gap — but add one ONLY if the agent
  will actually call it AND it changes the graded outcome. Do NOT add read/compute/summary
  helper tools that a guard or a prompt line would subsume, and never add a tool just to
  "ship a new tool" — that is churn the gate punishes.

- **DECISION / PERMISSION cluster → a discriminating-predicate guard (the BOUNDED-blast-
  radius alternative to a prompt change).** When a cluster is about ACT-vs-REFUSE (the
  agent acted where it should have refused/escalated, or vice versa), the WRONG fix is
  loosening a global decision rule in the prompt — that has UNBOUNDED blast radius and
  regresses every task where the original behavior was gold. The RIGHT fix lives here:
  an in-body guard on the tool that owns the action, expressing the EXACT policy
  predicate, that refuses/raises ONLY when the qualifying condition is/isn't met. It
  fires only on the narrow violating condition, so its blast radius is bounded to the
  failing inputs — the SAFEST edit, preferred over any prompt/permission change.
- **HARD-ZERO / capability-gap cluster → a REAL targeted tool, never prose.** A task
  scoring 0.00 that needs a compute / composite / discriminating-predicate tool stays
  0.00 after any docstring or prompt reword. Ship a tool the agent will CALL that
  changes the graded state.

The two failure modes to avoid: (1) leaving a rule the agent keeps breaking as loose
prose instead of a guard, or loosening a global permission rule (unbounded regression)
instead of a scoped guard; (2) padding the candidate with low-value helper tools or
cosmetic rewrites that move no graded task.

1. **Edit the CODE of EXISTING tools to enforce rules deterministically (the most
   common high-leverage edit)** — most violated textual rules govern a tool that
   ALREADY exists, and the fix is an in-body guard *there*, not a new tool. Bake the
   precondition / normalization / actionable refusal into the body so correctness
   doesn't depend on the LLM. *Ex:* add `if not rec["cancellable"]: raise
   ValueError("not cancellable; reason=...; do X instead")` to the existing
   `cancel_record` body. Expect to touch the BODIES of SEVERAL existing tools per
   iteration — one per violated rule.
2. **Add a new tool (first-class — reach for it freely)** — give the agent a
   capability it lacks or a safe path it keeps skipping, built as a thoughtful
   workflow/validation tool, not a thin wrapper. *Ex:* `search_logs` returns only
   the relevant lines instead of a raw dump; or a `find_duplicate_records` the agent
   has no way to compute today. For a STALL or capability-gap cluster this is the
   right move even when a primitive exists — see item 7 (composite atomic-WRITE).
3. **Replace / wrap a tool** — superset an existing tool and route the old behavior
   through it. *Ex:* wrap `find_record`+`charge_payment` behind one
   `charge_record(record_id)` that resolves then charges.
4. **Improve a tool's documentation** — sharpen description / important-notes /
   `Raises:` / per-param docs / examples; rename for least surprise. *Ex:*
   `lookup(record)` → `get_record(record_id: str)` with "returns an error object if
   not found."
5. **Improve RETURN VALUES for recoverability** — high-signal fields, stable
   human-readable ids, and **actionable error text with a next-step hint and what
   NOT to do**. *Ex:* error returns "payment method not on file; available:
   ['card_1'] — pass one of these" instead of a raw traceback.
6. **Add a loop tool** — replace N repeated single-item calls with one list call.
   *Ex:* `get_records(ids: [...])` replaces N× `get_record(id)`.
7. **Add a composite atomic-WRITE / workflow tool (first-class — the fix for STALLS
   and multi-step writes)** — for a recurring, failure-prone multi-step action
   (especially one the agent narrates/confirms then fails to execute, e.g. a
   multi-step update that must cancel/undo then re-create a record), a deterministic
   tool whose body performs ALL the steps in order via the
   existing primitives, then `remove` the raw primitives so the action is
   un-skippable. *Ex:* `apply_change_plan(record_id, steps)` validates → applies each
   → returns final state as one reliable call. Reach for this whenever a cluster
   STALLS at the action boundary — do not settle for a prose "be sure to act" rule.
8. **Remove-with-replacement** — remove a redundant/overlapping tool *only* after a
   replacement preserving its capability exists. *Ex:* drop `query` once
   `get_record` + `search_records` cover it.

**Before/after — convert a violated prose rule into an in-body guard (the default
edit).** The rule "a record can only be cancelled when it is cancellable" lives as
prose in the prompt and the agent keeps breaking it. Don't add a tool — edit the
EXISTING `cancel_record` body:

```diff
  def cancel_record(record_id):
+     rec = get_record(record_id)
+     if not rec["cancellable"]:
+         raise ValueError(
+             "not cancellable; reason=" + rec.get("status", "unknown")
+             + "; do X instead (e.g. offer a change_record)")
      return _backend.cancel(record_id)
```

And the rule "amounts are in whole cents and the method must be on file" — edit the
EXISTING `book` (or `charge`) body to normalize the field then raise an actionable
error:

```diff
  def book(record_id, amount, payment_id):
+     amount = int(round(amount))            # normalize: callers pass dollars
+     methods = {m["id"] for m in get_record(record_id)["payment_methods"]}
+     if payment_id not in methods:
+         raise ValueError(
+             f"payment method {payment_id!r} not on file; "
+             f"available={sorted(methods)} — pass one of these")
      return _backend.book(record_id, amount, payment_id)
```

Both fixes touch a tool that ALREADY exists; no new tool is needed. A docstring-only
or new-tool-only iteration that leaves these rules as prose is under-used.

**Guardrails (depth below):** encode deterministic logic in code, not prose (a
tool body the model cannot skip beats a sentence it can forget); keep the toolset
small and namespaced (aim **< ~20** active tools); ship correct, bug-free code
(every code edit needs validation + a `validate` run); and **never remove a tool
without a capability-preserving replacement** (add → verify → swap, see the SAFE
TOOL-REPLACEMENT PROTOCOL).

**Generalize, never hardcode.** Every in-code guard must fire on the GENERAL
condition that defines the failure class, never on a literal value from one task.
*Good:* `if payment_id not in user_payment_methods: raise ...`. *Bad:*
`if record_id == "<TASK_SPECIFIC_ID>": raise ...` — that overfits to one task, gets
rejected by the held-out gate, and helps nothing else. Use a failing task's
specifics only to identify the class, then write the general check.

A discriminating-predicate guard for a decision/permission cluster must encode the
GENERAL policy condition that separates the qualifying cases from the rest (e.g.
`if record.tier == "restricted" and action == "modify": raise ...`), NOT a global
behavior flip and NOT a task literal. The guard NARROWS — it fires only on the cases
the policy actually governs — so passing tasks outside that condition keep their
behavior unchanged.

## The highest-leverage edit: deterministic CODE (usually in an EXISTING tool body)

**Start here. A deterministic guard in code beats a sentence in the prompt.** A
docstring or system-prompt rule only makes the model *more likely* to comply — it
can be forgotten, mis-read, or out-reasoned on the next task. Code (a precondition
check, a normalization, a loop) makes the right behavior *the only thing that can
happen* — it cannot be "forgotten." When the traces show a rule the agent keeps
breaking, a multi-step action it keeps fumbling, or — most importantly — an action
it *stalls on and never executes*, **do not just reword a description — put the
behavior in code.**

**Two code-bearing edits, chosen by failure type — both first-class.** For a rule
VIOLATION, enforce the rule in the body of the EXISTING tool that owns it — "only
cancel a cancellable record" governs `cancel_record`, "amounts in whole cents"
governs `book`/`charge`; add an in-body guard there and expect to touch SEVERAL
existing bodies per iteration. For a CAPABILITY GAP or an action STALL, write a NEW
code-bearing tool — a loop tool to collapse a multi-call chain, or (the big one) a
**composite atomic-WRITE tool** to encapsulate a multi-step write the agent keeps
skipping. Do not treat the new tool as a last resort: when a cluster stalls at the
action boundary, the composite is the *correct* fix even though a write primitive
already exists, because the primitive is exactly what the agent declines to call.
(See the before/after diffs above, the three patterns below, and the worked bodies
in [`references/examples.md`](references/examples.md).)

**Prose cannot fix a BEHAVIORAL failure.** There is a sharp distinction the
optimizer must make. If the agent *does not know* something (a format, a rule, a
decision criterion), prose can teach it — that is a KNOWLEDGE gap, and it belongs
in the prompt. But if the agent demonstrably *knows* what to do and still doesn't
do it — it analyzes the situation, explains the plan, even gets the user's
confirmation, and then simply **fails to CALL the action tool and stops** — that
is a BEHAVIORAL failure, and *more prose does not fix it*. You cannot instruct a
model out of a behavior it already "agreed" to and then skipped. The only
reliable fix is to move the behavior into CODE: encapsulate the whole action in a
tool whose body performs it, so executing it is no longer a choice the model can
decline mid-conversation. Telling the agent to "be sure to act" is exactly the
kind of edit the traces show failing.

Three patterns carry almost all the gain (worked bodies below and in
[`references/examples.md`](references/examples.md)):

1. **Validation / rule-enforcement tool (wrap, then delegate).** When a rule or
   precondition that today lives only in the prompt is GENERAL — it always
   applies, not just to one task — implement it as code in a NEW tool that:
   validates / normalizes the inputs → enforces the rule → calls the existing
   primitive → returns a clear result (or a clean refusal). Then **remove the raw
   primitive from the exposed set** if the agent should only ever reach it
   through the safe path. Example: `cancel_record_safely(record_id)` reads the
   record, refuses unless it is cancellable, then calls the raw `cancel_record`.

2. **Workflow / loop tool (collapse a recurring multi-step sequence).** When a
   small multi-step workflow recurs, or the agent calls one primitive N times in
   a row (and drops or mis-threads a result), implement it as ONE tool with real
   loops/code that calls the existing tools internally and returns the finished
   result. Example: a tool that loops over a list of ids calling `get_record`
   once each and returns them aligned, instead of the agent issuing N calls.

3. **Write / workflow COMPOSITE tool — make a stalled action un-skippable
   (co-equal PRIMARY pattern).** This is the fix for the single most common
   BEHAVIORAL failure: the agent reliably **stalls at the action/write boundary**
   — it analyzes, explains, even confirms with the user, then never issues the
   write call and stops, leaving the task half-done. The cure is *not* a stronger
   rule. Encapsulate the ENTIRE multi-step action (analyze → confirm → act) as
   ONE composite tool whose body performs *all* the steps in code — calling the
   existing primitives in the right sequence and looping where needed — so the
   action completes the moment the tool is called and **cannot be skipped
   mid-conversation**. Then **`remove` the raw primitives** so the composite is
   the only path; the safe, complete behavior is then the only behavior reachable.
   Generic example: an `apply_change_plan(record_id, steps)` that performs a
   multi-step update atomically — validating each step, applying them in order via
   the existing write primitives, and returning the final state — so the agent
   hands over the plan in one call instead of narrating it and then failing to
   execute. (Worked body in [`references/examples.md`](references/examples.md) §3e.)

**Lean caveat — replace, don't accumulate.** Every exposed tool enters the
agent's context, and too many tools degrade selection (see §3 of concepts.md).
So PREFER consolidating over piling on: when you add a safer or looped tool,
**`remove` the now-redundant primitive** so the net tool count stays small and
sharp. Do not add many narrow tools. One sharp tool that subsumes a primitive
beats two overlapping ones.

**SAFE TOOL-REPLACEMENT PROTOCOL (never bare-remove a tool).** To replace or
consolidate a tool, follow these steps in order — never delete a tool without a
replacement that subsumes it:

1. **ADD a wrapper tool whose body CALLS the existing tool** — after validation,
   normalization, or the extra steps you want guaranteed. The wrapper delegates to
   the primitive; it does not re-implement it.
2. **VERIFY** the wrapper (run `validate`; confirm the body actually calls the
   primitive and returns a sane result).
3. **Only then SWAP the registration**: `remove` the raw primitive from the active
   / exposed set and register the wrapper as the path the agent uses.

Bare-removing a primitive with no replacement strands every task that needed it
("no applicable tool"); adding a wrapper but leaving the primitive exposed lets the
model route around the guard and reproduce the original failure. The add-verify-swap
order is what makes the safe path the *only* path without a coverage gap.

**You must write the BODY.** A `compose`/`add`/`code` edit whose body is `...`,
a bare `pass`, or docstring-only is NOT this edit — it does nothing. Emit a real
implementation: the loop, the precondition check, the calls to the existing
tools (`get_record(i)` — or `self.get_record(i)` if your adapter binds tools as
methods). Worked examples with full bodies are below under
[Add tools that call existing tools](#add-tools-that-call-existing-tools-the-highest-leverage-edit).

**SECONDARY (last resort): passthrough / "think" / reasoning-only tools.** A tool
whose body just returns (or echoes) its argument, with the actual rule living only
in the *docstring* (e.g. a `think(thought)`/`check_policy(text)` tool that does no
real work), is the WEAKEST form of this edit — it is prose wearing a tool's
costume, and the model can ignore or mis-apply it exactly like any prompt sentence.
**If a rule can be encoded as code, encode it as code** — validate, normalize, and
enforce it in the body (patterns 1 and 2 above), don't leave it as docstring prose.
Reach for a reasoning-only tool only when the behavior genuinely cannot be made
deterministic (e.g. you want to *prompt* a planning step), never as a substitute
for a check you could have written in a few lines of code.

## How agents fail (and how tools fix it)

Map the trace symptom to the code-bearing edit. Each row is a failure the model
*could* "know" how to avoid yet keeps producing — so the fix is code, not prose:

These four rows carry most of the recoverable gain — diagnose for them FIRST, and
verify the fix you ship actually FIRES on the failing trace (run the new body on the
exact arguments from that trajectory; a guard that never triggers on the failing task
is dead code, not a fix). These rows are independent: fix as MANY of them as appear in
the trajectories in one candidate, not just the first — each guarded tool is its own
bounded fix.

| Trace symptom | Fix |
|---------------|-----|
| **Wrong ARGUMENT the tool could validate** — a write whose id / reference / count / unit is not consistent with the agent-visible state (an id not in the record, a count exceeding what's available, the wrong unit). Right tool, bad argument; partial credit or a corrupted write. | **Normalize-then-call wrapper**: wrap the write in a body that RESOLVES / VALIDATES the argument against the current state, and on mismatch returns `available=[...]` (the valid options) or raises an actionable error naming what's wrong and what to pass instead — never let a write proceed on an unvalidated reference. Coerce units, resolve ids, check the field is on file, then delegate to the primitive. |
| **Escalate / bail-out abandoning a REQUIRED, eligible action** — the agent hands off or gives up when it could and should have completed the action itself; this is a behavioral STALL, not a missing capability. | **Composite WRITE tool**: encapsulate the eligible-action batch in ONE tool whose body executes the steps in code (skipping any ineligible item with a recorded reason), then `remove` the raw primitives so completing the batch is the only path. Do NOT add a "don't bail out" prose rule — the agent already chose to bail; only code removes the choice. |
| **Recoverable error that strands the agent** — a tool raises an opaque traceback / bare code, the agent retries the same bad call or gives up. | **Enriched RETURN that aids recovery**: on a recoverable error, return what's wrong + the valid options + the recommended next action (e.g. `{"error": "id not found", "available": [...], "next": "call search_x to resolve the id"}`), so the model self-corrects on the next turn instead of repeating the failure. |
| **Execution stalls at the action boundary** — the agent analyzes, explains, even confirms, then never calls the write tool and stops (the task is left half-done). | **Composite WRITE tool** (pattern 3): one tool whose body performs the whole analyze→confirm→act sequence, then `remove` the raw primitives so the action is un-skippable. |
| **The same primitive called N times in a row** — looping over a list in the agent's own context, dropping or mis-threading results. | **Loop tool** (pattern 2): one tool that takes the list and loops inside a single call. |
| **A rule stated in the prompt but repeatedly violated** — a required order ("read before write"), a precondition the API doesn't enforce. | **Validation wrapper** (pattern 1): enforce the rule in the tool body; `remove` the unguarded primitive. |

The throughline: a failure the agent *knows better than* but still commits is
behavioral, and behavioral failures are fixed by removing the choice — putting the
behavior in code and `remove`-ing the path that let it go wrong.

## When to use this

Reach for `tools` when a trace shows one of these failure signatures:

- **Execution stall at the action/write boundary (BEHAVIORAL)** — the agent
  reaches the point of acting, narrates or confirms the action, then **fails to
  call the write tool and stops**. This is not a knowledge gap and prose will not
  fix it; encapsulate the whole action in a composite WRITE tool and remove the
  raw primitives so completing it is the only path (§"highest-leverage edit",
  pattern 3).
- **Mis-selection** — the agent calls the wrong tool, or calls none when one
  applied, or invents a tool that does not exist. Selection is driven almost
  entirely by the tool *name* and *description*, so this is a documentation fix.
- **Bad argument-filling** — the right tool, wrong arguments: a missing required
  field, the wrong enum value, a free-text string where a structured object was
  expected. This is a parameter-schema and per-parameter-description fix.
- **Repeated multi-call sequences the agent fumbles** — the agent must chain
  `search` → `filter` → `fetch` every time and keeps getting the order or the
  glue wrong. A single well-named **composite** tool collapses the sequence.
- **The same primitive called N times in a row** — the agent loops over a list
  in *its own context* (calls `get_record(id)` once per id, or `search(a,b,date)`
  once per date/route combination), burning turns and often dropping or
  mis-threading a result. A tool that takes the **list** and loops *inside one
  call* collapses N calls into 1.
- **An invariant the model keeps violating** — a required order of operations
  ("read before write"), a precondition the API does not itself enforce, or a
  normalization the model forgets. A tool that **enforces the rule in code**
  (validates, normalizes, or performs the steps in the right order) makes the
  mistake impossible rather than merely discouraged.
- **A DECISION / PERMISSION the model gets wrong (ACT vs REFUSE)** — the agent acts
  where the policy says refuse/escalate (or refuses where it should act). Do NOT fix
  this by loosening the global rule in the prompt — that changes behavior for the whole
  class and regresses every task where the original behavior was correct (unbounded
  blast radius). Encode the EXACT discriminating policy predicate as an in-body guard on
  the tool that owns the action: it refuses/raises ONLY on the qualifying condition, so
  its blast radius is bounded to the violating cases. This is the SAFE, preferred
  alternative to a permission-rule prompt edit.
- **A bloated or overlapping toolset** — too many tools, or several that do
  nearly the same thing, distracting the agent. Remove or consolidate.
- **A real behavioral bug in a handler** — the tool returns the wrong thing.
  Because you own the code, you can fix it directly.

If the problem is *what the agent is told to do* rather than *what it can do*, it is
out of scope for this capability (it belongs to whatever capability edits the agent's
instructions).

## What can be optimized (default policy = all of these)

| Action | Changes | Why it moves the metric |
|--------|---------|-------------------------|
| `description` | tool-level wording incl. in-desc examples | the single biggest lever on *selection* |
| `params` | per-parameter descriptions / defaults | drives correct *argument-filling* |
| `examples` | example call strings | shows concrete well-formed calls |
| `schema` | the full JSON Schema (types, `required`, `enum`) | constrains/guides the model's output |
| `code` | **the handler body of an EXISTING tool** | **the default high-leverage edit** — convert a violated prose rule into an in-body guard (precondition, normalization, actionable refusal); expect to edit SEVERAL existing bodies per iteration |
| `compose` | add a code-bearing tool that calls existing tools | enforce a rule, collapse a multi-call chain, or perform a whole stalled WRITE action in code — use when no existing tool owns the rule |
| `add` / `remove` | introduce / delete a tool | shape and shrink the toolset (replace primitives; keep it lean) |

The `code` row (editing an EXISTING tool's body) is the **first edit to reach
for**, with `compose`/`add` close behind — a deterministic guard beats a sentence
in a prompt (see below). For each violated rule, first ask "which EXISTING tool
governs this, and what in-body check enforces it?" — usually the answer is editing
that tool's body, not adding a new one. Reword descriptions *after* you've asked
"can this rule be code in the existing body instead?" In ONE pass, apply EVERY edit
class the traces call for — in-body guards across SEVERAL existing tools AND a loop
tool where needed AND enriched returns/errors AND doc fixes across all implicated
tools can and should all ship in the same candidate; do not stop after a single
edit.

Lock any of these off via `inputs/policy.json`. For example, in a frozen-API
deployment you might allow only `["description", "params", "examples"]` so an
optimizer can reword tools but never change the wire contract or the code.
`apply()` refuses anything outside the allowed set and reports the refusal — it
never silently drops or silently applies a disallowed edit.

## How tool-using agents actually read a tool

An LLM never sees your implementation. At call time it sees, for every available
tool, a serialized block of `{name, description, parameters-schema, examples}`
injected into its context (this is literally how the Anthropic and OpenAI tool
APIs work, and how an MCP host presents `tools/list` results). Two decisions
follow, and each is driven by a different part of that block:

1. **Selection** — *which* tool (or none) to call. Decided primarily from the
   **name** and **description**. Anthropic's own guidance is blunt: the
   description "is by far the most important factor in tool performance," and
   they recommend at least 3–4 sentences covering *what the tool does, when to
   use it, and when not to*. A name like `lookup` selects worse than
   `get_order_by_id`.
2. **Argument-filling** — *how* to populate the call. Decided from the
   **parameter schema** (types, `required`, `enum`, descriptions) plus any
   **examples**. An `enum` turns "guess a status string" into "pick from this
   closed set"; prefer it for every closed value set, and use the provider's
   **strict / schema-validated mode** where available so the model adheres to the
   schema instead of guessing. A per-field description ("ISO-8601 date, e.g.
   2025-06-14"; "amount in whole US cents") turns a malformed argument into a
   correct one — always pin **units, format, and default** per parameter. Add
   schema-validated **`input_examples`** for complex / nested / format-sensitive
   params (a few help; long dumps hurt reasoning models). And **don't make the
   model fill arguments you already know** — pass them in code (a wrapper) instead
   of asking for them.

**Namespace by service/resource** so selection stays unambiguous as the set grows
(`github_list_prs`, `payments_charge`), and keep the **active toolset small** — aim
for **fewer than ~20 tools per turn** (OpenAI's heuristic); selection degrades
sharply past that. This is the number behind the lean caveat above.

## Shape the RESULT, not just the call (output/response design)

What a tool *returns* steers the next turn as much as its description steers
selection. A bloated or opaque result causes hallucinated ids, wasted context, and
redundant calls. Design the response:

- **Return high-signal fields only.** Strip low-value noise (internal uuids, mime
  types, 256-px thumbnail urls, audit columns). Return the semantic fields the
  agent will actually act on.
- **Use stable, human-readable identifiers, not raw UUIDs.** Models hallucinate and
  mis-copy long opaque ids; a `get_order(order_id)` projection should surface
  `order_id="A-1042"` over `4f3c…-uuid`. If the backend only has a UUID, attach a
  readable handle alongside it.
- **Paginate / filter / truncate with sane defaults**, and offer a
  **`verbosity`/`response_format`** control (e.g. `"concise"` vs `"full"`) so the
  agent asks for detail only when needed instead of drowning in it.
- **Make error messages ACTIONABLE — they are a steering surface, not just a
  failure.** A raw traceback or opaque code teaches the model nothing. Return a
  specific, example-bearing message that tells the agent how to recover:
  `"payment method not on file; available: ['card_1','gift_4'] — pass one of these"`
  or `"date must be ISO-8601 YYYY-MM-DD, got '6/14/25'"`. The model reads the error
  and self-corrects on the next call instead of retrying the same bad one. Wrappers
  (patterns 1–3) are the natural place to produce these.

## Document every tool comprehensively

A tool's documentation is its contract. Every tool — primitive or wrapper — needs
**all** of these, or the model is left guessing:

- a **crisp description**: what it does, when to use it, and when NOT to (the
  boundary against the nearest sibling tool);
- an **"important points"** note for any non-obvious behavior or precondition;
- a **Raises / errors** section listing the failure conditions (keep these — see
  below; they are a guard rail, not clutter);
- a **per-parameter description** with units / format / allowed values / default;
- one **generic, always-valid usage example** (the shape of a call, never one
  task's literal id/date/city).

**The description is the model's contract, not flavor text.** It is the *only*
information the model has about *which* tool to call and *what argument values
are legal*. A good description always states, in always-true terms (never one
task's specifics):

- **When to use / when not to use** — explicit triggers, and the boundary
  against the nearest sibling tool ("use X for a single record by id; use Y to
  search across records").
- **Argument semantics** — for each parameter: its meaning, **units**, **allowed
  values / format**, and **default**. "amount in whole US cents" beats "the
  amount"; "ISO-8601 date `YYYY-MM-DD`" beats "the date".
- **Preconditions and failure modes** — what must be true *before* the call, and
  what the tool **raises / returns on error**. This is the model's chance to
  avoid a bad call. **Do NOT strip `Raises:`/error-condition text to make the
  description "cleaner."** Knowing a call raises `ValueError: gift card balance
  too low` is exactly what lets the model pick a different payment method instead
  of failing the task. Stripping error info removes a guard rail; it does not
  improve selection.
- **A short, always-valid usage example** — one concrete well-formed call that is
  correct for *any* input (e.g. the shape of a list element), never a single
  benchmark task's literal values.

Selection degrades as the toolset grows: benchmarks like the Berkeley
Function-Calling Leaderboard include a dedicated "relevance detection" category
precisely because models hallucinate calls when no tool fits, and ToolLLM had to
add a *retriever* to cope with thousands of tools. The practical implication for
this capability: **fewer, sharper, non-overlapping tools beat many vague ones.**

## Concrete before/after

**Selection fix (description).** A trace shows the agent calling a generic
`query` tool for order lookups, then failing.

```diff
- "name": "query", "description": "Run a query."
+ "name": "get_order", "description": "Look up a single order by its ID and
+   return status, line items, and shipping. Use when the user references a
+   specific order (an ID, 'my last order', or an order in the current thread).
+   Do NOT use for searching across orders — use search_orders for that."
```

**Argument-filling fix (schema + enum).** The agent keeps sending
`status="done"` when the backend expects `"fulfilled"`.

```diff
  "parameters": { "type": "object", "properties": {
-   "status": { "type": "string", "description": "the status" }
+   "status": { "type": "string", "enum": ["pending","fulfilled","cancelled"],
+               "description": "Order status to filter by." }
  }, "required": ["status"] }
```

**Collapse a fumbled chain (compose).** The agent must `search_orders` then
`get_order` on the first hit, and often forgets the second call.

```json
{ "kind": "compose", "value": {
    "name": "find_order",
    "description": "Search orders by free text and return the full record of the
      best match. Use this instead of search_orders+get_order when you want one order.",
    "code": "def find_order(q):\n    hit = search_orders(q)[0]\n    return get_order(hit['id'])"
}}
```

## Add tools that call existing tools (the highest-leverage edit)

A docstring edit can only make the model *more likely* to do the right thing.
A new tool whose body calls existing tools can make the right thing *the only
thing the model can do*, and can turn many calls into one. These are the two
PRIMARY patterns (§"highest-leverage edit" above) plus the normalize variant —
all benchmark-agnostic, and each shows a REAL body you are expected to write:

1. **Workflow / loop — collapse repeated primitive calls into one list call.** If the agent calls
   `get_record(id)` once per id, or `search(origin, dest, date)` once per
   route/date combination, add a tool that takes the **list** and loops inside a
   single call, returning all results together. The agent makes one call instead
   of N; nothing is dropped or mis-threaded.
   ```json
   { "kind": "compose", "value": {
       "name": "get_records",
       "description": "Fetch the FULL details of EVERY record in `ids` in one call. Use this instead of calling get_record once per id when you have several ids (e.g. all of a user's records). Returns a list aligned with `ids`; an entry is an error object if that id is not found.",
       "parameters": {"type":"object","properties":{"ids":{"type":"array","items":{"type":"string"}}},"required":["ids"]},
       "code": "def get_records(ids):\n    out = []\n    for i in ids:\n        try:\n            out.append(get_record(i))\n        except Exception as e:\n            out.append({'id': i, 'error': str(e)})\n    return out" }}
   ```

2. **Validation / rule-enforcement — enforce a rule or required order
   deterministically (wrap, then delegate).** If a write must be preceded by a
   read, or a precondition the API does not itself check must hold, put the check
   in code: validate/normalize the inputs, enforce the rule, then call the
   existing primitive — so a violation returns a clear refusal instead of
   corrupting state. The model literally cannot skip the step. Then **`remove`
   the raw primitive** so the only path is the safe one.
   ```json
   { "kind": "compose", "value": {
       "name": "cancel_record_safely",
       "description": "Cancel a record after verifying it is cancellable. Reads the record first and REFUSES (returns an error) if the cancellation preconditions are not met, so you never need to call get_record yourself before cancelling. Use this for every cancellation.",
       "parameters": {"type":"object","properties":{"record_id":{"type":"string"}},"required":["record_id"]},
       "code": "def cancel_record_safely(record_id):\n    rec = get_record(record_id)\n    if not rec.get('cancellable'):\n        return {'error': 'not cancellable', 'record': rec}\n    return cancel_record(record_id)" }}
   ```
   ...paired with a `{ "tool": "cancel_record", "kind": "remove" }` so the unsafe
   primitive leaves the choice set entirely.

3. **Normalize / return richer, ready-to-use results.** Have the new tool do the
   glue the model otherwise improvises (resolve an id, attach the related record,
   coerce units), so the model gets a result it can act on directly.

**Then remove the error-prone original** deliberately (the lean caveat). This
`remove` step is not optional polish — it is what makes the safe/complete tool the
*only* path. A wrapper that enforces a rule, or a composite that performs a whole
write, achieves nothing if the raw primitive is still exposed: the model can (and
under pressure will) route around the guard straight to the primitive and
reproduce the exact failure. Observed in real runs, optimizers add wrappers but
**never `remove` the primitives they wrap**, so the unsafe path survives and the
metric barely moves. To *replace* a confusing or now-redundant tool,
`add`/`compose` the clearer one and `remove` the old name so it leaves the choice
set — don't keep both, or selection gets harder (§3 of concepts.md). Net tool
count should stay small and sharp: prefer one tool that subsumes a primitive over
two that overlap. Pair every wrapper/composite with the matching `remove` unless
the primitive is still independently needed for a *different*, safe purpose.

## What good vs bad tool edits look like

Drawn from real runs where the optimizer left most of the gain on the table.

**Bad — what under-performs (do not stop here):**

- **Stripping `Raises:` / error info** "to clean up" the docstring. Observed: an
  accepted candidate deleted every `Raises:` section. It barely moved the metric
  and left the model blind to why calls fail. Error conditions are guidance, not
  clutter — keep them.
- **Cosmetic description rewording** — reflowing sentences, adding commas,
  restating the obvious ("Cancel the record" → "Cancel an entire record"). No new
  always-true information, so no behavior change.
- **Baking one task's specifics into a description** — naming a particular id,
  date, or city. It overfits and can mislead on the next task.
- **Adding tools that duplicate ones the agent already uses fine** — enlarges the
  choice set and *hurts* selection for no gain.

**Good — what actually moves accuracy and cuts calls:**

- **A loop/composite tool** that collapses the repeated-primitive pattern from the
  traces (e.g. the agent fetching records one id at a time, or sweeping a search across
  many parameter combinations) into a single list call.
- **A rule-enforcing tool** that reads-before-writes or validates a precondition
  the underlying API does not, turning a silent bad write into a clear refusal.
- **Precise descriptions** that add genuinely new, always-true content: explicit
  when/when-not triggers, per-argument units/allowed-values/defaults, retained
  failure modes, and one always-valid example call.
- **Replace, don't accumulate** — add the clearer tool and `remove` the
  error-prone original so the surface stays small and sharp.

The test: *would this edit help on a task the optimizer has never seen?* A loop
tool, a precondition check, and a unit-pinned argument description pass. A comma
and a deleted `Raises:` line do not.

## Failure modes to avoid

- **Over-describing into contradiction.** Adding a fifth "use when" clause that
  conflicts with the first makes selection *worse*. Keep descriptions internally
  consistent; state the boundary against the nearest sibling tool, not every tool.
- **Schema changes that break callers.** You own the callers here, but a `code`
  edit and a `schema` edit must stay in sync — change both in one batch, then run
  `validate`. In a frozen-API setting, lock `schema`/`code` off via policy.
- **Composite-tool sprawl.** A composite is worth it only if the chain is
  frequent and error-prone. Adding one for a two-call path the agent already
  handles just enlarges the toolset and hurts selection.
- **Removing a tool that's rarely-but-critically needed.** Check the traces:
  remove for *overlap/confusion*, not merely for low call-count.
- **Examples that fight reasoning models.** A few examples sharpen formatting, but
  long example dumps can degrade reasoning-tuned models — prefer a crisp schema
  over many examples.

## The action policy (safety knob)

`inputs/policy.json` is the safety boundary between "reword the docs" and "rewrite
the program." It exists because the same artifact is edited in very different
trust settings: an optimizer you trust to polish descriptions should not be free
to change the wire schema of a tool other systems depend on, or to inject
arbitrary handler code. The default here is the **full** set; tighten it to match
your deployment's blast radius. Every refused edit is reported, so a policy that's
too tight surfaces as visible refusals rather than silent no-ops.

## Artifact + handlers

`tools.json` — a list of `{name, description, parameters, examples, code?}`.
`scripts/abstract.py` provides:
- `materialize(dir)` — flatten the surface into named text components
  (`tool.<name>.description`, `.parameters`, `.examples`) for a text optimizer.
- `apply(dir, edits)` — policy-enforced edits incl. `schema`/`code`/`compose`;
  returns `{changed, refused}`.
- `validate(dir)` — schema well-formedness, empty-description and duplicate-name
  checks.

## How to run

```
python scripts/check.py
python scripts/run.py --path <capability_dir>     # candidate + policy + validity
```

## References

- [`references/authoring-and-validation.md`](references/authoring-and-validation.md) —
  how to BUILD/specify a tool or bundled script the agent can find, fill, and run
  (spec fields, docstring rules, the validate pipeline, script interface). Load when
  creating a new tool/compose/script, not when only rewording one.
- [`references/concepts.md`](references/concepts.md) — the mental model (select vs.
  fill, toolset design, the policy) with cited sources.
- [`references/examples.md`](references/examples.md) — worked before/after edits.
- [`references/pitfalls.md`](references/pitfalls.md) — failure modes and how to detect them.
