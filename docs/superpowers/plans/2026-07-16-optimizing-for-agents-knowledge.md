# Optimizing-for-Agents Knowledge — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the four cap-evolve capability skills so each teaches how to optimize its layer of a skill/tool for the AI-agent reader — adding the 4-layer model, the "write for the agent, not the human" principle, and the tool build-and-validate discipline — plus one external table tracking duplicated text.

**Architecture:** Documentation/reference edits only, inside `skills/capabilities/`. Content is placed **per-capability** (each skill stays self-contained); duplicated passages are recorded in one external `SHARED-TEXT.md` maintenance table. No code, scripts, adapters, or infra change.

**Tech Stack:** Markdown reference files with YAML frontmatter (Agent Skills format). Validation via `skill-package/scripts/token_report.py` (body-budget check, runs standalone) plus manual link/frontmatter checks.

## Global Constraints

- Edits are **docs-only**. Do NOT touch any `scripts/*.py`, `meta.yaml`, adapters, `capevolve.yaml`, or Python/infra. Verbatim from spec: "we will change add or split and improve only prompts and text ... will not need to change any of the infrastructure or code."
- Frontmatter (`name`, `description`, `component`, etc.) must stay valid and, for this work, **unchanged**: `name` ≤64 chars `[a-z0-9-]`, no XML tags; `description` non-empty ≤1024 chars, no XML tags.
- SKILL.md **bodies** target <500 lines AND ~5k tokens. `tools/SKILL.md` is ALREADY over budget (~10.7k tokens / 661 lines) — its edit is limited to a single pointer line in the existing `## References` list; add NO prose to its body. New long-form content goes in `references/`.
- References stay **one level deep** (a reference never links to another reference); each new reference is linked from its own `SKILL.md` with an explicit "what it contains / when to load it" pointer; any reference >300 lines starts with a table of contents.
- All guidance is **general and always-true** — never bake in a specific benchmark task's id/value/date.
- Validation command (runs standalone, no cap-evolve install needed):
  `python skills/capabilities/skill-package/scripts/token_report.py --path skills/capabilities/<CAP>`
  — `over_budget` must be `false` for every capability whose SKILL.md body you touch.
- Work on branch `docs/optimizing-for-agents-knowledge` (already created; the design doc is committed there).
- Run all commands from repo root: `/home/eranra/go/src/github.com/skillberry-ai/cap-evolve`.

---

## Task 1: `skill-package` — write-for-agents principle + description/snippet enrichment

**Files:**
- Create: `skills/capabilities/skill-package/references/writing-for-agents.md`
- Modify: `skills/capabilities/skill-package/references/description-optimization.md` (append two sections)
- Modify: `skills/capabilities/skill-package/references/concepts.md` (append snippet-patterns + 4-layer note)
- Modify: `skills/capabilities/skill-package/references/anti-patterns.md` (append human-oriented smells)
- Modify: `skills/capabilities/skill-package/SKILL.md` (add one pointer in `## References`)

**Interfaces:**
- Produces: a reference file named `writing-for-agents.md` linked from `SKILL.md`. Later tasks (2–4) reuse the SAME principle wording; Task 5 records it in `SHARED-TEXT.md` under passage key `write-for-agents`.

- [ ] **Step 1: Create `references/writing-for-agents.md`** with exactly this content:

