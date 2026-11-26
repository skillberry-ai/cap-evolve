# Cross-run memory — design in depth

- [The model in this framework](#the-model-in-this-framework)
- [What to distill](#what-to-distill)
- [Lesson formats](#lesson-formats)
- [Injecting and retrieving](#injecting-and-retrieving)
- [Pruning and updating](#pruning-and-updating)
- [Failure modes](#failure-modes)
- [A memory round, step by step](#a-memory-round-step-by-step)
- [Sources](#sources)

## The model in this framework

Published memory systems differ in WHO writes memory and WHEN:

| System | Written by | When | What is stored |
|---|---|---|---|
| Reflexion [reflexion] | the agent | after a failed attempt, before a retry of the SAME task | a verbal self-reflection |
| ExpeL [expel] | the agent | offline, over a set of training tasks | natural-language insights plus past experiences |
| Agent Workflow Memory [awm] | the agent | offline from training examples, or online from test queries | reusable workflows (routines) |
| Dynamic Cheatsheet [dc] | the model | after each query | strategies, code snippets, insights |
| ACE [ace] | generator → reflector → curator | after each task, as incremental updates | an evolving playbook of strategies |
| ReasoningBank [reasoningbank] | the agent | after each task, self-judged | strategies from successes and failures |

cap-evolve uses the **offline** form (ExpeL, offline AWM): the optimizer writes the
lessons between iterations from train/val traces, and the agent reads them, read-only,
during scored rollouts. The online forms learn from test queries; under a sealed test
that is leakage, and it makes each score depend on task order. `validate()` enforces
both rules: `memory.write_during_eval` must be false, and no lesson may cite `test`.

If the deployed agent should keep learning in production, that is a valid design, but
it is not what the gate can measure. Optimize the offline memory here, and ship the
online writer as a separate, separately tested feature.

## What to distill

Use the diagnose clusters, not single tasks.

- **A failure cluster** → a corrective lesson: the condition that precedes the error
  (`when`) and the action that avoids it (`do`).
- **A success pattern** → a keep-doing lesson. ReasoningBank distills from both, and
  reports that this beats memories built from raw trajectories or from successes
  only [reasoningbank].
- **A recurring routine** → a workflow: the ordered steps the agent re-derives on
  every task of a type. AWM reports +24.6% and +51.1% relative success on Mind2Web
  and WebArena, with fewer steps per solved task [awm].
- **A reusable computation** → a code snippet, or better, a hook or tool. Dynamic
  Cheatsheet took GPT-4o on Game of 24 from 10% to 99% after it stored and reused a
  Python solution [dc]. If the snippet is deterministic, a `tools` edit or a `hooks/`
  file makes it un-skippable.

Do not store raw transcripts. Dynamic Cheatsheet keeps "short, reusable pieces rather
than entire transcript" [dc], and a transcript carries task-specific values.

## Lesson formats

Required fields: `id`, `when`, `do`, `evidence`, `source_split` (`train` or `val`).
Optional fields the adapter may use: `tags` (for retrieval), `kind`
(`rule | workflow | snippet`), `steps` (a list, for a workflow).

```json
{"id": "refund-to-original", "kind": "rule",
 "when": "the user asks for a refund on a paid booking",
 "do": "refund to the original payment method; ask before using any other method",
 "evidence": "val: cluster refund_wrong_method, 5 of 7 failing traces",
 "source_split": "val", "tags": ["refund", "payment"]}
{"id": "change-flight-workflow", "kind": "workflow",
 "when": "the user asks to change a flight",
 "do": "follow the steps in order",
 "steps": ["get the reservation", "check the fare rules", "search flights",
           "state the price difference", "get explicit confirmation", "update"],
 "evidence": "train: 9 passing traces share this order; 4 failing ones skip step 2",
 "source_split": "train", "tags": ["change", "flight"]}
```

## Injecting and retrieving

- `memory.mode: all` — inject every lesson. Simple and order-free; right while the
  memory is small.
- `memory.mode: retrieved` with `memory.top_k` — inject only the lessons relevant to
  the task (by tags, embedding, or keyword; the adapter decides). Needed once the
  memory no longer fits the prompt budget. Retrieval adds a failure mode: a relevant
  lesson that is not retrieved has no effect, so check retrieval on the traces.
- `memory.inject_at` — `system` (stable, cache-friendly) or `first_user` (closer to
  the task text). Keep it in the stable prefix when you can: a changing prefix
  invalidates the KV cache [manus].

## Pruning and updating

- **Incremental edits only.** ACE's "context collapse": rewriting the whole context
  each round erodes detail. Its fix is structured, incremental updates [ace]. Use
  `add_lesson` / `update_lesson` / `remove_lesson`, not a `set` of the whole file.
- **Keep detail.** ACE's "brevity bias": compressing into short summaries drops the
  domain insight [ace]. Merge duplicates, but keep each distinct condition.
- **Budget.** `memory.max_entries` is a hard limit in `validate()`. `stats.memory_tokens`
  shows the prompt cost.
- **Remove on evidence.** Remove a lesson when a gate shows the agent followed it into
  a failure, or when the rule is now enforced in a tool or hook (the code is
  authoritative; the lesson only competes for attention).

## Failure modes

- **Experience-following and error propagation.** Agents closely copy retrieved
  memory; a wrong record makes the agent repeat its error, and if that run is written
  back, the error spreads. A reliable trajectory evaluator for what gets added is
  the main defence [experience-following]. Here the evaluator is the scorer: add a
  lesson only from scored outcomes.
- **Memory poisoning.** Text from tool outputs or users that reaches memory can carry
  injected instructions. Agents that write and retrieve more aggressively are easier
  to exploit [mpbench]. Never copy tool-output text into a lesson verbatim; write the
  rule in your own words.
- **Overfitting.** A lesson with a record id, a date or a gold value helps one task and
  misleads others. `validate()` warns on id-like literals.
- **Ignored memory.** The lesson is present and the agent does not apply it. Check one
  trace where `when` held before changing the content.

## A memory round, step by step

1. Diagnose train and val; list clusters with `score_lost`.
2. For each addressable cluster, write one lesson (or update an existing one).
3. `apply()` the lesson edits; `validate()` with `--baseline` the parent.
4. Gate on full val. Read one trace per new lesson: was it injected, was it followed?
5. Record in `PROCESS.md`: lesson id → cluster → tasks, and the gate numbers.

## Sources

- [reflexion] Shinn et al., arXiv:2303.11366, 2023.
- [expel] Zhao et al., arXiv:2308.10144, 2023.
- [awm] Wang et al., arXiv:2409.07429, 2024.
- [dc] Suzgun et al., arXiv:2504.07952, 2025.
- [ace] Zhang et al., arXiv:2510.04618, 2025.
- [reasoningbank] Ouyang et al., arXiv:2509.25140, 2025.
- [experience-following] "How Memory Management Impacts LLM Agents: An Empirical Study of Experience-Following Behavior", arXiv:2505.16067, 2025.
- [mpbench] "From Untrusted Input to Trusted Memory: A Systematic Study of Memory Poisoning Attacks in LLM Agents", arXiv:2606.04329, 2026.
- [manus] Y. Ji, "Context Engineering for AI Agents: Lessons from Building Manus", 2025.
