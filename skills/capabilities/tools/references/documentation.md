# Documentation & response design — what the model actually reads

How a tool-using model consumes a tool definition, what a complete tool doc
contains, how to shape the RESULT so the next turn recovers, and how to scale all
of that to the reader's capability tier. SKILL.md carries the one-line rule
("document every tool: description, important-notes, `Raises:`, per-param, one
generic example"); this file is the checklist behind it.

## Contents
- [How tool-using agents actually read a tool](#how-tool-using-agents-actually-read-a-tool)
- [Adapting to the reader's capability tier](#adapting-to-the-readers-capability-tier)
- [Shape the RESULT, not just the call](#shape-the-result-not-just-the-call)
- [Document every tool comprehensively](#document-every-tool-comprehensively)

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
sharply past that. This is the number behind the lean caveat in
[`edit-playbook.md`](edit-playbook.md).

Selection degrades as the toolset grows: benchmarks like the Berkeley
Function-Calling Leaderboard include a dedicated "relevance detection" category
precisely because models hallucinate calls when no tool fits, and ToolLLM had to
add a *retriever* to cope with thousands of tools. The practical implication for
this capability: **fewer, sharper, non-overlapping tools beat many vague ones.**

## Adapting to the reader's capability tier

Scale the edit to WHO calls these tools at runtime (see the `THE READER` block in
your instructions, if present). For a **mid/weak** reader, push harder on this
skill's already-preferred **code enforcement** (in-body guards, composite
atomic-write tools) — a weak reader skips a prose rule but a guard fires regardless
— and write **literal, example-bearing per-parameter slot-filling docs** on every
tool (name the exact format, units, and one concrete valid value, e.g. `date:
ISO-8601 "2026-07-20"`). A weak reader mis-fills under-documented arguments far more
often, so the marginal value of explicit parameter docs and a smaller,
less-confusable toolset is highest there. For a **frontier** reader, terser
parameter docs and fewer worked examples suffice; spend the budget on removing
redundant tools instead.

## Shape the RESULT, not just the call

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
  (the three patterns in [`edit-playbook.md`](edit-playbook.md)) are the natural
  place to produce these.

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