```markdown
# Writing for the agent reader, not the human

> Load this before editing any user-facing text of a skill (the `description`, the
> body, a reference). Most skills are authored by humans (or human+AI), so the prose
> drifts toward a *human* reader — it markets, narrates, and explains at length. The
> only reader that matters at runtime is an **agent** deciding whether to trigger the
> skill and how to follow it. Optimize for that reader.

## The principle
A human reader skims, infers intent, and forgives vague prose. An agent reader does
three concrete things with your text and nothing else:
1. **Selects** — reads the `description` to decide whether this skill fires.
2. **Follows** — reads the body to decide what to do, step by step.
3. **Pays** — every body token is re-read on every trigger for the whole session.

So write text that makes those three cheap and unambiguous, and cut everything that
only serves a human.

## Human-reader smells → agent-reader fix
- **Marketing / value-prop tone** ("a powerful, flexible toolkit for…") → state the
  concrete task and the trigger: "Exports a table to CSV. Use when the user asks to
  export or download tabular data."
- **Describing internal mechanics** ("uses a three-pass XML transform") → describe
  the *user intent* the skill serves; the agent matches against what the user asked,
  not how you built it.
- **Narrating the why at length** (paragraphs of rationale) → state what to do; give
  a rule's reason in one clause ("…because the output is read aloud by TTS").
- **First / mixed person** ("I can help you…", "we then…") → third person,
  imperative: "Processes…", "Run the validation script first."
- **Prose where a list/table/decision-tree is clearer** → the agent parses structure
  faster and follows it more reliably than paragraphs.

## Checklist (run before keeping an edit)
- [ ] `description` says WHAT it does AND WHEN to use it, third person, front-loaded.
- [ ] The literal keywords a user would actually type appear in the `description`.
- [ ] The body instructs (imperative) rather than narrates; each rule's reason is one
      clause, not a paragraph.
- [ ] No first person, no marketing adjectives, no ALL-CAPS unless a measured
      over/under-trigger problem demands it.
- [ ] Nothing in the text serves only a human reader (history, credits, prose that
      restates the obvious).

See also: [`description-optimization.md`](description-optimization.md) (the trigger
lever) and [`anti-patterns.md`](anti-patterns.md) (smells to review against).
```

- [ ] **Step 2: Append to `references/description-optimization.md`** — after the existing `## What a good description does` section (after item 4 "Front-load the key use case."), insert these two subsections:

```markdown

## Decompose the capability into concrete tasks
A single blurb ("Presentation editing") triggers worse than an enumerated task list,
because the agent matches user intent against concrete verbs. State the **scope**
(supported tasks), the **boundary** (unsupported tasks), and any **prerequisites**.

- **Instead of:** `Presentation editing`
- **Use:** `Create, edit, review and analyze PowerPoint (.pptx) presentations —
  including layouts, speaker notes, comments, formatting and XML extraction. Use when
  the user works with slides/PowerPoint/PPT/presentations, even if they don't say
  "pptx".`
- **Enumerate supported tasks** so each becomes a trigger surface: create
  presentation, modify existing presentation, extract text, analyze formatting, edit
  speaker notes.
- **Keyword enrichment** — include the terms users actually say: `slides`,
  `powerpoint`, `ppt`, `presentation`, `speaker notes`, `animations`.
- **State prerequisites/scope limits** the agent needs before triggering (e.g. "input
  must be a .pptx, not a Google Slides link").

## Metrics for the description (Layer 1)
The description is the **Description layer** — optimize it for discoverability and
routing, and measure it as such:
- **Selection accuracy** — right skill chosen for the task.
- **Precision** — fires only when it should (few false positives / near-miss triggers).
- **Recall** — fires whenever it should (few false negatives / missed triggers).
Tune these on a held-out should-trigger / should-NOT-trigger set (near-miss negatives
included), never on the iteration examples.
```

- [ ] **Step 3: Append to `references/concepts.md`** — at the end of the file, add:

```markdown

## The four optimization layers (this capability owns Description + Snippets)
A skill decomposes into four independently optimizable layers. This capability edits
the first two; the others live in sibling capabilities:

| Layer | What | Optimize for | Owner capability |
|---|---|---|---|
| 1. Description | when to trigger | discoverability, precision/recall | this capability (`description`) |
| 2. Snippets | how to do the task (body + references) | reasoning, token cost, fewer hallucinations | this capability (body/refs) |
| 3. Tools | executable capabilities | invocation accuracy, latency | the `tools` / `mcp-tool` capability |
| 4. Tool implementation | internal code | reliability, runtime | the `tools` capability (`code`) |

Routing a failure to the right layer is the core move: **retrieval/routing wrong →
fix the Description; reasoning/workflow wrong → fix the Snippets; capability missing
or hard to call → fix the Tools; slow/unreliable execution → fix the Implementation.**
This mirrors cap-evolve's own loop: identify the target layer → make one targeted
edit → `evaluate` on val → `gate` → keep or roll back.

## Snippet-organization patterns (Layer 2)
The body and references are *instructional snippets* — they teach the agent how to
work. High-leverage patterns:
- **Split one giant document into focused snippets.** Instead of one long README,
  organize into named sections/references the agent loads only when relevant
  (Overview · Reading content · <the hard workflow> · Troubleshooting · Limitations ·
  Examples). Lower context, faster reasoning, cheaper inference.
- **Decision trees** — teach *when* to use each workflow with a compact branch:
  `Need only text? → convert to Markdown.  Need comments? → read the XML.  Need
  animations? → use the XML workflow.` A branch table steers selection better than a
  paragraph.
- **Failure-handling / recovery blocks** — state the recovery, not just the happy
  path: `If unpack.py is unavailable: 1) search for unpack.py  2) validate the ZIP
  3) retry extraction.`
- **Example quality** — examples should resemble *real* user requests, not toy
  fragments. `Extract XML.` is weak; `If the user asks to modify speaker notes, first
  unpack the presentation and edit ppt/notesSlides XML.` teaches the actual mapping.
- **Redundancy removal** — repeated instructions cost tokens every trigger;
  consolidate duplicate guidance into one place.

## Metrics for snippets (Layer 2)
Success rate · token consumption · tool-selection accuracy · hallucination rate ·
time-to-completion. A snippet edit is an improvement only if it moves the objective
on the held-out val split without inflating body token cost.
```

