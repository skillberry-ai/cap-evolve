---
name: agent-harness
description: Optimize the harness around an agent's model — the agent loop and its stopping rules, context management and compaction, cross-run memory that lets the agent learn from past runs, tool-error handling and retries, sampling and verification, and sub-agents. Use when traces show a loop-level failure that no prompt or tool edit reaches - the agent repeats the same call, ends without acting or without checking its work, loses early facts as the context grows, drowns in long tool outputs, repeats mistakes past runs already made, or gives up on a recoverable error. The artifact is harness.json plus memory/lessons.jsonl plus hooks/*.py, wired by the adapter.
component: capability
argument-hint: "--path DIR"
allowed-tools: Read, Write, Edit, Bash
provides: [candidate]
needs: []
sources: [ace, reasoningbank, awm, reflexion, dynamic-cheatsheet, experience-following, complexity-trap, swe-agent, anthropic-context-engineering, manus-context-engineering, anthropic-think-tool, langchain-harness-engineering, anthropic-multi-agent, cognition-multi-agent, large-language-monkeys, dgm, adas]
---

# Capability: agent harness

The harness is every piece of code and configuration that is not the model: the
loop that calls it, what goes into its context, what it remembers between tasks,
how tool errors come back, how many samples it draws, and whether it delegates.
Changing only the harness, with the model fixed, moved a coding agent from 52.8% to
66.5% on Terminal Bench 2.0 (LangChain, 2026). This capability makes that layer the
optimizable artifact.

Other capabilities own the neighbouring layers. What the agent is *told* belongs to
`system-prompt`; what a tool *does* or how it is *described* belongs to `tools` or
`mcp-tool`. Use this capability when the failure is in *how the loop runs*: the same
instruction and the same tools would succeed under a different loop. Classify the
failure clusters first (`./guidance/diagnose/SKILL.md`, when present).

## The artifact

```
<capability_dir>/
  harness.json           settings the adapter wires into the agent (sections below)
  memory/lessons.jsonl   cross-run lessons, one JSON object per line
  hooks/*.py             harness code the adapter imports (compaction, checks, ...)
  harness_policy.json    optional: allowed edit kinds and the "wired" setting list
```

`harness.json` sections: `loop`, `context`, `memory`, `tool_errors`, `sampling`,
`subagents`, and free-form `custom`. The known keys, types and ranges are in
`scripts/abstract.py` (`SCHEMA`); `validate()` rejects a wrong type or an out-of-range
value and warns on an unknown key.

**A setting does something only if the adapter reads it.** The adapter author lists
the paths it wires in `harness_policy.json` (`"wired": ["loop.*", "memory.*"]`), and
`apply()` refuses a `set` on any other path. If the policy still says `"*"`, open the
adapter and confirm the key is read before you spend a gate evaluation on it.

## Pick the lever by trace symptom

Each row is one bounded edit. Ship every row the traces call for in one candidate,
each one aimed at a named cluster. Depth and sources for each row:
[`references/concepts.md`](references/concepts.md).

| Trace symptom | Edit | Setting / file |
|---|---|---|
| The same mistake recurs across tasks; the agent re-derives a routine every task | **Distill a lesson** from the cluster into cross-run memory | `memory.mode`, `memory/lessons.jsonl` |
| The same tool call (or edit to the same file) N times in a row | **Repeat detection** that nudges, then stops | `loop.repeat_limit`, `loop.on_repeat` |
| The agent ends after reading its own work and judging it fine | **Final check before exit** against the task spec | `loop.final_check`, a `hooks/` check |
| The agent explains or confirms, then stops without the write | **No-action nudge** when the episode ends with no mutating call | `loop.no_action_nudge` |
| Long tool outputs fill the context; early facts are lost late in the task | **Observation masking** of old tool outputs, then summaries only if needed | `context.compaction`, `context.keep_last_turns`, `context.tool_output_max_chars` |
| The agent drifts from the goal on long tasks | **Recitation**: a todo / goal block rewritten at the end of context | `context.recitation`, `loop.plan_tool` |
| The agent repeats a failed call after the error was hidden or truncated | **Keep errors in context** with the full message | `context.keep_errors`, `tool_errors.feed_error_back` |
| A transient failure (timeout, rate limit) ends the task | **Bounded retry** with backoff, only on named error classes | `tool_errors.max_retries`, `tool_errors.retry_on` |
| Malformed tool arguments reach the tool | **Validate arguments** against the schema and return the error before the call | `tool_errors.validate_args` |
| Policy-heavy, sequential decisions go wrong after a tool result | **A think step** between tool results | `loop.think_tool` |
| Correct answers appear in some trials but not others, and a checker exists | **Best-of-N with a verifier** | `sampling.n_candidates`, `sampling.selector` |
| Independent sub-questions overflow one context | **Sub-agents** that return short summaries | `subagents.*` |
| The agent stops at the step limit while making progress / loops until the limit | **Raise / lower the step budget** | `loop.max_steps` |

Prefer the cheapest row that reaches the cluster. The first eight rows cost little per
task; best-of-N and sub-agents multiply the model calls (see "Cost" below).

## Cross-run memory — how the agent learns from past runs

Memory is the main new lever here: the agent starts each task with distilled lessons
from earlier runs instead of from zero. Reflexion, ExpeL, Agent Workflow Memory,
Dynamic Cheatsheet, ACE and ReasoningBank all report gains from this. AWM, for
example, reports +24.6% and +51.1% relative success on Mind2Web and WebArena.

