---
name: tools
description: Optimize an agent's OWN tool surface (tools it implements, not an external MCP server). Use when the agent mis-selects tools, fills arguments wrong, calls the same tool N times in a row, or has a confusing, redundant, or oversized toolset. Covers tool names and descriptions, parameter docs, tool schemas, handler code, function-calling accuracy, and adding or removing tools.
component: capability
argument-hint: "--path DIR"
allowed-tools: Read, Write, Edit, Bash
provides: [candidate]
needs: []
sources: [gepa, tau2bench]
---

# Capability: tools (full control)

This capability treats the agent's **entire tool surface as the optimizable
artifact**. It applies when the agent *owns* its tools — it implements the handlers,
defines the wire schema, and controls every caller — so names, descriptions,
parameter docs, in-description examples, the JSON Schema, *and the implementation
code* are all fair game. (When the tools come from an external server you can only
re-describe, not re-implement: that is `mcp-tool`, whose policy is tightened to
documentation-only edits.)

## What you can change here

**The tool's documentation AND its return value are what the agent SEES — make both
clear and recovery-oriented.** The doc surface (description, important-notes,
per-param, error/`Raises` text, examples) drives *which* tool the model calls and
*how* it fills the arguments; the return value (and especially the error text) steers
the *next* turn. Confirm which parts of a docstring your runtime actually SENDS before
writing into it — some frameworks discard whole sections, and guidance written into
that void does nothing (`references/field-notes.md` §1).