- [ ] **Step 4: Append to `references/anti-patterns.md`** — at the end of the file, add:

```markdown

## Human-oriented writing (the meta-smell)
The prose reads like it was written for a person, not an agent. These all *feel*
polished to a human author and hurt the agent reader:
- **Marketing / value-prop adjectives** ("powerful", "flexible", "seamless"). → Carry
  no always-true, matchable information; replace with the concrete task + trigger.
- **Describing internal mechanics instead of user intent.** → The agent matches what
  the user asked for, not how the skill is built. Describe the intent.
- **Narrating the why at length.** → Every body line is a recurring per-session token
  cost; give a rule's reason in one clause, not a paragraph.
- **First/mixed person** ("I can help…"). → Inconsistent POV hurts discovery; use
  third-person imperative.
See [`writing-for-agents.md`](writing-for-agents.md) for the full principle and
checklist.
```

- [ ] **Step 5: Add the pointer in `SKILL.md`** — in the `## References` list at the bottom, add this bullet as the first reference entry (before `concepts.md`):

```markdown
- [`references/writing-for-agents.md`](references/writing-for-agents.md) — the
  write-for-the-agent-reader principle + checklist. Load before editing any
  user-facing text (description, body, references).
```

- [ ] **Step 6: Validate body budget and links**

Run:
```bash
cd /home/eranra/go/src/github.com/skillberry-ai/cap-evolve
python skills/capabilities/skill-package/scripts/token_report.py --path skills/capabilities/skill-package
```
Expected: JSON with `"over_budget": false`. Then verify every `references/…` link in `SKILL.md` resolves:
```bash
for f in $(grep -oE 'references/[a-z0-9-]+\.md' skills/capabilities/skill-package/SKILL.md | sort -u); do test -f "skills/capabilities/skill-package/$f" && echo "OK $f" || echo "MISSING $f"; done
```
Expected: every line prints `OK …` (including `references/writing-for-agents.md`).

- [ ] **Step 7: Commit**

```bash
git add skills/capabilities/skill-package/
git commit -m "docs(skill-package): add write-for-agents principle, task decomposition, snippet patterns"
```

---

## Task 2: `tools` — tool build-and-validate discipline (new reference) + framing

**Files:**
- Create: `skills/capabilities/tools/references/authoring-and-validation.md`
- Modify: `skills/capabilities/tools/references/concepts.md` (append 4-layer note + metrics)
- Modify: `skills/capabilities/tools/references/pitfalls.md` (append granularity + human-smell pitfalls)
- Modify: `skills/capabilities/tools/SKILL.md` (add ONE pointer line in `## References` — body is over budget, add nothing else)

**Interfaces:**
- Produces: `authoring-and-validation.md` linked from `tools/SKILL.md`. Task 5 records shared passages (`select-then-fill`, `validation-pipeline`, `write-for-agents`) in `SHARED-TEXT.md`.

- [ ] **Step 1: Create `references/authoring-and-validation.md`** with exactly this content:

