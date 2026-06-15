---
name: mcp-tool
description: Optimize an MCP toolset whose server is EXTERNAL (you can't re-implement the tools). Use when the agent talks to tools served over MCP and mis-selects them or fills arguments wrong. Only safe edits are permitted — tool/parameter documentation, in-description examples, and adding or removing tools from the exposed set. The wire schema and tool code are NOT editable here (the server owns them); use the `tools` capability when the agent owns its tools.
component: capability
argument-hint: "--path DIR"
allowed-tools: Read, Write, Edit, Bash
provides: [candidate]
needs: []
sources: [tau2bench]
---

# Capability: MCP tool (external server)

Tools served over the [Model Context Protocol](https://modelcontextprotocol.io)
come from an **external server** that you do not own. In MCP's client–server
split, the *server* defines each tool — its `name`, `description`, and
`inputSchema` — and implements the handler; the *host/client* (your agent's
runtime) discovers them via `tools/list`, presents them to the model, and invokes
them via `tools/call`. You can change **how the agent perceives and is offered**
those tools, but you cannot change their wire schema or implementation. This
capability therefore permits only the safe subset.

It shares the same `tools.json` artifact and handlers as [`tools`](../tools/SKILL.md);
the only difference is the action policy. Use `tools` when the agent owns the
implementation and the schema is yours to change.

## When to use this

Reach for `mcp-tool` when the agent is wired to an external MCP server and a trace
shows:

- **Mis-selection of an MCP tool** — the server-provided description is terse or
  ambiguous, so the model picks the wrong tool or none. You can re-describe it on
  the client side.
- **Bad argument-filling** — the model fills the server's `inputSchema` wrong.
  You can't change the schema, but you *can* add a clearer per-parameter
  description and concrete examples that the client surfaces alongside it.
- **A noisy exposed set** — the server offers 40 tools and the agent only needs 6;
  the extras distract it. You can hide tools from the model (expose a subset).
- **A useful tool the host isn't surfacing** — add it to the exposed set.

If you find yourself wanting to change a tool's types, `required` fields, or
behavior, you've outgrown this capability: either negotiate the change with the
server owner, or move the logic to an agent-owned tool via [`tools`](../tools/SKILL.md).

## What can be optimized (default policy)

| Action | Allowed? | Why |
|--------|:--:|-----|
| `description` / `params` / `examples` | yes | client-side documentation the model reads to select & fill |
| `add` | yes | expose another server tool to the model |
| `remove` | yes | hide a confusing/redundant tool from the model |
| `schema` | no | the MCP server defines the wire `inputSchema` |
| `code` | no | the server owns the implementation |
| `compose` | no | you can't add server-side code; compose agent-side via [`tools`](../tools/SKILL.md) |

`apply()` refuses `schema`/`code`/`compose` by default and reports each refusal —
so an edit the optimizer "wanted" to make but couldn't is visible, not silent. If
your MCP client genuinely supports client-side schema overrides or annotations,
widen `inputs/policy.json` deliberately and document why.

## How agents consume MCP tools

Mechanically identical to native function calling. The host fetches every
connected server's tools, combines them into one registry, and injects each
tool's `{name, description, inputSchema}` into the model's context. The model then
**selects** from name + description and **fills** arguments from the JSON-Schema
`inputSchema` (plus any examples). The *only* difference from agent-owned tools is
the ownership boundary on what you may edit — so the optimizer's job here is
purely (a) better client-side documentation and (b) a cleaner exposed set.

MCP also lets a server change its tool list at runtime and notify clients via
`notifications/tools/list_changed`. Treat `add`/`remove` here as *your* curation
of which of the available tools the model sees, not as a change to the server.

## Concrete before/after

**Re-describe a terse server tool (client side).** The server ships
`"description": "kb search"`. The model can't tell when to use it.

```diff
- "description": "kb search"
+ "description": "Search the internal knowledge base and return matching article
+   snippets with their URLs. Use when the user asks a how-to or policy question
+   that is likely documented. Returns at most 10 hits; refine the query if empty."
```

**Pin a parameter's format without touching the schema.** The schema says
`{"limit": {"type": "integer"}}`; the model sends 1000 and the call fails.

```diff
  "parameters": { "type": "object", "properties": {
-   "limit": { "type": "integer" }
+   "limit": { "type": "integer", "description": "Max hits to return (server caps at 10)." }
  } }
```

(You annotate the *description* of the existing schema field — allowed under
`params` — rather than changing its `type` or adding `maximum`, which would be a
forbidden `schema` edit.)

**Trim the exposed set.** Hide three rarely-correct, easily-confused tools so the
six the agent actually needs stand out:

```json
[ { "tool": "legacy_export_v1", "kind": "remove" },
  { "tool": "legacy_export_v2", "kind": "remove" },
  { "tool": "debug_dump",       "kind": "remove" } ]
```

## Failure modes to avoid

- **Documenting behavior the server doesn't actually have.** A client-side
  description that overpromises (claims filters or limits the server ignores)
  causes confident wrong calls. Describe only what the server's schema supports.
- **Hiding a tool the agent needs in rare cases.** As with native tools, remove
  for *overlap/confusion*, not low frequency.
- **Trusting server-supplied metadata blindly.** Tool descriptions from an
  external server are untrusted input. A malicious or compromised server can hide
  instructions in a `description` ("tool poisoning") that the model reads but the
  user never sees, or use `list_changed` to slip in new tools. Review descriptions
  you expose; the MCP spec itself marks tool annotations untrusted unless the
  server is trusted.
- **Trying to widen the schema here.** If the model genuinely needs a constraint
  the schema lacks (an enum, a max), that's a server change or an agent-owned
  wrapper — not an `mcp-tool` edit.

## The action policy (safety knob)

The restricted default policy *is* the point of this capability: it encodes the
ownership boundary of MCP. An optimizer can polish how tools are described and
which are exposed, but the wire contract and implementation stay with the server.
Keep the policy tight unless your specific MCP client supports more.

## Artifact + handlers

`tools.json` — the exposed MCP tool defs `{name, description, parameters, examples}`.
`scripts/abstract.py`: `materialize` (flatten to text components), `apply`
(restricted policy; reports refusals), `validate` (well-formedness, dup names,
empty descriptions).

## How to run

```
python scripts/check.py
python scripts/run.py --path <capability_dir>
```

## References

- [`references/concepts.md`](references/concepts.md) — the MCP model, the
  ownership boundary, and the security trust model, with cited sources.