**Ship MULTIPLE fixes per iteration — but every one must be REAL (targets a
currently-failing task), SAFE (cannot change a passing task's behavior), and VERIFIED
(proven to fix its target).** Several such fixes beat a long list that includes a
speculative edit: one edit that regresses a passing task sinks the whole candidate at
the val gate. Never add an edit to hit a count, and never re-add a rule or tool the run
already tried and rejected.

**Per-change SAFETY (the rule that makes multi-change work).** Scope every guard to
fire ONLY on the exact violating condition, and check its blast radius: run it on the
args of 1–2 currently-PASSING tasks that use the same tool and confirm it does NOT
fire. A guard that fires on a passing task is a regression — rescope or drop it.

## Pick the lever by failure type

Each item is an edit class. In ONE pass, apply EVERY class the traces call for — a
validation wrapper AND a loop tool AND enriched returns/errors AND doc fixes across all
implicated tools can and should ship in the same candidate. The in-body guard is the
default strong move; reach for a documentation edit only after asking "can this rule be
code in the existing body instead?"

1. **Edit the CODE of an EXISTING tool (reach for this FIRST for a rule violation).**
   Most violated textual rules govern a tool that ALREADY exists, and the fix is an
   in-body guard *there*, not a new tool: bake the precondition, normalization, or
   actionable refusal into the body so correctness does not depend on the LLM. *Ex:*
   add `if not rec["cancellable"]: raise ValueError("not cancellable; reason=...; do X
   instead")` to the existing `cancel_record` body. Expect to touch the BODIES of
   SEVERAL existing tools per iteration — one per violated rule. A deterministic guard
   beats a sentence in a prompt: prose makes the model *more likely* to comply, code
   makes the right behavior the only thing that can happen.
2. **Add a composite atomic-WRITE tool** — for a stalled or abandoned multi-step action,
   encapsulate the ENTIRE action in one tool whose body performs all the steps in order
   via the existing primitives, then **`remove` the raw primitives** so the action is
   un-skippable. *Ex:* `apply_change_plan(record_id, steps)` validates → applies each →
   returns final state as one call. Reach for this even though a write primitive already
   exists: the primitive is exactly what the agent declines to call.
3. **Add a discriminating-predicate guard** for an ACT-vs-REFUSE cluster — an in-body
   guard on the tool that owns the action, expressing the EXACT policy predicate, that
   refuses only when the qualifying condition is (or is not) met. It is the narrowest
   edit available here and the tool-side alternative to changing a global rule.
4. **Add a real targeted tool for a capability gap** — a task that needs a compute /
   composite / predicate tool it does not have stays failing after any docstring reword.
   Ship a tool the agent will CALL that changes the graded state — *Ex:* a
   `find_duplicate_records` it has no way to compute today, or a `search_logs` that
   returns the relevant lines instead of a raw dump.
5. **Add a loop tool** — replace N repeated single-item calls with one list call. *Ex:*
   `get_records(ids: [...])` replaces N× `get_record(id)`.
6. **Replace / wrap a tool** — superset an existing tool and route the old behavior
   through it. *Ex:* wrap `find_record`+`charge_payment` behind one
   `charge_record(record_id)` that resolves then charges.
7. **Improve a tool's documentation** — sharpen description / important-notes / error
   conditions / per-param docs / examples; rename for least surprise. *Ex:*
   `lookup(record)` → `get_record(record_id: str)` with "returns an error object if not
   found."
8. **Improve RETURN VALUES for recoverability** — high-signal fields, stable
   human-readable ids, and **actionable error text with a next-step hint and what NOT to
   do**. *Ex:* an error returning "payment method not on file; available: ['card_1'] —
   pass one of these" instead of a raw traceback. Adding to a return is not free,
   though: it is re-read every turn, so treat enrichment as a hypothesis to gate, not a
   free win (`references/field-notes.md` §2).
9. **Remove-with-replacement** — remove a redundant/overlapping tool *only* after a
   replacement preserving its capability exists. *Ex:* drop `query` once `get_record` +
   `search_records` cover it.

The two ways to waste an iteration: leaving a rule the agent keeps breaking as loose
prose instead of a guard (or loosening a global permission rule instead of scoping a
guard); and padding the candidate with low-value helper tools or cosmetic rewrites that
move no graded task.

## Guardrails

- **Encode deterministic logic in code, not prose** — a tool body the model cannot skip
  beats a sentence it can forget. A tool whose body enforces nothing (a `think()` /
  `check_policy()` passthrough with the rule only in its docstring) is prose in a tool's
  costume; reach for it only when the behavior genuinely cannot be made deterministic.
- **You must write the BODY.** A `compose`/`add`/`code` edit whose body is `...`, a bare
  `pass`, or docstring-only is not this edit — it does nothing. Emit the real loop, the
  real precondition check, the real calls to existing tools (`get_record(i)` — or
  `self.get_record(i)` if your adapter binds tools as methods).
- **Never remove a tool without a capability-preserving replacement.** Add → verify →
  swap (`references/concepts.md` §8). Bare-removing strands every task that needed it;
  adding a wrapper but leaving the primitive exposed lets the model route around the
  guard and reproduce the original failure.
- **Keep the toolset small and namespaced** — aim for **< ~20** active tools; selection
  degrades sharply past that. Prefer consolidating over piling on: when you add a safer
  or looped tool, `remove` the now-redundant primitive.
- **Ship correct, bug-free code** — every code edit needs validation plus a `validate`
  run, and proof the toolset still *registers* (an import check is not a registration
  check — `references/field-notes.md` §3).
- **Generalize, never hardcode.** Every guard must fire on the GENERAL condition that
  defines the failure class, never on a literal value from one task. *Good:* `if
  payment_id not in user_payment_methods: raise ...`. *Bad:* `if record_id ==
  "<TASK_SPECIFIC_ID>": raise ...` — that overfits, gets rejected by the held-out gate,
  and helps nothing else. Use a failing task's specifics only to identify the class,
  then write the general check. The test for any edit: *would this help on a task the
  optimizer has never seen?*

## How agents fail (and how tools fix it)

Map the trace symptom to the edit. This table is the single canonical statement of what
to ship for what failure. The rows are independent: fix as MANY of them as appear in the
trajectories in one candidate, not just the first — each guarded tool is its own bounded
fix. Verify the fix you ship actually FIRES on the failing trace (run the new body on
the exact arguments from that trajectory; a guard that never triggers on the failing
task is dead code, not a fix).

| Trace symptom | Fix |
|---------------|-----|
| **Wrong ARGUMENT the tool could validate** — a write whose id / reference / count / unit is not consistent with the agent-visible state. Right tool, bad argument; partial credit or a corrupted write. | **Normalize-then-call wrapper**: wrap the write in a body that RESOLVES / VALIDATES the argument against current state, and on mismatch returns `available=[...]` or raises an actionable error naming what is wrong and what to pass instead. Never let a write proceed on an unvalidated reference. |
| **The action never happens** — the agent analyzes, explains, even confirms, then never calls the write tool and stops; or it hands off / gives up on an action it could have completed. Task left half-done. | **Composite WRITE tool** (lever 2): one tool whose body performs the whole sequence — or the whole eligible-action batch, skipping any ineligible item with a recorded reason — then `remove` the raw primitives so completing it is the only path. Not a "be sure to act" prose rule. |
| **Recoverable error that strands the agent** — a tool raises an opaque traceback / bare code; the agent retries the same bad call or gives up. | **Enriched RETURN that aids recovery**: on a recoverable error return what is wrong + the valid options + the recommended next action (`{"error": "id not found", "available": [...], "next": "call search_x to resolve the id"}`) so the model self-corrects next turn. |
| **The same primitive called N times in a row** — looping over a list in the agent's own context, burning turns and dropping or mis-threading results. | **Loop tool** (lever 5): one tool that takes the list and loops inside a single call. |
| **A rule stated in the prompt but repeatedly violated** — a required order ("read before write"), a precondition the API does not enforce, a normalization the model forgets. | **In-body guard / validation wrapper** (lever 1): enforce the rule in the body of the tool that owns it; `remove` the unguarded primitive if the safe path must be the only one. |
| **A wrong ACT-vs-REFUSE call** — the agent acts where policy says refuse/escalate, or refuses where it should act. | **Discriminating-predicate guard** (lever 3) on the tool that owns the action. |
| **Mis-selection** — the agent calls the wrong tool, calls none when one applied, or invents a tool that does not exist. | **Name + description fix**: selection is driven almost entirely by the name and description — sharpen what/when/when-not and the boundary against the nearest sibling (`references/doc-contract.md`). |
| **Bad argument-filling** — right tool, wrong arguments: a missing required field, the wrong enum value, free text where a structured object was expected. | **Schema + per-parameter docs**: close the value set with an `enum`, pin units/format/default per parameter, add an in-description example. |
| **A bloated or overlapping toolset** — too many tools, or several that do nearly the same thing, distracting the agent. | **Consolidate then `remove`** the originals (lever 9). Remove for *overlap/confusion*, not for low call-count. |
| **A bug in a handler** — the tool returns the wrong thing. | **`code` edit**: because you own the code, fix it directly. |

The throughline: a failure the agent *knows better than* but still commits is fixed by
removing the choice — putting the behavior in code and `remove`-ing the path that let it
go wrong.

If the problem is *what the agent is told to do* rather than *what it can do*, it
belongs to whatever capability edits the agent's instructions, not here.

## What can be optimized (default policy = all of these)

| Action | Changes | Why it moves the metric |
|--------|---------|-------------------------|
| `description` | tool-level wording incl. in-desc examples | the single biggest lever on *selection* |
| `params` | per-parameter descriptions / defaults | drives correct *argument-filling* |
| `examples` | example call strings | shows concrete well-formed calls |
| `schema` | the full JSON Schema (types, `required`, `enum`) | constrains/guides the model's output |
| `code` | **the handler body of an EXISTING tool** | **the default high-leverage edit** — convert a violated prose rule into an in-body guard; expect to edit SEVERAL bodies per iteration |
| `compose` | add a code-bearing tool that calls existing tools | enforce a rule, collapse a multi-call chain, or perform a whole stalled WRITE action in code |
| `add` / `remove` | introduce / delete a tool | shape and shrink the toolset (replace primitives; keep it lean) |

`policy.json` in the capability dir is the safety boundary between "reword the docs" and "rewrite the
program" — the same artifact is edited in very different trust settings, so tighten the
allowed set to match your deployment's blast radius (a frozen-API deployment might allow
only `["description", "params", "examples"]`). `apply()` refuses anything outside the
allowed set and *reports* the refusal, so an over-tight policy surfaces as visible
refusals rather than silent no-ops.