```markdown
# Building tools & scripts an agent can find, fill, and run

> Load this when the edit *builds or specifies* a tool or a bundled script (not just
> rewording an existing one). Two things must be true of a good tool: (a) the agent
> can FIND it and FILL its arguments correctly, and (b) it FUNCTIONALLY WORKS and
> returns the desired output. This file covers both, plus the validation that proves
> it. The mental model behind (a) is in [`concepts.md`](concepts.md) (SELECT-then-FILL);
> failure modes are in [`pitfalls.md`](pitfalls.md).

## Contents
- 1. Write for the agent reader, not the human
- 2. Specify a tool completely before building it
- 3. Docstring rules that make slot-filling reliable
- 4. Validate that the tool functionally works
- 5. Tool granularity, composition, and observability
- 6. Bundled scripts: the agent-facing interface

## 1. Write for the agent reader, not the human
An LLM never sees your implementation — only `{name, description, parameters, examples}`
and the return value. Text written to impress a human (marketing tone, internal
mechanics, long rationale, first person) wastes the surface the agent actually reads.
Write third-person and imperative; state what the tool does, when to use it, when NOT
to, and the exact argument semantics. (Same principle across every capability.)

## 2. Specify a tool completely before building it
A tool the agent can use well starts from a complete spec. Capture every field —
gaps here become slot-filling and correctness failures later:
- **name** — a `verb_noun` that states the action and object (`get_order`, not `lookup`).
- **summary / intent** — one line of what it does; one line of why it exists.
- **inputs** — per parameter: `name`, `type`, `description`, `required`, `default`,
  and **`enum_values`** for any closed set (turns "guess a string" into "pick one").
- **outputs** — per field: `name`, `type`, `description`, `nullable`.
- **examples** — split into **happy_path**, **edge_cases**, and **error_cases**.
- **dependencies** — the other tools this one calls, with their compact signatures so
  the body calls them correctly.
- **error_model** — the failure conditions and what each returns/raises.
- **security_notes** — anything the code must refuse or sanitize.

**Error-case discipline.** An `error_case` whose expected result is an error *code*
(`NOT_FOUND`, `UNAUTHORIZED` — all-caps, no spaces) is a true negative the tool should
raise/return-as-error. An `error_case` whose expected result is a full-sentence
message, OR any tool that always returns a dict, should instead be a *positive* example
returning `{"success": false, "message": "..."}`. Don't model a recoverable,
message-bearing outcome as a thrown exception.

## 3. Docstring rules that make slot-filling reliable
The docstring is the contract the agent reads to fill arguments. Make it exact:
- **Derive the docstring from the CODE, not from a supplied description.** This
  prevents description/implementation drift — the doc always matches what runs.
- **Enumerate ALL allowed values for every constrained parameter.** If the code uses
  an enum, a `Literal`, a default, or validation logic, list every accepted value
  explicitly (do not generalize or summarize). Explain each hardcoded value the code
  depends on.
- **Pin units, format, and default per parameter** — "amount in whole US cents",
  "ISO-8601 date `YYYY-MM-DD`", "default: 10".
- **Keep it parseable:** a standalone `Parameters:` section with one indented
  `<name> (<type>): <description>` line per argument, and a standalone `Returns:`
  section with the return type and description. Retain a `Raises:` / errors section —
  documented failure modes are guidance the model uses to avoid a bad call, not clutter.

## 4. Validate that the tool functionally works
Building is not done until the tool is proven to work. A robust build/validate loop:
- **Retry generation on validation failure** (a few attempts) rather than shipping a
  broken tool.
- **Generate unit tests from the provided examples** — assert happy_path and
  edge_cases return the expected output, and that error_cases raise/return the expected
  error. Prefer testing against the *provided* examples (including negatives) over
  free-invented tests.
- **Execute the tests**, don't just generate them — execution validation catches what
  static checks miss.
- **Syntax + signature checks** — the code parses (AST), defines the named function,
  and matches the declared signature (strict signature from name + inputs).
- **Evaluation-score threshold** — hold the candidate to a minimum quality score;
  reject below it.
- **Security / unwanted-content checks** — refuse code that does something the spec
  forbids or embeds disallowed content.
- **Recovery** — on a codegen failure, prefer reusing an already-validated tool over
  emitting a stub.

## 5. Tool granularity, composition, and observability
- **Granularity** — avoid tools that are too small (one trivial call the agent could
  inline) or too large (`office_tool()` that does everything). Aim for one clear
  capability per tool: `extract_text()`, `extract_xml()`, `validate_file()`,
  `repair_document()`.
- **Composition** — design tools that compose naturally
  (`extract_xml() → modify_notes() → repackage()`) instead of one monolithic
  executable. A composite tool is worth its slot only when the chain it replaces is
  frequent and error-prone.
- **Observability (Layer 4, invisible to the LLM)** — the implementation should be
  robust (retries, validation, graceful failures, informative errors) and, where it
  matters, collect execution time / failures / retries so the tool can be optimized
  over time. Algorithmic and memory improvements (streaming, caching, parallelism)
  live here and never change the tool's contract.

## 6. Bundled scripts: the agent-facing interface
A script an agent runs must be designed for a non-interactive reader:
- **Never prompt interactively.** Agents run in non-interactive shells; a TTY prompt
  hangs forever. Take all input via flags / env / stdin, and fail with a clear message
  naming the missing flag.
- **Document the interface in `--help`** — a brief description, the flags, and usage
  examples. This is how the agent learns to call the script; keep it concise.
- **Structured output** — prefer JSON/CSV/TSV on stdout; send progress/warnings to
  stderr so the agent can parse clean data while still seeing diagnostics.
- **Meaningful, documented exit codes** — distinct codes for distinct failures
  (not-found, bad-args, auth), listed in `--help`.
- **Idempotency & `--dry-run`** — agents retry; "create if not exists" beats "fail on
  duplicate", and a `--dry-run` lets the agent preview stateful/destructive actions.
- **Truncation-safe output** — many harnesses truncate large tool output; default to a
  summary and support `--offset`/`--output` (or write to a file) for more.
- **Self-contained dependencies** — declare deps inline (PEP-723 `# /// script` for
  Python `uv run`; `npm:`/`bun` pins for JS) and pin versions so runs are reproducible.
