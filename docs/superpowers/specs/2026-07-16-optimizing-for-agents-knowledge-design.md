# Design: Capture "how to optimize skills & tools for AI agents" in `skills/capabilities/`

**Date:** 2026-07-16
**Status:** Approved (design) — ready for implementation plan
**Scope:** Documentation/reference edits only inside `skills/capabilities/`. No infrastructure or code changes (per constraint).

## Problem

The four cap-evolve capability skills (`skill-package`, `tools`, `mcp-tool`,
`system-prompt`) instruct the optimizer agent on *how to optimize* a target
artifact. They are already strong, but three gaps limit how well they "explain how
to optimize" skills and tools:

1. **No unifying mental model.** There is no explicit map that decomposes a skill
   into optimizable layers and routes a failure to the capability that owns it.
2. **"Write for the AI-agent reader, not the human" is implicit.** Humans (or
   human+AI) author most skills/tools, so the text drifts toward narrating,
   explaining *why* at length, and marketing tone — optimized for a human reader,
   not for an agent that must trigger, slot-fill, and execute. This principle is
   scattered across third-person / imperative / front-load rules but never stated
   once with a checklist.
3. **Tool/script *authoring & validation* discipline is thin.** The `tools`
   capability covers *editing* an existing tool surface well, but not *building* a
   correct tool (full spec fields, strict docstrings, a test/validate pipeline) or
   *script* interface design.

## Sources synthesized

- **"AI Skill Optimization Guide"** (ChatGPT export, `~/Downloads/AI Skill
  Optimization Guide.pdf`) — the 4-layer decomposition, cross-layer moves, and the
  route-to-layer optimization pipeline.
- **skillberry-skill-maker** (`github.ibm.com/skillberry/skillberry-skill-maker`,
  local copy) — the concrete tool build-and-validate discipline: tool spec fields,
  strict docstring rules, and the generation/validation pipeline
  (`agentic_stages/tool_making/`, `remediation/base.py`).
- **agentskills.io** skill-creation docs — description-optimization loop and the
  script-authoring interface rules.
- **Anthropic "Writing tools for agents", OpenAI function-calling, GEPA/DSPy,
  BFCL/ToolLLM** — already cited in the existing references; reused for grounding.

### The 4-layer model → capability mapping

| Layer | What it is | Optimize for | Metrics | cap-evolve capability |
|---|---|---|---|---|
| **1. Description** (metadata) | when to select/trigger | discoverability, routing, precision/recall | selection accuracy, precision, recall, invocation frequency | `skill-package` (skill desc) · `tools`/`mcp-tool` (tool desc) |
| **2. Snippets** (instructional body/refs, policy) | how to do the task | reasoning quality, token cost, fewer hallucinations | success rate, token consumption, tool-selection accuracy, hallucination rate, time-to-completion | `skill-package` (body/refs) · `system-prompt` |
| **3. Tools** (executable capabilities) | what it can do & how it's exposed | capability, invocation accuracy, latency, composability | invocation accuracy, success/failure rate, latency, retry count | `tools` · `mcp-tool` |
| **4. Tool Implementation** (internal code) | runtime correctness/perf (invisible to LLM) | reliability, runtime, memory | runtime, CPU/mem, success/error rate | `tools` (`code`) — NOT `mcp-tool` (server owns it) |

Cross-layer moves: token reduction (1+2), better examples (2+3), semantic
alignment (1+2), modularization (2+3), telemetry-driven / benchmarking / continuous
evolution (all). The **route-to-layer pipeline** (telemetry → benchmark → identify
target layer → targeted change → re-evaluate → promote/rollback) mirrors cap-evolve's
`propose → evaluate → gate → finalize`.

### Tool build-and-validate discipline (from skillberry-skill-maker)

