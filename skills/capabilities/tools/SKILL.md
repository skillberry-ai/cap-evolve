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
| `compose` | **add a tool that calls existing tools** | collapse a fumbled multi-call chain |
| `add` / `remove` | introduce / delete a tool | shape and shrink the toolset |

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
