# Optimize the system prompt — ship several REAL, SAFE, VERIFIED fixes this iteration

{{TARGET_READER}}

{{FOCUS_SUMMARY}}

{{EMPTY_SEED}}

GOAL: raise the eval score as much as you can THIS iteration, then STOP (the harness
re-scores you — don't run evaluation yourself). The edit surface is ONE file: the store
skill's `SKILL.md`, which the Skillberry Proxy-Agent injects as the agent's system prompt.
There are no tools to edit in this approach.

Make **AS MANY real fixes as you can this iteration — solve many issues across many
trajectories, not just the biggest one.** Diagnose EVERY failure cluster in `./trajectories/`
and ship a prompt fix for each one that passes the three tests below. Breadth is the goal.

The ONLY brake on breadth is regression: every edit must pass all three tests, because a
single speculative edit that breaks a passing task can sink an iteration of good work.

## How SKILL.md reaches the agent (read before editing)
- The agent under test is AppWorld's own ReAct code agent with its own, unchanged stock prompt.
  It writes Python in a REPL against the apps' APIs, one ```python block per step.
- Every LLM call goes through the Skillberry Proxy-Agent. The proxy:
  1. drops the client's stock prompt, keeping the history from the real task turn
     ("Using these APIs, now generate code to solve the actual task: … Task: …") onward;
  2. renders `SKILL.md` with the task's supervisor (`{{ main_user.first_name }}`,
     `{{ main_user.last_name }}`, `{{ main_user.email }}`, `{{ main_user.phone_number }}`);
  3. sends it as the FIRST message, role `system`, followed by that real history.
- So `SKILL.md` replaces the stock prompt's demo and key instructions. The seed is a byte copy
  of AppWorld's stock prompt up to the real task turn, plus a short header saying the
  USER/ASSISTANT turns are a worked few-shot example.
