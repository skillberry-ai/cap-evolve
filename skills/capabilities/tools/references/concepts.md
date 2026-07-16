# Concepts — optimizing an agent's own tool surface

> The mental model behind the `tools` capability: how an LLM turns a set of tool
> definitions into a tool call, what each part of a definition controls, and why
> the editable surface is governed by an action policy. Grounded in provider tool
> docs, function-calling benchmarks, and prompt-optimization research.

## Contents
- 1. The model never sees your code — it sees the definitions
- 2. Two decisions, two levers: SELECT, then FILL
- 3. More tools is not better
- 4. Composite tools collapse fragile chains
- 5. The action policy is the safety boundary
- 6. Automatic optimization of tool text
- 7. Output / response shaping
- 8. The safe tool-replacement protocol
- Sources

## 1. The model never sees your code — it sees the definitions

At call time the model is given, for every available tool, a serialized block:

```
name            an identifier (e.g. get_order)
description     plaintext: what it does, when to use it, when NOT to
parameters      a JSON Schema (types, properties, required, enum, descriptions)
examples        optional concrete example calls / inputs
```

This is exactly the contract of both major provider APIs and of the Model
Context Protocol: a tool is `{name, description, input_schema/inputSchema}`. The
implementation is invisible to the model. **Therefore every selection and
argument error is, first, a *definition* problem — not a code problem** (unless
the handler is genuinely buggy, which `code` edits address).

## 2. Two decisions, two levers: SELECT, then FILL

- **Selection** — *which* tool, or none. Driven by **name + description**.
  Anthropic's tool-use guidance states the description "is by far the most
  important factor in tool performance" and recommends ≥3–4 sentences covering
  what / when / when-not. OpenAI's guide gives the same advice and adds: describe
  each parameter and its format, and use the prompt to say when *not* to call a
  function.
- **Argument-filling** — *how* to populate the call. Driven by the **parameter
  schema** (types, `required`, `enum`) and **examples**. A JSON-Schema `enum`
  restricts a value to a fixed set, so the model picks rather than guesses;
  structured-output research shows a schema can *guarantee* conformance rather
  than merely suggest it.

Mapped to the action kinds this capability exposes: `description` → selection;
`params`/`schema`/`examples` → filling; `code` → behavior; `add`/`remove`/
`compose` → the shape of the choice set itself.

## 3. More tools is not better

Selection accuracy degrades as the toolset grows and as tools overlap:

- The **Berkeley Function-Calling Leaderboard** evaluates name/required-param/
  type correctness and includes a dedicated *relevance-detection* category —
  measuring whether a model hallucinates a call when no tool fits.
- **Gorilla** and **ToolLLM/ToolBench** found that even strong models hallucinate
  API usage at scale; ToolLLM had to add a neural *retriever* to navigate 16k+
  tools, and Gorilla showed a document retriever sharply cuts hallucination.
- **MetaTool** separates "is a tool needed?" from "which tool?" and finds
  selection is the harder, still-unsolved half.

Design implication: prefer **fewer, sharper, non-overlapping tools.** Anthropic's
"Writing tools for agents" makes the same point — overlapping tools "distract
agents," a single tool can "consolidate functionality… under the hood," and even
small description refinements "yield dramatic improvements." A concrete budget:
OpenAI's function-calling guide recommends keeping the **active set under ~20
tools** per turn. **Namespacing** by service/resource (`orders_search` vs
`users_search`, `payments_charge` vs `payments_refund`) reduces selection ambiguity
as the library grows, and `user_id` selects better than a bare `user`.

Argument-filling reliability scales with how *closed* the schema is: use **`enum`**
for every closed value set, the provider's **strict / schema-validated mode** where
available (so output conforms rather than merely suggesting), per-parameter
**units/format/default**, and **`input_examples`** for nested or format-sensitive
params. Don't ask the model to fill an argument the code already knows — bind it in
a wrapper.