## Adapting to the runtime reader's capability tier

Scale the edit to WHO calls these tools at runtime (if your instructions state the
runtime reader's capability tier, use it). For a **mid/weak** reader, push harder on
this skill's already-preferred **code enforcement** (in-body guards, composite
atomic-write tools) — a weak reader skips a prose rule but a guard fires regardless —
and write **literal, example-bearing per-parameter slot-filling docs** on every tool
(exact format, units, and one concrete valid value, e.g. `date: ISO-8601 "2026-07-20"`).
A weak reader mis-fills under-documented arguments far more often, so explicit parameter
docs and a smaller, less-confusable toolset are worth most there. For a **frontier**
reader, terser parameter docs and fewer worked examples suffice; spend the budget on
removing redundant tools instead.

## Artifact + handlers

`tools.json` — a list of `{name, description, parameters, examples, code?}`.
`scripts/abstract.py` provides:
- `materialize(dir)` — flatten the surface into named text components
  (`tool.<name>.description`, `.parameters`, `.examples`) for a text optimizer.
- `apply(dir, edits)` — policy-enforced edits incl. `schema`/`code`/`compose`;
  returns `{changed, refused}`.
- `validate(dir)` — schema well-formedness, empty-description and duplicate-name checks.
- `is_empty(dir)` — whether the artifact is an empty seed (no tools yet).