- Because the demo arrives as TEXT inside one system message (not as real chat turns), the model
  can mistake it for a transcript to continue. A known failure mode: in one reply the model
  writes several steps and invents `USER: Output:` turns itself. If the traces show it, fix it in
  the prompt (an explicit, unmissable "reply with ONE step: one sentence and one ```python block,
  then stop; never write USER: or Output: yourself" rule, and/or a clearer demo framing).

## SKILL.md rules (the lint enforces them; a violating candidate is rejected unrun)
- `SKILL.md` is the ONLY file in the skill folder. Do not add files: any other text file would
  be injected too, and a script would become a tool.
- Keep the frontmatter (`name: my_skill`) as the first lines.
- The ONLY placeholders are `{{ main_user.first_name }}`, `{{ main_user.last_name }}`,
  `{{ main_user.email }}` and `{{ main_user.phone_number }}`. Keep each of them at least once;
  never add another `{{ … }}`, a `{% … %}` block or a filter, and never `{{ instruction }}`
  (the real task turn comes from the client, after the proxy's marker).
- The app list (the JSON array of 11 apps in the demo's `show_app_descriptions` output) is
  AppWorld's own text: keep it VERBATIM (`{AW_APP_DESCRIPTIONS}` holds it).
- Keep the demo's `USER:` / `ASSISTANT:` turns and their format (one ```python block per
  ASSISTANT turn). At most 8,500 tokens.
- Everything must be GENERAL: no 8-gram copied from any task instruction, no supervisor
  name/email/phone, no task-specific value. AppWorld permits generic hints, not task-specific
  ones.

How episodes run and are scored: `./guidance/sources/react_agent_notes.md` (REPL, trimming,
termination, blocked modules) and `./guidance/sources/api_index.md` (every app and API). The
stock prompt is at `{AW_REFERENCE}/stock_react_instructions.txt` when present.
`./trajectories/` holds one JSON per rollout: `input.instruction`, `rollout.trace` (per step:
thought, reasoning excerpt, code, output truncated to 2,000 chars), `rollout.metadata`
(termination, steps, tokens, failed requirement texts, collateral-damage flag) and
`score.feedback`. A requirement text says WHAT the evaluator checked, never the gold value.
Do NOT try to find gold answers, solutions or test data anywhere on disk, and do NOT run
AppWorld episodes yourself (the harness re-scores you).

LINT BEFORE YOU STOP — a failing candidate is rejected without being run:
`AW_LINT_CACHE={AW_LINT_CACHE} AW_APP_DESCRIPTIONS={AW_APP_DESCRIPTIONS} {AW_PY} {AW_BB_LINTS} .`
must print `"ok": true`.

## The THREE TESTS every change must pass
1. **REAL** — it targets a cluster that is FAILING in THIS iteration's `./trajectories/`. Never
   edit for a hypothetical problem, never touch a rule only exercised by already-PASSING tasks.
2. **SAFE (bounded blast radius)** — would this edit change what the agent DOES on ANY
   currently-passing task? A NARROWING rule (states the exact condition) is the safe default. A
   change to a GLOBAL decision rule (loosening "X may do Y", relaxing an autonomy or
   collateral-damage rule) flips behavior for the whole class: allowed ONLY if you have read the
   passing tasks in that class and confirmed none relied on the old behavior. Name the passing
   tasks in each edit's blast-radius class.
3. **VERIFIED** — you have shown it addresses its target (see VERIFY-THE-FIX). An edit you cannot
   verify is a guess — drop it.

## Choose the lever by FAILURE TYPE (prompt levers)
- **RULE VIOLATION** — the agent breaks a rule it already has (e.g. guesses an id instead of
  reading it, stops paging early). Make the rule unmissable: a checklisted step in the key
  instructions, or a worked counterexample in the demo, placed where the agent decides.
- **CAPABILITY GAP / ACTION STALL** — the agent narrates an action and never executes it, or has
  no reliable procedure. Write an explicit, ordered, unavoidable procedure (and show it in the demo).
- **KNOWLEDGE GAP** — a format/criterion/fact the agent cannot derive (an API convention the docs
  leave implicit). Add a precise, GENERAL rule.
- **DECISION / PERMISSION** — NEVER loosen a global decision rule; add an ADDITIVE rule that
  NARROWS (states the exact predicate).
- **REPLY FORMAT** — invented turns, several code blocks, missing code block: tighten the output
  contract (see "How SKILL.md reaches the agent").
Consolidate instead of only appending; never delete a needed rule (change/merge it instead).

## VERIFY-THE-FIX (for each kept edit)
- Quote the failing step from the trace and the new prompt text that addresses it; confirm the
  rule is general (no task-specific value) and placed where the agent reads it before deciding.
- For a decision/permission edit, list the passing tasks in the same class and confirm the edit
  would not flip their action.
Record one line per edit in PROCESS.md. An edit with no verification line is unverified — drop it.

## Read these first (everything is in this working directory)
- **`./guidance/system-prompt/SKILL.md` — READ IT IN FULL**; it is the menu of prompt improvement
  types (rewrite, consolidate, add a sourced rule, reorder, tighten the output contract, soften
  over-strong wording). Apply MULTIPLE different types this iteration.
- `./guidance/diagnose/SKILL.md` — the failure-clustering method. Use it.
- `./trajectories/`, `./LEDGER.md`, `./JOURNAL.md`, `./RUNMAP.md` + `./prior_iterations/<id>/`
  — as in every cap-evolve iteration: facts, handover with RESULT lines, and every prior diff.
  If the most recent RESULT is REJECTED, keep the edits that did not appear in its `broke={...}`
  and drop or redesign the ones that did.
- `./PROCESS.md` — your REQUIRED explainability file for THIS iteration (template inside).
- `./guidance/optimizer/<name>.md` — your agent's subagent/parallelism features (optional).
{{BENCH_REPO}}

## Process (do this, then STOP)
**Parallelism:** {{PARALLEL_NOTE}}
1. Read the system-prompt SKILL + the diagnose method + the cross-iteration files.
2. Diagnose THIS iteration's `./trajectories/` ONLY. Cluster ALL failures by shared root cause.
   RANK clusters by LEVERAGE = (# failing tasks × trials × score recoverable).
3. For EACH cluster, pick the strongest prompt lever and draft the edit; run it through the THREE
   TESTS; keep it only if it passes all three.
4. Ship every passing edit together in this ONE candidate (`SKILL.md`), lint it, and STOP after
   step 5.
5. Fill `PROCESS.md` and APPEND your entry to `JOURNAL.md` (intent only; the framework stamps the
   RESULT).

## NON-OVERFITTING
Every edit encodes a GENERAL rule that holds across the whole class of inputs — never a literal
that special-cases one task (its id, target, name or expected answer).

## Handover (REQUIRED before you STOP)
- **PROCESS.md**: the ranked cluster list (with leverage + tag), every kept edit + its lever, the
  VERIFY-THE-FIX + blast-radius line per edit, what you skipped and why.
- **DIAGNOSIS.json** (optional): the schema described in the PROCESS.md template; `files` is
  `["SKILL.md"]`.
- **JOURNAL.md**: append ONE entry below the marker; never edit earlier entries.

{{FAILURES}}
{{PASSING}}
{{CAP_BRIEF}}
{{ALGO_BRIEF}}

## Self-check before STOP
- Every kept edit passes the THREE TESTS and has its verify + blast-radius line in PROCESS.md.
- You addressed EVERY failing cluster you found, with MULTIPLE different prompt improvement types.
- `SKILL.md` is the only file; the frontmatter, the four main_user placeholders, the verbatim app
  list and the USER:/ASSISTANT: demo are intact; the lint prints `"ok": true`.
- No edit hardcodes a task-specific id/value/date/answer, and no decision rule was loosened.
