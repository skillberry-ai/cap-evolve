# Concepts — optimizing an agent's own tool surface

> The mental model behind the `tools` capability: how an LLM turns a set of tool
> definitions into a tool call, what each part of a definition controls, and why
> the editable surface is governed by an action policy. Grounded in provider tool
> docs, function-calling benchmarks, and prompt-optimization research.

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
small description refinements "yield dramatic improvements." Namespacing
(`orders_search` vs `users_search`) reduces selection ambiguity.

## 4. Composite tools collapse fragile chains

When a trace repeatedly shows the same multi-call sequence going wrong (wrong
order, forgotten step, mis-threaded IDs), a `compose` edit adds one higher-level
tool whose code calls the existing handlers. This trades a brittle multi-turn
plan the model must reconstruct each time for a single deterministic call. It is
only worth it when the chain is *frequent and error-prone* — otherwise it just
enlarges the choice set and hurts selection (§3).

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
