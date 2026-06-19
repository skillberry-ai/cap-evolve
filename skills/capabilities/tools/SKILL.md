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

Use this when the agent owns its tools. Use [`mcp-tool`](../mcp-tool/SKILL.md)
when the tools come from an external Model Context Protocol server you can only
re-describe, not re-implement. The two share the same `tools.json` artifact and
handlers; the only difference is which edits the action policy permits.

## The highest-leverage edit: write a NEW code-bearing tool

**Start here. A deterministic tool beats a sentence in the prompt.** A docstring
or system-prompt rule only makes the model *more likely* to comply — it can be
forgotten, mis-read, or out-reasoned on the next task. A tool whose body is
**real code** (loops, validation, calls to existing tools) makes the right
behavior *the only thing that can happen* — it cannot be "forgotten." When the
traces show a rule the agent keeps breaking or a multi-step sequence it keeps
fumbling, **do not just reword a description — write a tool with a real body.**
This is the first edit to reach for, not the last.

Two patterns carry almost all the gain (worked bodies below and in
[`references/examples.md`](references/examples.md)):

1. **Validation / rule-enforcement tool (wrap, then delegate).** When a policy
   or precondition that today lives only in the prompt is GENERAL — it always
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

**Lean caveat — replace, don't accumulate.** Every exposed tool enters the
agent's context, and too many tools degrade selection (see §3 of concepts.md).
So PREFER consolidating over piling on: when you add a safer or looped tool,
**`remove` the now-redundant primitive** so the net tool count stays small and
sharp. Do not add many narrow tools. One sharp tool that subsumes a primitive
beats two overlapping ones.

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

## When to use this

Reach for `tools` when a trace shows one of these failure signatures:

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
- **A bloated or overlapping toolset** — too many tools, or several that do
  nearly the same thing, distracting the agent. Remove or consolidate.
- **A real behavioral bug in a handler** — the tool returns the wrong thing.
  Because you own the code, you can fix it directly.

If the problem is *what the agent is told to do* rather than *what it can do*,
optimize the [`system-prompt`](../system-prompt/SKILL.md) instead.

## What can be optimized (default policy = all of these)

| Action | Changes | Why it moves the metric |
|--------|---------|-------------------------|
| `description` | tool-level wording incl. in-desc examples | the single biggest lever on *selection* |
| `params` | per-parameter descriptions / defaults | drives correct *argument-filling* |
| `examples` | example call strings | shows concrete well-formed calls |
| `schema` | the full JSON Schema (types, `required`, `enum`) | constrains/guides the model's output |
| `code` | the handler implementation | fix behavior, bugs, or return shape |
| `compose` | **add a code-bearing tool that calls existing tools** | **highest leverage** — enforce a rule or collapse a multi-call chain in code |
| `add` / `remove` | introduce / delete a tool | shape and shrink the toolset (replace primitives; keep it lean) |

The `compose`/`code`/`add` rows are the **first edits to reach for** — a
deterministic tool beats a sentence in a prompt (see below). Reword descriptions
*after* you've asked "can this rule or recurring workflow be code instead?"

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
   closed set." A per-field description ("ISO-8601 date, e.g. 2025-06-14") turns
   a malformed argument into a correct one.

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

**Then remove the error-prone original** deliberately (the lean caveat). To
*replace* a confusing or now-redundant tool, `add`/`compose` the clearer one and
`remove` the old name so it leaves the choice set — don't keep both, or selection
gets harder (§3 of concepts.md). Net tool count should stay small and sharp:
prefer one tool that subsumes a primitive over two that overlap.

## What good vs bad tool edits look like

Drawn from real runs where the optimizer left most of the gain on the table.

**Bad — what under-performs (do not stop here):**

- **Stripping `Raises:` / error info** "to clean up" the docstring. Observed: an
  accepted candidate deleted every `Raises:` section. It barely moved the metric
  and left the model blind to why calls fail. Error conditions are guidance, not
  clutter — keep them.
- **Cosmetic description rewording** — reflowing sentences, adding commas,
  restating the obvious ("Cancel the reservation" → "Cancel an entire
  reservation"). No new always-true information, so no behavior change.
- **Baking one task's specifics into a description** — naming a particular id,
  date, or city. It overfits and can mislead on the next task.
- **Adding tools that duplicate ones the agent already uses fine** — enlarges the
  choice set and *hurts* selection for no gain.

**Good — what actually moves accuracy and cuts calls:**

- **A loop/composite tool** that collapses the repeated-primitive pattern from the
  traces (e.g. the agent fetching a user's records one id at a time, or sweeping
  flight searches across many date/route combinations) into a single list call.
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

- [`references/concepts.md`](references/concepts.md) — the mental model (select vs.
  fill, toolset design, the policy) with cited sources.
- [`references/examples.md`](references/examples.md) — worked before/after edits.
- [`references/pitfalls.md`](references/pitfalls.md) — failure modes and how to detect them.