- **Tool spec fields:** name, summary, intent, pseudo-code, inputs
  (type/description/required/default/**enum_values**), outputs (type/nullable),
  examples split into **happy_path / edge_cases / error_cases**, dependencies
  (+ compact dependency signatures), error_model, test_mocks, security_notes.
- **Strict docstring rules:** docstring derived **only from the code** (prevents
  description/impl drift); **enumerate ALL allowed values** for every constrained
  param (enum/Literal/default/validation); Store-parseable `Parameters:` /
  `Returns:` sections (`<name> (<type>): <description>` per arg). → serves slot-filling.
- **Validation pipeline:** generation retries on validation failure; unit tests run
  **against the provided positive + negative examples**; execution validation;
  evaluation-score threshold; unwanted-words + security checks; **strict function
  signatures**; AST syntax + function-name checks; recovery/reuse on failure. →
  serves "functionally working".
- **Error-case discipline:** distinguish an error **code** (`NOT_FOUND` → raise/true
  negative) from a full message or a dict-returning tool
  (`{"success": false, "message": ...}` → positive).

### Script-authoring interface rules (from agentskills.io)

Non-interactive (no TTY prompts); `--help`/usage as the interface; structured
stdout vs. diagnostics-on-stderr; meaningful, documented exit codes; idempotency;
`--dry-run` for stateful ops; truncation-safe output (summaries + `--offset`/`--output`);
self-contained dependencies (PEP-723 for Python, equivalents elsewhere); pinned versions.

## Decision: per-capability content + one external duplication table

Chosen approach (user decision): keep each capability **self-contained** — put only
the layers/knowledge it owns inside its own `SKILL.md` and `references/`. Do **not**
add a shared cross-capability reference file. To keep future updates manageable,
add **one external tracking table** (`skills/capabilities/SHARED-TEXT.md`) that
records which passages are duplicated across capabilities and where, so a future
edit to a shared idea can be synced everywhere.

Rationale: preserves the skill self-containment / one-level-deep convention; avoids
up-directory reference links; the tracking table pays the DRY cost explicitly rather
than through fragile cross-references.

## File-by-file plan

### A. `skill-package/` (Layers 1 + 2)
- **New** `references/writing-for-agents.md` — the "write for the agent-reader, not
  the human" principle + checklist, scoped to skills: describe user intent not
  internal mechanics; imperative; keywords users actually say; no marketing tone; no
  narrating *why* at length; front-load. Cross-referenced from `SKILL.md`.
- **Edit** `references/description-optimization.md` — add **task decomposition**
  (enumerate concrete supported/unsupported tasks), explicit **scope + prerequisites**,
  sharpen **keyword enrichment**, add the "Presentation editing" before/after, add
  **metrics** (selection accuracy, precision, recall).
- **Edit** `references/concepts.md` — add **snippet-organization patterns**: decision
  trees ("Need X? → do Y"), failure-handling / recovery blocks, example quality
  (resemble real user requests), redundancy removal, focused-snippet split; add
  snippet **metrics**; add a short 4-layer framing note (this capability owns
  Description + Snippets) and the route-to-layer pipeline framing.
- **Edit** `references/anti-patterns.md` — add human-oriented writing smells.
- **Edit** `SKILL.md` — one-line principle + pointer to `writing-for-agents.md`.

### B. `tools/` (Layers 3 + 4, plus tool-description sublayer)
- **New** `references/authoring-and-validation.md` — full **tool spec fields**;
  **strict docstring rules**; the **validation pipeline**; **error-case discipline**;
  **tool granularity** (too small / too large), **composition**, **observability**;
  **script-interface rules** (non-interactive, `--help`, structured output, exit
  codes, idempotency, `--dry-run`, truncation-safe, self-contained deps).
- **Edit** `references/concepts.md` — add the 4-layer framing (this capability owns
  Tools + Implementation) + Layer-3/4 metrics.
- **Edit** `references/pitfalls.md` — add granularity pitfalls + human-oriented smells.
- **Edit** `SKILL.md` — principle + pointer to the new reference.

### C. `mcp-tool/` (Layer 1 + set curation only)
- **Edit** `SKILL.md` + `references/concepts.md` — write-for-agents principle scoped
  to client-side descriptions; task-decomposition / keyword enrichment for
  re-describing; slot-filling-via-description-only (enum/units/format in the param
  description, since schema is server-owned); explicitly note Layers 2/4 are
  server-owned and out of scope.

### D. `system-prompt/` (Layer 2)
- **Edit** `SKILL.md` + `references/concepts.md` — snippet patterns (decision trees,
  failure-handling, redundancy removal, instruction decomposition) framed for
  policy/prompt text; write-for-agents principle; Layer-2 metrics. Respect the
  existing never-drop rule and knowledge-vs-behavioral boundary already present.

### E. External tracking table
- **New** `skills/capabilities/SHARED-TEXT.md` — a maintenance table (not a skill
  reference). One row per duplicated passage (write-for-agents principle,
  SELECT-then-FILL, progressive disclosure, 4-layer model, route-to-layer pipeline,
  validation pipeline) × columns naming each capability file that holds a copy, plus
  a note on intended variance, so future edits can find and sync all instances.

## Non-goals

- No changes to `scripts/`, adapters, `capevolve.yaml`, or any Python/infra.
- No new shared reference file linked across capabilities (rejected in favor of
  per-capability + tracking table).
- Not re-deriving benchmark/gate mechanics — those already exist and are only
  *referenced* by the new framing.

## Validity constraints to honor while editing

- Frontmatter unchanged/valid (`name`, `description` limits; no XML tags).
- Bodies stay within budget (<500 lines / ~5k tokens); overflow goes to `references/`.
- References stay one level deep; each new reference is linked from its `SKILL.md`
  with an explicit "what/when to load" pointer; long references get a TOC.
- No task-specific/overfit content; all guidance is general and always-true.
- Run each capability's `scripts/check.py` after edits to confirm nothing breaks
  frontmatter/link validation.