```

- [ ] **Step 2: Append to `references/concepts.md`** — at the end of the file, add:

```markdown

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
```

- [ ] **Step 3: Append to `references/pitfalls.md`** — at the end of the file, add:

```markdown

## Tool granularity that fights the agent
A tool that is too small (a one-liner the agent could inline) clutters the choice set;
a tool that is too large (`office_tool()` doing everything) hides its real behavior and
can't be selected precisely.
- **Detect:** a rarely-chosen trivial tool, or one mega-tool whose description needs
  five "use when" clauses.
- **Fix:** one clear capability per tool; split the mega-tool into composable pieces
  (`extract_text`, `extract_xml`, `validate_file`, `repair_document`).

## Human-oriented tool text (the meta-smell)
Descriptions and docstrings written to read well for a person — marketing adjectives,
internal-mechanics narration, long rationale, first person — waste the surface the
agent selects and fills from.
- **Detect:** the description carries no always-true matchable info (triggers, units,
  allowed values, failure modes) — just polished prose.
- **Fix:** third-person imperative; what/when/when-not; per-argument units, allowed
  values, defaults; retained failure modes. See
  [`authoring-and-validation.md`](authoring-and-validation.md) §1.
```

- [ ] **Step 4: Add ONE pointer line in `tools/SKILL.md`** — in the `## References` list at the bottom, add as a new bullet (do NOT add any other text to the body — it is over budget):

```markdown
- [`references/authoring-and-validation.md`](references/authoring-and-validation.md) —
  how to BUILD/specify a tool or bundled script the agent can find, fill, and run
  (spec fields, docstring rules, the validate pipeline, script interface). Load when
  creating a new tool/compose/script, not when only rewording one.
```

- [ ] **Step 5: Validate links (body budget was already over before this change; confirm we did not grow it)**

Run:
```bash
cd /home/eranra/go/src/github.com/skillberry-ai/cap-evolve
python skills/capabilities/skill-package/scripts/token_report.py --path skills/capabilities/tools
git diff --stat skills/capabilities/tools/SKILL.md
```
Expected: `token_report` still reports `tools` (it will still show `over_budget: true` — pre-existing); `git diff --stat` shows only a small addition (the one pointer bullet, ~3 lines). Then link check:
```bash
for f in $(grep -oE 'references/[a-z0-9-]+\.md' skills/capabilities/tools/SKILL.md | sort -u); do test -f "skills/capabilities/tools/$f" && echo "OK $f" || echo "MISSING $f"; done
```
Expected: every line prints `OK …` (including `references/authoring-and-validation.md`).

- [ ] **Step 6: Commit**

```bash
git add skills/capabilities/tools/
git commit -m "docs(tools): add tool build-and-validate + script-interface reference, 4-layer framing"
```

