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
tightened to documentation-only edits — that is the `mcp-tool` capability.)

**Read this skill, then read [`references/edit-playbook.md`](references/edit-playbook.md)
before editing** — the playbook holds the eight levers in depth, the before/after
diffs, the three code-bearing patterns, and the safe tool-replacement protocol.

## The core rule

**A deterministic guard in code beats a sentence in a prompt.** A docstring or
prompt rule only makes the model *more likely* to comply; code makes the right
behavior the only thing that can happen. So the DEFAULT edit is: find the EXISTING
tool that owns the violated rule and put a scoped guard in its body.

**Ship MULTIPLE fixes per iteration — but every one must be REAL** (targets a
currently-failing task), **SAFE** (cannot change a passing task's behavior), and
**VERIFIED** (proven to fix its target). Several such fixes beat a long list that
includes a speculative edit: one edit that regresses a passing task can sink the
whole candidate at the gate. Quality over churn — never add an edit to hit a count,
and never re-add a rule/tool the run already tried and rejected.

**Per-change SAFETY (the rule that makes multi-change work).** Scope every guard to
fire ONLY on the exact violating condition, and check its blast radius: run it on the
args of 1–2 currently-PASSING tasks that use the same tool and confirm it does NOT
fire. A guard that fires on a passing task is a regression — rescope or drop it. This
is how you ship many changes without net-zero churn.

**Generalize, never hardcode.** A guard must fire on the GENERAL condition that
defines the failure class, never on a literal value from one task. *Good:* `if
payment_id not in user_payment_methods: raise ...`. *Bad:* `if record_id ==
"<TASK_SPECIFIC_ID>": raise ...` — that overfits, gets rejected by the held-out gate,
and helps nothing else.

**Prose cannot fix a BEHAVIORAL failure.** If the agent *does not know* something,
prose can teach it — a KNOWLEDGE gap belongs in the prompt. But if it demonstrably
knows what to do, narrates the plan, even gets confirmation, and then **fails to call
the action tool and stops**, more prose will not fix it. Move the behavior into code.

## Pick the lever by failure type

Full detail for every row: [`references/edit-playbook.md`](references/edit-playbook.md).

| Failure signature in the traces | The edit |
|---|---|
| **A rule the agent keeps VIOLATING** (wrong field value, id not on file, action on a record whose state forbids it) | **In-body guard on the EXISTING tool that owns the rule** — the default, highest-yield, lowest-regression edit. Expect to touch SEVERAL bodies per iteration. |
| **Wrong ARGUMENT the tool could validate** — right tool, bad argument; partial credit or a corrupted write | **Normalize-then-call wrapper**: resolve/validate the argument against current state; on mismatch return `available=[...]` or raise an actionable error. Never let a write proceed on an unvalidated reference. |
| **Execution STALLS at the action/write boundary** — analyzes, explains, even confirms, then never calls the write tool | **Composite atomic-WRITE tool** whose body performs the whole sequence, then `remove` the raw primitives so the action is un-skippable. Not a "be sure to act" prose rule. |
| **Escalate / bail-out abandoning a REQUIRED, eligible action** | Same composite WRITE tool (skip ineligible items with a recorded reason). The agent already *chose* to bail; only code removes the choice. |
| **The same primitive called N times in a row** | **Loop tool** that takes the list and loops inside one call. |
| **Recoverable error that strands the agent** — opaque traceback, agent retries the same bad call | **Enriched RETURN**: what's wrong + the valid options + the recommended next action. |
| **DECISION / PERMISSION wrong (ACT vs REFUSE)** | **Discriminating-predicate guard** on the tool that owns the action, encoding the EXACT policy predicate. Do NOT loosen a global prompt rule — unbounded blast radius regresses every task the original behavior got right. |
| **HARD-ZERO / capability gap** — a 0.00 task needing a compute/composite tool | **A REAL targeted tool the agent will CALL**, never a reword. A 0.00 stays 0.00 after any docstring change. |
| **Mis-selection** — wrong tool, no tool where one applied, or an invented tool | **A documentation fix**: selection is driven almost entirely by the *name* and *description*. |
| **Bad argument-filling** — right tool, wrong arguments (missing required field, wrong enum value, free text where an object was expected) | **A parameter-schema + per-parameter-description fix.** |
| **A fumbled multi-call sequence** — the agent must chain `search` → `filter` → `fetch` and keeps getting the order or the glue wrong | **One well-named composite tool** that collapses the sequence. |
| **Bloated / overlapping toolset**, or a real handler bug | Consolidate (`add` the superset, then `remove`); or just fix the code — you own it. |

**Diagnose for the first four rows FIRST** — they carry most of the recoverable gain.
Verify the fix you ship actually FIRES on the failing trace (run the new body on the
exact arguments from that trajectory; a guard that never triggers on the failing task
is dead code, not a fix). The rows are independent: fix as MANY as appear in the
trajectories in one candidate, not just the first — each guarded tool is its own
bounded fix. The throughline: a failure the agent *knows better than* but still
commits is behavioral, and behavioral failures are fixed by removing the choice —
putting the behavior in code and `remove`-ing the path that let it go wrong. Each
row's long-form symptom description and full fix recipe:
[`references/edit-playbook.md`](references/edit-playbook.md#how-agents-fail-and-how-tools-fix-it--the-full-symptomfix-table).

If the problem is *what the agent is told to do* rather than *what it can do*, it is
out of scope here (it belongs to whatever capability edits the agent's instructions).

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

The `code` row (editing an EXISTING tool's body) is the **first edit to reach for**,
with `compose`/`add` close behind. For each violated rule, first ask "which EXISTING
tool governs this, and what in-body check enforces it?" Reword descriptions *after*
you've asked "can this rule be code in the existing body instead?" In ONE pass, apply
EVERY edit class the traces call for — in-body guards across SEVERAL existing tools
AND a loop tool where needed AND enriched returns/errors AND doc fixes across all
implicated tools can and should all ship in the same candidate.

**You must write the BODY.** A `compose`/`add`/`code` edit whose body is `...`, a bare
`pass`, or docstring-only is NOT this edit — it does nothing. Worked bodies:
[`references/examples.md`](references/examples.md).

**Never bare-remove a tool.** Add the wrapper → verify it → *then* swap the
registration. Bare-removing strands every task that needed the primitive; leaving the
primitive exposed lets the model route around the guard. Protocol:
[`references/edit-playbook.md`](references/edit-playbook.md#the-safe-tool-replacement-protocol).

**Keep the surface lean** — aim **< ~20** active tools; selection degrades sharply
past that. When you add a safer or looped tool, `remove` the now-redundant primitive.

Lock any action off via `inputs/policy.json`. For example, in a frozen-API deployment
you might allow only `["description", "params", "examples"]` so an optimizer can
reword tools but never change the wire contract or the code. `apply()` refuses
anything outside the allowed set and reports the refusal — it never silently drops or
silently applies a disallowed edit. `inputs/policy.json` is the safety boundary
between "reword the docs" and "rewrite the program"; the default here is the **full**
set. Tighten it to match your deployment's blast radius — a too-tight policy surfaces
as visible refusals rather than silent no-ops.

## Documentation, schema, and return values

The model never sees your implementation — only `{name, description,
parameters-schema, examples}`. **Selection** comes from the name + description;
**argument-filling** comes from the schema + examples. Every tool needs a crisp
description (what / when / when-NOT vs the nearest sibling), an important-points note,
a **`Raises:`/errors section** (keep it — knowing a call raises "balance too low" is
what lets the model pick a different argument), a per-parameter description with
**units / format / allowed values / default**, and one **generic, always-valid**
example (never one task's literal id/date/city). Use `enum` for every closed value
set; namespace by service/resource as the set grows.

What a tool *returns* steers the next turn as much as its description steers
selection: return high-signal fields only, prefer stable human-readable ids over raw
UUIDs, paginate/truncate with sane defaults, and make **error messages actionable**
(`"payment method not on file; available: ['card_1'] — pass one of these"`).

Full checklist, the reader-capability-tier adjustment, and the response-design rules:
[`references/documentation.md`](references/documentation.md).

## Failure modes to avoid

- **Over-describing into contradiction.** A fifth "use when" clause that conflicts
  with the first makes selection *worse*. State the boundary against the nearest
  sibling tool, not every tool.
- **Schema changes that break callers.** A `code` edit and a `schema` edit must stay
  in sync — change both in one batch, then run `validate`.
- **Composite-tool sprawl.** A composite is worth it only if the chain is frequent
  and error-prone.
- **Removing a tool that's rarely-but-critically needed.** Remove for
  *overlap/confusion*, not for low call-count.
- **Examples that fight reasoning models.** A few sharpen formatting; long dumps
  degrade reasoning-tuned models — prefer a crisp schema.
- **Cosmetic rewording / stripping `Raises:`** — no new always-true information, so
  no behavior change. The test for any edit: *would this help on a task the optimizer
  has never seen?*

Detection signals for each: [`references/pitfalls.md`](references/pitfalls.md).

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

- [`references/edit-playbook.md`](references/edit-playbook.md) — **read before
  editing**: the eight levers in depth, the in-body-guard before/after diffs, the
  three code-bearing patterns, the safe tool-replacement protocol, and good-vs-bad
  edits.
- [`references/documentation.md`](references/documentation.md) — how a model reads a
  tool definition, the per-tool doc checklist, response/error design, and the
  reader-capability-tier adjustment.
- [`references/concepts.md`](references/concepts.md) — the mental model (select vs.
  fill, toolset design, the policy) with cited sources.
- [`references/examples.md`](references/examples.md) — worked before/after edits with
  full bodies.
- [`references/pitfalls.md`](references/pitfalls.md) — failure modes and how to detect them.
- [`references/optimizer-playbook.md`](references/optimizer-playbook.md) — what the
  authored optimizer INSTRUCTIONS must demand when `tools` is selected: the
  existing-tool-code mandate, the depth mandate's tools wording, and the two-phase
  (diagnose fan-out → implement fan-out → merge) subagent pattern. `intake` points
  here rather than inlining it.
