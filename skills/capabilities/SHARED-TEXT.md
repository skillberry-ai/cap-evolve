# Shared / duplicated text across capabilities (maintenance index)

Per the design decision, each capability skill is **self-contained**: shared ideas are
restated in each capability rather than linked from one shared file. This table tracks
those duplicated passages so a future edit to a shared idea can be synced everywhere.
This file is a maintenance aid only — it is NOT an Agent Skill reference and is not
linked from any `SKILL.md`.

When you change any passage below, update every listed location (and this table).

| Passage key | Idea | Locations (file · section) | Intended variance |
|---|---|---|---|
| `write-for-agents` | Write for the agent reader, not the human (third person, imperative, no marketing/mechanics/long-why, keywords users say) | skill-package/references/writing-for-agents.md (whole file) · skill-package/references/anti-patterns.md (§Human-oriented writing) · tools/references/authoring-and-validation.md (§1) · tools/references/pitfalls.md (§Human-oriented tool text) · mcp-tool/SKILL.md (§Write the client-side text…) · system-prompt/SKILL.md (§Organize the prompt…) | skill-package has the canonical full version + checklist; others state a compact, capability-scoped version |
| `four-layer-model` | Description / Snippets / Tools / Implementation decomposition + which capability owns which layer | skill-package/references/concepts.md (§The four optimization layers) · tools/references/concepts.md (§The four optimization layers) · mcp-tool/references/concepts.md (§Where MCP sits…) · system-prompt/references/concepts.md (§The four optimization layers) | each table highlights the layer(s) that capability owns; mcp-tool notes Layers 2/4 are server-owned |
| `route-to-layer` | Identify the failing layer → make one targeted edit → evaluate → gate/rollback (mirrors cap-evolve loop) | skill-package/references/concepts.md · tools/references/concepts.md · system-prompt/references/concepts.md | phrased around each capability's owned layer |
| `layer-metrics` | The metrics per layer (selection/precision/recall; success/tokens/hallucination/time; invocation/latency/retry; runtime/CPU/mem) | skill-package/references/description-optimization.md (§Metrics…) + concepts.md (§Metrics for snippets) · tools/references/concepts.md (§Metrics) · system-prompt/references/concepts.md (§Snippet metrics) | each lists only the layer(s) it owns |
| `select-then-fill` | Selection driven by name+description; argument-filling driven by schema/enum/examples | tools/references/concepts.md (§2, pre-existing) · tools/references/authoring-and-validation.md (§3) · mcp-tool/references/concepts.md (pre-existing) | tools owns the deep version; others reference the same idea |
| `validation-pipeline` | Build a tool then prove it works: retries, unit tests vs provided +/- examples, execution validation, signature/AST checks, eval threshold, security, recovery | tools/references/authoring-and-validation.md (§4) | single home; other capabilities do not build code tools |
| `script-interface` | Non-interactive, --help, structured stdout/stderr, exit codes, idempotency, --dry-run, truncation-safe, self-contained deps | tools/references/authoring-and-validation.md (§6) | single home |
| `snippet-patterns` | Focused-snippet split, decision trees, failure-handling/recovery, example quality, redundancy removal | skill-package/references/concepts.md (§Snippet-organization patterns) · system-prompt/SKILL.md (§Organize the prompt…) | skill-package frames for skill bodies; system-prompt frames for prompt/policy |
| `task-decomposition` | Enumerate concrete supported/unsupported tasks + keyword enrichment for triggering | skill-package/references/description-optimization.md (§Decompose the capability…) · mcp-tool/SKILL.md (§Write the client-side text…) | mcp-tool applies it to re-describing server tools |