## 4. Composite tools collapse fragile chains

When a trace repeatedly shows the same multi-call sequence going wrong (wrong
order, forgotten step, mis-threaded IDs), a `compose` edit adds one higher-level
tool whose code calls the existing handlers. This trades a brittle multi-turn
plan the model must reconstruct each time for a single deterministic call. It is
only worth it when the chain is *frequent and error-prone* — otherwise it just
enlarges the choice set and hurts selection (§3).

Three sub-cases, all benchmark-agnostic, recur in practice:

- **Loop-in-one-call.** When the agent calls the *same* primitive N times in its
  own context — once per id, once per date, once per route — a tool that takes
  the list and loops inside one call removes N−1 turns and the chance of dropping
  a result. This is the single most common waste in real traces.
- **Rule/invariant enforcement.** When the backend does not itself enforce a
  precondition or a required order (read-before-write, "only if cancellable"),
  put the check in the composite's code. A violation becomes a clean refusal the
  model can react to, instead of a silent wrong-state write.
- **Normalization / richer return.** Resolve ids, attach related records, or
  coerce units inside the tool so the model gets a ready-to-use result.

Keeping error information matters here too: a tool's documented failure modes
(what it `Raises`/returns on error) are part of the contract the model reasons
over — "Tool Documentation Enables Zero-Shot Tool-Usage" (arXiv:2308.00675)
finds documentation, not examples, is what carries usage. Deleting error
conditions to shorten a description removes guidance and is a common
*non-improving* edit.

## 7. Output / response shaping

Selection and filling decide the *call*; the **response** decides the next turn.
Anthropic's "Writing tools for agents" treats response design as a first-class
lever:

- **Return high-signal fields, drop noise.** Internal uuids, mime types,
  thumbnail urls, and audit columns inflate context and distract. Project to the
  fields the agent acts on.
- **Stable, human-readable ids over raw UUIDs.** Long opaque identifiers are
  mis-copied and hallucinated; surface a readable handle (`order_id="A-1042"`) and
  keep the UUID only if a later call truly needs it.
- **Pagination / filtering / truncation with sane defaults**, plus a
  **`verbosity` / `response_format`** control so the model can request `concise`
  vs `full` rather than always paying for the largest payload.
- **Errors are a steering surface.** An `isError` result with a specific,
  example-bearing message ("amount must be whole cents; got 12.99 → pass 1299")
  lets the model self-correct; an opaque traceback or code teaches it nothing and
  it retries the same bad call. Treat the error string as instructions to the next
  turn, not a log line. (Tool Documentation Enables Zero-Shot Tool-Usage,
  arXiv:2308.00675, finds documented behavior — including failure modes — is what
  carries usage.)

## 8. The safe tool-replacement protocol

Observed in real runs: optimizers add wrappers but never remove the primitives, so
the unsafe path survives — or they bare-remove a tool and strand the tasks that
needed it. Both are regressions. The safe sequence to replace/consolidate a tool:

1. **ADD a wrapper** whose body *calls* the existing primitive after the extra
   validation/normalization/steps you want guaranteed (it delegates, never
   re-implements).
2. **VERIFY** it (`validate`; confirm the body calls the primitive and returns a
   sane result).
3. **SWAP the registration** — `remove` the raw primitive from the exposed set and
   expose the wrapper.

Never bare-remove without a replacement that calls the original. Add-verify-swap
makes the safe path the only path with no coverage gap (and keeps the count lean —
one tool subsuming a primitive beats two overlapping ones).

## 5. The action policy is the safety boundary

`inputs/policy.json` lists the allowed edit kinds. It exists because the same
artifact is edited in different trust settings. Rewording a description is low
risk; rewriting a handler's `code` or changing a `schema` other systems depend on
is high risk. The policy lets you grant exactly the blast radius you intend:

- Frozen API / shared schema → allow `["description","params","examples"]` only.
- You own everything → allow the full set (the default in this capability).

