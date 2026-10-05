# The documentation contract for one tool

Load this when the fix is documentation rather than code — you are sharpening a
description, per-parameter docs, or error text and want to know what a complete tool
doc contains. A worked, fully-documented tool is `examples.md` §3g.

## Every tool needs all of these

A tool's documentation is its contract. Every tool — primitive or wrapper — needs
**all** of these, or the model is left guessing:

- a **crisp description**: what it does, when to use it, and when NOT to (the boundary
  against the nearest sibling tool);
- an **"important points"** note for any non-obvious behavior or precondition;
- a **Raises / errors** section listing the failure conditions (keep these — see below;
  they are a guard rail, not clutter);
- a **per-parameter description** with units / format / allowed values / default;
- one **generic, always-valid usage example** (the shape of a call, never one task's
  literal id/date/city).

## The description is the model's contract, not flavor text

It is the *only* information the model has about *which* tool to call and *what
argument values are legal*. A good description always states, in always-true terms
(never one task's specifics):

- **When to use / when not to use** — explicit triggers, and the boundary against the
  nearest sibling tool ("use X for a single record by id; use Y to search across
  records").
- **Argument semantics** — for each parameter: its meaning, **units**, **allowed values
  / format**, and **default**. "amount in whole US cents" beats "the amount"; "ISO-8601
  date `YYYY-MM-DD`" beats "the date".
- **Preconditions and failure modes** — what must be true *before* the call, and what
  the tool **raises / returns on error**. This is the model's chance to avoid a bad
  call. **Do NOT strip `Raises:`/error-condition text to make the description
  "cleaner."** Knowing a call raises `ValueError: gift card balance too low` is exactly
  what lets the model pick a different payment method instead of failing the task.
  Stripping error info removes a guard rail; it does not improve selection.
- **A short, always-valid usage example** — one concrete well-formed call that is
  correct for *any* input (e.g. the shape of a list element), never a single benchmark
  task's literal values.

## Why fewer, sharper tools beat many vague ones

Selection degrades as the toolset grows: benchmarks like the Berkeley Function-Calling
Leaderboard include a dedicated "relevance detection" category precisely because models
hallucinate calls when no tool fits, and ToolLLM had to add a *retriever* to cope with
thousands of tools. The practical implication for this capability: **fewer, sharper,
non-overlapping tools beat many vague ones** — so a documentation pass that reduces
overlap between two siblings is worth more than one that polishes either alone.