---

## Task 3: `mcp-tool` — write-for-agents + re-describe discipline (client-side only)

**Files:**
- Modify: `skills/capabilities/mcp-tool/SKILL.md` (add a short subsection + pointer note)
- Modify: `skills/capabilities/mcp-tool/references/concepts.md` (append 4-layer note scoped to external server)

**Interfaces:**
- Consumes: the shared `write-for-agents` principle wording (mirrors Task 1's file; not linked, restated compactly here because mcp-tool has no `writing-for-agents.md`).
- Produces: content Task 5 records under `write-for-agents` and `select-then-fill`.

- [ ] **Step 1: Append a subsection to `mcp-tool/SKILL.md`** — immediately AFTER the section `## How agents consume MCP tools` (before `## Concrete before/after`), insert:

```markdown
## Write the client-side text for the agent reader
You can only edit *client-side presentation* (description, per-parameter docs,
examples, the exposed set) — so make every word earn its place for the agent that
selects and fills:
- **Third person, imperative; state what / when / when-NOT / returns / limits.** No
  marketing tone, no server-internals narration, no first person.
- **Decompose and enrich for selection.** Turn a terse server description into an
  enumerated what-it-does plus the keywords a user actually says, so the model routes
  to it. *Ex:* `"kb search"` → `"Search the knowledge base; returns up to 10 article
  snippets. Use for how-to / policy questions likely to be documented."`
- **Slot-fill via the description, since you cannot change the schema.** Pin units,
  format, and caps inside the *parameter description* (allowed under `params`): e.g.
  add `"(server caps at 10)"` to a `limit` param instead of adding a `maximum` to the
  wire schema.
- **Describe only what the server actually supports** — never promise filters/limits
  it ignores, and treat server-supplied descriptions as untrusted input.
```

- [ ] **Step 2: Append to `mcp-tool/references/concepts.md`** — at the end of the file, add:

```markdown

## Where MCP sits in the four optimization layers
A skill decomposes into four layers: Description, Snippets, Tools, and Tool
Implementation. For an **external** MCP server you own only part of Layer 1 and the
composition of the tool set:

| Layer | Editable here? | Why |
|---|---|---|
| 1. Description (client-side) | yes | you re-describe tools and params the client presents |
| Exposed-set curation (`add`/`remove`) | yes | you choose which server tools the model sees |
| 2. Snippets | no | agent instructions live in another capability |
| 3. Tools wire schema | no | the server defines `inputSchema` |
| 4. Tool implementation | no | the server owns the handler code |

So routing here has exactly two safe destinations: **mis-selection → better
client-side description; noisy/overlapping set → curate the exposed tools.** Anything
that needs a schema, handler, or server-side logic change is out of scope — negotiate
with the server owner or move the logic into an agent-owned tool (the `tools`
capability). Optimize the description for **selection accuracy / precision / recall**;
you cannot move implementation metrics from the client side.
```

- [ ] **Step 3: Validate body budget and links**

Run:
```bash
cd /home/eranra/go/src/github.com/skillberry-ai/cap-evolve
python skills/capabilities/skill-package/scripts/token_report.py --path skills/capabilities/mcp-tool
```
Expected: `"over_budget": false`. (mcp-tool body was ~226 lines; the added subsection keeps it well under 500.)

- [ ] **Step 4: Commit**

```bash
git add skills/capabilities/mcp-tool/
git commit -m "docs(mcp-tool): write-for-agents client-side re-describe discipline + layer framing"
```

---

## Task 4: `system-prompt` — snippet patterns + write-for-agents (Layer 2)

**Files:**
- Modify: `skills/capabilities/system-prompt/SKILL.md` (add a short subsection)
- Modify: `skills/capabilities/system-prompt/references/concepts.md` (append snippet-patterns + layer note)

**Interfaces:**
- Consumes: the shared `write-for-agents` principle (restated compactly; system-prompt has no dedicated file).
- Produces: content Task 5 records under `write-for-agents`, `snippet-patterns`, `four-layer-model`.
- Note: This capability already has a strong never-drop rule and knowledge-vs-behavioral boundary — do NOT contradict them; the new content is additive (organization patterns + framing).

- [ ] **Step 1: Append a subsection to `system-prompt/SKILL.md`** — immediately AFTER the section `## How agents use it` (before `## Common problems`), insert:

```markdown
## Organize the prompt for the agent reader (snippet patterns)
The prompt is a *snippet* the agent re-reads every turn — organize it the way an agent
parses fastest, and write it for that reader (third person, imperative, no marketing
tone, reason-in-one-clause):
- **Decompose instructions into concrete, ordered steps** rather than one dense
  paragraph; number them when order matters.
- **Decision trees for when-to-do-what.** A compact branch (`If X → do A; if Y → do B`)
  steers the act/refuse and tool-choice decisions better than prose.
- **Failure-handling / recovery lines** — state the recovery path, not only the happy
  path (e.g. "If the lookup returns empty, ask for the id instead of guessing.").
- **Redundancy removal** — repeated guidance dilutes attention and costs tokens every
  turn; consolidate duplicates into one rule (never dropping a distinct constraint —
  see the never-drop rule below).
These are organization moves; they never loosen a decision/permission rule (unbounded
blast radius) — keep the narrowing-only discipline from `references/concepts.md`.
```

- [ ] **Step 2: Append to `system-prompt/references/concepts.md`** — at the end of the file (after `## Sources`), add:

```markdown

## The four optimization layers (this capability owns the Snippets layer)
A skill/agent decomposes into four independently optimizable layers — Description
(when to trigger), **Snippets** (how to do the task — the system prompt/policy lives
here), Tools (executable capabilities), and Tool Implementation (internal code). This
capability edits the Snippets layer. Route the failure to the owning layer:
retrieval/routing wrong → Description; **reasoning/workflow/output-shape wrong →
Snippets (here)**; a capability missing or hard to call → Tools; slow/flaky execution
→ Implementation. A prompt edit fixes only *knowledge* gaps in the Snippets layer —
behavioral stalls belong to the Tools/Implementation layers, not more prose (see the
knowledge-vs-behavioral section above).

## Snippet metrics (Layer 2)
Success rate · token consumption · tool-selection accuracy · hallucination rate ·
time-to-completion. A prompt edit is an improvement only if it moves the objective on
the held-out val split without inflating length — length is not safety.
```

- [ ] **Step 3: Validate body budget and links**

Run:
```bash
cd /home/eranra/go/src/github.com/skillberry-ai/cap-evolve
python skills/capabilities/skill-package/scripts/token_report.py --path skills/capabilities/system-prompt
```
Expected: `"over_budget": false`. (system-prompt body was ~198 lines; stays under 500.)

- [ ] **Step 4: Commit**

```bash
git add skills/capabilities/system-prompt/
git commit -m "docs(system-prompt): snippet-organization patterns + four-layer framing"
```

---

## Task 5: External duplication-tracking table

**Files:**
- Create: `skills/capabilities/SHARED-TEXT.md`

**Interfaces:**
- Consumes: the passages introduced in Tasks 1–4 (their file locations).
- Produces: a maintenance index (NOT a skill reference; not linked from any SKILL.md).

- [ ] **Step 1: Create `skills/capabilities/SHARED-TEXT.md`** with exactly this content:

```markdown
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
```

- [ ] **Step 2: Verify the table's locations exist**

Run:
```bash
cd /home/eranra/go/src/github.com/skillberry-ai/cap-evolve
for f in \
  skills/capabilities/skill-package/references/writing-for-agents.md \
  skills/capabilities/tools/references/authoring-and-validation.md \
  skills/capabilities/mcp-tool/references/concepts.md \
  skills/capabilities/system-prompt/references/concepts.md ; do
  test -f "$f" && echo "OK $f" || echo "MISSING $f"; done
```
Expected: every line prints `OK …`.

- [ ] **Step 3: Commit**

```bash
git add skills/capabilities/SHARED-TEXT.md
git commit -m "docs(capabilities): add SHARED-TEXT duplication-tracking index"
```

---

## Task 6: Final consistency pass & verification

**Files:** none created; verification + fixes only.

- [ ] **Step 1: Confirm no infra/code was touched**

Run:
```bash
cd /home/eranra/go/src/github.com/skillberry-ai/cap-evolve
git diff --name-only main... | grep -vE '\.md$' || echo "GOOD: only .md files changed"
```
Expected: prints `GOOD: only .md files changed` (no `.py`, `.yaml`, etc.).

- [ ] **Step 2: Re-run body-budget check on all four capabilities**

Run:
```bash
for c in skill-package tools mcp-tool system-prompt; do
  echo "== $c =="; python skills/capabilities/skill-package/scripts/token_report.py --path skills/capabilities/$c | grep -E 'body_lines|over_budget';
done
```
Expected: `skill-package`, `mcp-tool`, `system-prompt` show `over_budget: false`. `tools` shows `over_budget: true` — pre-existing and unchanged by this work (verify its `body_lines` did not increase materially vs. the ~661 baseline; only the one pointer bullet was added).

- [ ] **Step 3: Verify all reference links across the four capabilities resolve**

Run:
```bash
for c in skill-package tools mcp-tool system-prompt; do
  for f in $(grep -rhoE 'references/[a-z0-9-]+\.md' skills/capabilities/$c/SKILL.md skills/capabilities/$c/references/*.md 2>/dev/null | sort -u); do
    test -f "skills/capabilities/$c/$f" && echo "OK $c/$f" || echo "MISSING $c/$f";
  done; done | grep MISSING && echo "FIX MISSING LINKS ABOVE" || echo "GOOD: all reference links resolve"
```
Expected: `GOOD: all reference links resolve`.

- [ ] **Step 4: Confirm no nested references were introduced**

The one-level-deep rule: a `references/*.md` file must not link to another `references/*.md`. The `writing-for-agents.md` and `authoring-and-validation.md` files link to sibling references (`description-optimization.md`, `anti-patterns.md`, `concepts.md`, `pitfalls.md`). This is a known convention question — sibling cross-links within the same skill's `references/` are for human navigation and are acceptable here because they point to files already linked directly from `SKILL.md` (the agent reaches each from the top level, not only via the sibling link). Verify each sibling-linked target is ALSO linked from its `SKILL.md`:

Run:
```bash
cd /home/eranra/go/src/github.com/skillberry-ai/cap-evolve
grep -oE 'references/[a-z0-9-]+\.md' skills/capabilities/skill-package/SKILL.md | sort -u
echo "--- targets cross-linked inside skill-package references ---"
grep -rhoE '\]\(references/[a-z0-9-]+\.md\)|\]\([a-z0-9-]+\.md\)' skills/capabilities/skill-package/references/*.md | sort -u
```
Expected: every reference cross-linked between skill-package references (`description-optimization.md`, `anti-patterns.md`, `concepts.md`) also appears in the `SKILL.md` reference list. If a cross-linked reference is NOT in `SKILL.md`, add it to `SKILL.md`'s `## References` list (so it is reachable from the top level), then re-commit. Repeat the same check for `tools`.

- [ ] **Step 5: Final commit if Step 4 required a fix (otherwise skip)**

```bash
git add skills/capabilities/
git commit -m "docs(capabilities): ensure cross-linked references are reachable from SKILL.md"
```

- [ ] **Step 6: Summary check against the spec**

Confirm each spec item has a task: write-for-agents principle (T1/T3/T4 + tools T2), 4-layer model (all), tool build/validate discipline (T2), script interface (T2), snippet patterns (T1/T4), mcp client-side (T3), SHARED-TEXT table (T5), docs-only (T6 Step 1). If any gap remains, add a task; otherwise the plan is complete.

---

## Self-review notes (author)

- **Spec coverage:** write-for-agents → T1 (canonical) + T2/T3/T4 (scoped); 4-layer model + route-to-layer + metrics → T1/T2/T3/T4; tool spec fields + docstring rules + validation pipeline + error-case discipline → T2; granularity/composition/observability → T2; script-interface rules → T2; snippet patterns → T1/T4; mcp client-side + out-of-scope layers → T3; SHARED-TEXT tracking → T5; docs-only guarantee → T6. No gaps.
- **Placeholder scan:** all new-file content is provided verbatim; edit insertions specify exact anchor sections and full text. No TBD/TODO.
- **Consistency:** passage keys in T5 (`write-for-agents`, `four-layer-model`, `route-to-layer`, `layer-metrics`, `select-then-fill`, `validation-pipeline`, `script-interface`, `snippet-patterns`, `task-decomposition`) match the section titles inserted in T1–T4.
- **Budget:** `tools/SKILL.md` is pre-existing over budget; T2 adds only a pointer bullet and puts all content in a new reference — verified by T2 Step 5 and T6 Step 2.
```