This mirrors the *mutation-lock* idea from agent-optimization tooling: let an
automatic optimizer change the safe surface, forbid the rest. `apply()` reports
every refusal, so an over-tight policy is visible, not silent.

## 6. Automatic optimization of tool text

The same loop a human runs here — propose a description/schema edit, score it on a
held-out task set, keep what helps — is what automatic prompt/instruction
optimizers do. **GEPA** evolves prompt/instruction text by reflecting in natural
language over sampled trajectories and reports beating RL (GRPO) and DSPy's
MIPROv2 on several tasks; **DSPy** optimizers (MIPROv2, GEPA) tune instructions
and demonstrations against a metric. Tool descriptions and examples are
exactly this kind of optimizable text, which is why this capability `materialize`s
them as named components an optimizer can rewrite.

## Sources

- Anthropic — Define tools / tool-use implementation (descriptions are the #1
  factor; ≥3–4 sentences; `input_examples`): https://platform.claude.com/docs/en/docs/agents-and-tools/tool-use/implement-tool-use
- Anthropic — Tool use overview (auto selection from descriptions; tools injected
  into the system prompt): https://platform.claude.com/docs/en/docs/build-with-claude/tool-use/overview
- Anthropic Engineering — Writing effective tools for agents (consolidation,
  overlap distracts, namespacing, small refinements help): https://www.anthropic.com/engineering/writing-tools-for-agents
- OpenAI — Function calling guide (name/description/parameters; describe each
  param; say when not to call; aim for <20 functions): https://developers.openai.com/api/docs/guides/function-calling
- OpenAI — Structured outputs (a JSON Schema can guarantee conformance): https://developers.openai.com/api/docs/guides/structured-outputs
- JSON Schema — `enum` (restrict a value to a fixed set): https://json-schema.org/understanding-json-schema/reference/enum
- Berkeley Function-Calling Leaderboard (AST eval + relevance detection): https://gorilla.cs.berkeley.edu/leaderboard.html
- Gorilla: LLM Connected with Massive APIs (arXiv:2305.15334): https://arxiv.org/abs/2305.15334
- ToolLLM: Mastering 16000+ Real-world APIs (arXiv:2307.16789): https://arxiv.org/abs/2307.16789
- MetaTool: Deciding Whether and Which Tool to Use (arXiv:2310.03128): https://arxiv.org/abs/2310.03128
- Tool Documentation Enables Zero-Shot Tool-Usage (arXiv:2308.00675): https://arxiv.org/abs/2308.00675
- GEPA: Reflective Prompt Evolution (arXiv:2507.19457): https://arxiv.org/abs/2507.19457
- DSPy — optimizers tune instructions/demos against a metric: https://dspy.ai/

## The four optimization layers (this capability owns Tools + Implementation)
A skill decomposes into four independently optimizable layers. This capability edits
the tool surface and the handler code:

| Layer | What | Optimize for | Owner |
|---|---|---|---|
| 1. Description | when to select the tool | selection accuracy | this capability (`description`) |
| 2. Snippets | agent instructions/policy | reasoning | the `skill-package` / `system-prompt` capability |
| 3. Tools | the exposed tool surface | invocation accuracy, latency, composability | this capability |
| 4. Tool implementation | the handler code (invisible to the LLM) | reliability, runtime, memory | this capability (`code`) |

Route the failure to the layer that owns it: mis-selection → Description (name +
description); bad arguments → the parameter schema / docs (Filling); missing or
hard-to-call capability → the Tool surface; slow/flaky execution → the Implementation.
Building a *new* tool well is its own discipline — see
[`authoring-and-validation.md`](authoring-and-validation.md).

## Metrics (Layers 3 + 4)
Tools (Layer 3): invocation accuracy, success/failure rate, average latency, retry
count. Implementation (Layer 4): runtime, CPU, memory, error rate. As always, a change
counts only if it moves the objective on the held-out val split.