**In this framework the optimizer writes the memory, not the agent.** Between
iterations you read the train/val traces, distill lessons, and add them with
`add_lesson`. During a scored rollout memory is read-only. Two reasons, both
mechanical:

- A rollout that writes memory makes its score depend on task order and trial number,
  so the paired gate compares different things on each side.
- An agent that writes memory during evaluation learns from val and test feedback.
  Test is sealed and scored once. `validate()` fails a candidate with
  `memory.write_during_eval: true` or with a lesson whose `source_split` is `test`.

The gate then measures what you want to know: does a fixed memory, read at the start
of each task, raise the score on tasks it was not distilled from?

**A lesson is a general rule with a trigger and its evidence.**

```json
{"id": "confirm-write", "when": "after any write tool call on a record",
 "do": "read the record back and compare each requested field before replying",
 "evidence": "train: 4 traces reported success after a write that set the wrong field",
 "source_split": "train"}
```

Rules for lessons, each from a measured failure mode in the sources:

1. **Write from a cluster, never from one task.** A lesson that names a record id,
   date or answer is overfitting; `validate()` warns on id-like literals.
2. **Learn from failures and successes.** ReasoningBank distills strategies from both;
   a lesson from a passing trace says what to keep doing.
3. **Add incremental entries; do not rewrite the whole memory.** ACE names the
   failure "context collapse": repeated rewriting erodes detail. Use `add_lesson` and
   `update_lesson`, not a full rewrite of the file.
4. **Do not compress lessons into slogans.** ACE's "brevity bias": a short summary
   drops the domain detail that made the lesson useful. Keep the `when` condition and
   the concrete action.
5. **A wrong lesson spreads.** Agents copy retrieved memory closely
   ("experience-following"), so a bad lesson repeats its error on every task it is
   retrieved for. Only add a lesson whose evidence is a scored outcome, and
   `remove_lesson` any lesson the candidate's traces show the agent followed into a
   failure.
6. **Budget the memory.** Set `memory.max_entries`; past it `validate()` fails. Merge
   duplicates (`validate()` flags repeated `do` text), and prefer `memory.mode:
   retrieved` with `memory.top_k` once the file outgrows what fits in the prompt.
7. **Check that the agent read it.** After a gate, open one trace where a lesson's
   `when` held. Lesson ignored ⇒ change where it is injected (`memory.inject_at`) or
   its form; lesson followed and still wrong ⇒ change its content.

Full memory design (write / retrieve / prune, the formats of workflow memory and
playbooks, and when retrieval beats injecting everything):
[`references/memory.md`](references/memory.md).

## Cost

Harness edits can buy score with compute. `validate()` reports `stats.cost_factor`
(model calls per task implied by the sampling and final-check settings), and with
`--baseline` it warns when that factor grows. Report the cost next to the reward gain
in `PROCESS.md`; a gain that doubles cost is a different result from a free one.

- Best-of-N pays only with a reliable selector. Coverage keeps rising with more
  samples, but majority voting and reward models plateau (Large Language Monkeys,
  2024). Use `selector: verifier` only when a real check exists (tests, a schema, a
  state comparison).
- Multi-agent research used about 15× the tokens of chat, and token use explained 80%
  of the performance variance (Anthropic, 2025). Sub-agents also lose shared context
  and make conflicting implicit decisions (Cognition, 2025). Default to one agent.
- Keep `context.stable_prefix: true`: a byte-stable prompt prefix keeps the KV cache,
  where cached input costs about one tenth of uncached input (Manus, 2025).

## Guardrails

- **Generalize, never hardcode.** No task id, value or answer in a lesson, a hook or a
  setting comment. Test for every edit: would it help on a task the optimizer has
  never seen?
- **One mechanism per cluster, verified on the trace.** Before you gate, run the hook
  or setting against the exact trace it targets and confirm it fires; then against
  1-2 passing tasks and confirm it does not change them.
- **Hooks are real code.** `apply()` refuses a hook that does not parse or has a
  function with only `pass`, `...` or a docstring.
- **Do not remove a guard to save cost** unless the traces show it never fires.
- **Write only inside the capability dir.** Code edits must target `hooks/*.py`;
  `memory.path` must be a relative path inside the dir.

## Handlers (scripts/abstract.py)

`materialize(dir) -> {file: text}` · `apply(dir, edits) -> {changed, refused,
warnings}` · `validate(dir, baseline=None) -> {ok, stats, problems, warnings}` ·
`is_empty(dir) -> bool` · `load_policy(dir)`, `load_config(dir)`, `load_lessons(dir)`.

Edit ops: `set` / `unset` (`path`, `value`), `add_lesson` / `update_lesson` /
`remove_lesson`, `code` (`file`, `text`). Policy kinds: `config`, `lesson`, `code`.

## How to run

```
python scripts/check.py
python scripts/run.py --path <capability_dir>                        # candidate + validity
python scripts/run.py --path <candidate_dir> --baseline <parent_dir>  # + cost growth
```

## References

Each is standalone.

- [`references/concepts.md`](references/concepts.md) — every lever in the table with
  its mechanism, when it hurts, and the measured results behind it, with sources.
  **Read once before your first candidate.**
- [`references/memory.md`](references/memory.md) — cross-run memory in depth: what to
  distill, lesson formats, retrieval, pruning, and the failure modes. **Read before
  the first `add_lesson`.**
- [`references/adapter-wiring.md`](references/adapter-wiring.md) — how an adapter
  reads `harness.json`, injects lessons, and imports hooks, plus a minimal example.
  **Read at intake, when wiring a new agent.**