## How to run

```
python scripts/check.py
python scripts/run.py --path <capability_dir>     # candidate + policy + validity
```

## References

Each is standalone — read the one that matches what you are about to do.

- [`references/examples.md`](references/examples.md) — worked before/after edits with
  full bodies, ordered by leverage: in-body guards (§0), description/schema fixes
  (§1–§2), loop and composite/write tools (§3b–§3e), result shaping (§3f), the doc
  contract in practice (§3g), removal and refusals (§4–§7). **Load when you are about to
  write an edit** and want the exact JSON and a real body to model.
- [`references/concepts.md`](references/concepts.md) — how an LLM turns tool definitions
  into a call (select from name+description, fill from schema+examples), toolset-size
  limits, response shaping, the safe replacement protocol, and the action-policy model,
  with cited sources. **Read once per project**, before your first candidate.
- [`references/doc-contract.md`](references/doc-contract.md) — the full documentation
  contract for one tool: what/when/when-not, important-points, error conditions,
  per-parameter units and formats, one always-valid example. **Load when the fix is
  documentation rather than code.**
- [`references/pitfalls.md`](references/pitfalls.md) — edits that look like improvements
  and regress (stripped error conditions, cosmetic rewording, task-overfitted
  descriptions, composite sprawl, example dumps, an exposed primitive behind a wrapper),
  each with how to detect it. **Read before shipping a docs-only candidate**, and when
  an accepted candidate barely moved the metric.
- [`references/field-notes.md`](references/field-notes.md) — observations from real runs:
  how much of a docstring the runtime actually delivers, why enriching a return is not
  free, a docstring header that broke tool registration, and a return shape that
  corrupted the feedback signal. **Read before your first candidate on a new harness**,
  and whenever an edit "verified" green without an explanation you can point at.
- [`references/optimizer-playbook.md`](references/optimizer-playbook.md) — what the
  authored optimizer INSTRUCTIONS must demand when `tools` is selected: the
  existing-tool-code mandate, the depth mandate's tools wording, and the two-phase
  (diagnose fan-out → implement fan-out → merge) subagent pattern. **Read when authoring
  or reviewing those instructions** (`intake` points here rather than inlining it).
