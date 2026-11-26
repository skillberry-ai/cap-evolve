# Concepts — optimizing an agent harness

- [What the harness is](#what-the-harness-is)
- [Loop and stopping rules](#loop-and-stopping-rules)
- [Context management](#context-management)
- [Tool-error handling](#tool-error-handling)
- [Sampling and verification](#sampling-and-verification)
- [Sub-agents](#sub-agents)
- [Cross-run memory (short form)](#cross-run-memory-short-form)
- [What automated harness search found](#what-automated-harness-search-found)
- [Sources](#sources)

Each section gives the mechanism, the trace symptom it fixes, when it hurts, and the
measured result from the source. A number is quoted only where the source reports it.

## What the harness is

LangChain defines the harness as "every piece of code, configuration, and execution
logic that isn't the model itself": prompts, tools, the sandbox, orchestration
(sub-agents, routing), and hooks or middleware for deterministic steps such as
compaction and lint checks [langchain-anatomy]. OpenAI's post that introduced the
term "harness engineering" (2026) describes building software with Codex agents
starting from an empty repository [openai-harness]. In cap-evolve the prompt and tools are separate
capabilities, so `agent-harness` covers the remaining layer: loop, context, memory,
error handling, sampling, sub-agents.

The layer is worth optimizing on its own. With the model fixed at gpt-5.2-codex,
LangChain raised deepagents-cli from 52.8% to 66.5% on Terminal Bench 2.0 by changing
prompts, tools and middleware [langchain-harness]. In the SWE-agent ablations, single
interface choices moved SWE-bench Lite resolve rate by 2-8 points [swe-agent].

## Loop and stopping rules

**Final check before exit** (`loop.final_check`). Symptom: the agent re-reads its own
work, judges it correct, and stops. LangChain's `PreCompletionChecklistMiddleware`
intercepts the exit and asks for a verification pass against the task spec; it was
one of the changes in the 52.8% → 66.5% result, with no separate number reported
[langchain-harness]. `run_tests` is the strongest form when the task has tests;
`self_verify` and `checklist` cost one extra model pass.

**Repeat detection** (`loop.repeat_limit`, `loop.on_repeat`). Symptom: the same call,
or edits to the same file, many times in a row ("doom loops", some over 10 repeats).
LangChain's `LoopDetectionMiddleware` counts edits per file and injects a nudge after
N; the authors note the model may continue if it believes it is right
[langchain-harness]. Start with `nudge`; use `stop` only when repeats never recover in
the traces.

**Think step** (`loop.think_tool`). A no-op tool where the model writes reasoning
between tool results. On τ-bench airline (Claude 3.7 Sonnet) pass^1 went from 0.332
(baseline) to 0.404 with the tool alone and 0.584 with the tool plus an optimized
prompt; on retail from 0.783 to 0.812 [anthropic-think]. It does not help single or
parallel tool calls or simple instruction following. Since December 2025 Anthropic
recommends extended thinking instead in most cases, so on a reasoning model test this
lever against the model's own thinking setting.

**Plan / todo tool and recitation** (`loop.plan_tool`, `context.recitation`). Symptom:
goal drift on long tasks. Manus tasks average about 50 tool calls; the agent rewrites
a `todo.md`, which puts the goals at the end of the context, where attention is
strongest [manus].

**Step budget** (`loop.max_steps`). Raise it when traces end at the limit while making
progress; lower it when failing traces loop until the limit (it saves cost, not
score). Combine with a time-budget warning that tells the agent to switch to
verification, as LangChain did [langchain-harness].

**No-action nudge** (`loop.no_action_nudge`). Symptom: the agent narrates or confirms
the change and ends with no mutating call. A harness-level re-prompt applies to every
task; if the agent owns the tools, a composite write tool (the `tools` capability) is
the stronger fix.

## Context management

**Context rot.** Recall degrades as the window fills; Anthropic treats context as an
"attention budget" [anthropic-context]. Three techniques, lightest first:

1. **Tool-result clearing / observation masking** (`context.compaction:
   observation_masking`, `context.keep_last_turns`). Replace old tool outputs with a
   placeholder; keep reasoning and actions. On SWE-bench Verified with SWE-agent,
   masking halved cost against the raw agent and matched or slightly beat LLM
   summarization; a hybrid cut cost a further 7% against masking and 11% against
   summarization [complexity-trap]. SWE-agent's own default (keep the last 5
   observations, collapse older ones) scored 18.0% on SWE-bench Lite against 15.0%
   with full history [swe-agent]. Anthropic calls tool-result clearing "one of the
   safest lightest touch forms of compaction" [anthropic-context].
2. **Summarization** (`summarize`, `context.compact_at_fraction`). Near the limit,
   summarize and restart from the summary. Claude Code keeps decisions, open bugs and
   implementation details, plus the five most recently used files. Tune the summary
   prompt for recall first, then precision; aggressive compaction loses details that
   matter later [anthropic-context].
3. **Restorable offload** (`context.tool_output_max_chars` plus a file path). Write
   a long output to a file and keep the path in context. Manus keeps the URL or path
   so a dropped observation can be reloaded [manus].

**Shape the observation, not only its length.** SWE-agent ablations: a 100-line file
viewer scored 18.0%, a 30-line one 14.3%, the full file 12.7%; summarized search
scored 18.0% and iterative search 12.0% [swe-agent].

**Keep errors in context** (`context.keep_errors`). Hiding a failed action removes the
evidence the model uses to avoid repeating it [manus].

**Keep the prefix stable** (`context.stable_prefix`). One changed token invalidates the
KV cache from that point; a timestamp at the top of the prompt is the usual cause.
Manus reports about a 100:1 input-to-output ratio and a 10× price gap between cached
and uncached input [manus]. Do not add or remove tools mid-task for the same reason;
mask them instead [manus].

**Vary repeated serialization.** Uniform action-observation pairs make the agent copy
its own pattern (Manus's 20-resume example) [manus]. A small variation in template
breaks the rut.

## Tool-error handling

**Validate before the call** (`tool_errors.validate_args`). Reject malformed arguments
against the schema and return the error, so the model corrects the next call.
SWE-agent's lint-on-edit guardrail: 18.0% with it, 15.0% without [swe-agent].

**Feed the error back** (`tool_errors.feed_error_back`). Return the full message, not
a bare code. A tool-description-rewriting agent cut later task time by 40% in
Anthropic's research system [anthropic-multi]; if the error *text* is the problem,
that is a `tools` edit.

**Bounded retry** (`tool_errors.max_retries`, `tool_errors.retry_on`). Retry only
named transient classes (timeout, rate limit, connection). Retrying a deterministic
error repeats it and costs a turn each time.

## Sampling and verification

**Best-of-N** (`sampling.n_candidates`, `sampling.selector`). On SWE-bench Lite,
coverage rose from 15.9% at 1 sample to 56% at 250. Without an automatic verifier,
majority voting and reward models plateaued after several hundred samples, so most of
that coverage was not turned into solved tasks [monkeys]. Use `selector: verifier`
only when a real check exists (tests, schema, state comparison).

**Temperature** (`sampling.temperature`). Lower it when the val noise floor is high and
the failures are inconsistent; raise it only together with N > 1.

**Reasoning budget per phase** (`custom.*` if your agent supports it). xhigh for
planning and verification with high for implementation scored 66.5%, against 63.6% at
high everywhere and 53.9% at xhigh everywhere (timeouts) [langchain-harness].

## Sub-agents

Anthropic's multi-agent research system (Opus 4 lead, Sonnet 4 workers) beat single
Opus 4 by 90.2% on an internal research eval. It used about 15× the tokens of chat,
and token use alone explained 80% of the variance on BrowseComp. It fits
high-value, parallel tasks larger than one context window; it fits most coding poorly
[anthropic-multi]. Cognition argues the opposite default: parallel sub-agents without
full shared traces make conflicting implicit decisions; prefer one linear agent, plus
a history-compression model for very long tasks [cognition]. Rule: enable
`subagents` only for independent read-only sub-questions that return a short summary
(Anthropic's workers return 1,000-2,000 tokens [anthropic-context]).

## Cross-run memory (short form)

The optimizer distills lessons from train/val traces between iterations; the agent
reads them, read-only, at the start of each task. Measured gains: Reflexion 91%
pass@1 on HumanEval against GPT-4's 80% [reflexion]; AWM +24.6% / +51.1% relative on
Mind2Web / WebArena [awm]; Dynamic Cheatsheet took GPT-4o on Game of 24 from 10% to
99% [dc]; ACE +10.6% on agent benchmarks [ace]. Full design: `memory.md` in this
folder.

## What automated harness search found

Searches that let a model rewrite the agent's own code are evidence of which harness
edits pay. The Darwin Gödel Machine raised SWE-bench from 20.0% to 50.0% and Polyglot
from 14.2% to 30.7%; the discovered changes included better code-editing tools,
long-context window management, and peer-review mechanisms [dgm]. ADAS's Meta Agent
Search writes agents as code from an archive of earlier designs, and the discovered
agents transferred across domains and models [adas]. The cap-evolve loop is the same
idea with a sealed test and a paired gate.

## Sources

Keys match `docs/sources.bib`.

- [ace] Zhang et al., "Agentic Context Engineering", arXiv:2510.04618, 2025.
- [reasoningbank] Ouyang et al., "ReasoningBank", arXiv:2509.25140, 2025.
- [awm] Wang, Mao, Fried, Neubig, "Agent Workflow Memory", arXiv:2409.07429, 2024.
- [reflexion] Shinn et al., "Reflexion", arXiv:2303.11366, 2023.
- [expel] Zhao et al., "ExpeL: LLM Agents Are Experiential Learners", arXiv:2308.10144, 2023.
- [dc] Suzgun et al., "Dynamic Cheatsheet", arXiv:2504.07952, 2025.
- [experience-following] "How Memory Management Impacts LLM Agents", arXiv:2505.16067, 2025.
- [complexity-trap] Lindenbauer et al., "The Complexity Trap", arXiv:2508.21433, 2025.
- [swe-agent] Yang et al., "SWE-agent: Agent-Computer Interfaces…", arXiv:2405.15793, 2024 (Table 3).
- [anthropic-context] Anthropic, "Effective context engineering for AI agents", 2025. https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- [anthropic-think] Anthropic, "The 'think' tool", 2025. https://www.anthropic.com/engineering/claude-think-tool
- [anthropic-multi] Anthropic, "How we built our multi-agent research system", 2025. https://www.anthropic.com/engineering/multi-agent-research-system
- [cognition] Cognition, "Don't Build Multi-Agents", 2025. https://cognition.com/blog/dont-build-multi-agents
- [manus] Y. Ji, "Context Engineering for AI Agents: Lessons from Building Manus", 2025. https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus
- [langchain-harness] LangChain, "Improving Deep Agents with harness engineering", 2026. https://www.langchain.com/blog/improving-deep-agents-with-harness-engineering
- [langchain-anatomy] LangChain, "The Anatomy of an Agent Harness", 2026. https://www.langchain.com/blog/the-anatomy-of-an-agent-harness
- [openai-harness] OpenAI, "Harness engineering: leveraging Codex in an agent-first world", 2026. https://openai.com/index/harness-engineering
- [monkeys] Brown et al., "Large Language Monkeys", arXiv:2407.21787, 2024.
- [dgm] Zhang, Hu, Lu, Lange, Clune, "Darwin Gödel Machine", arXiv:2505.22954, 2025.
- [adas] Hu, Lu, Clune, "Automated Design of Agentic Systems", arXiv:2408.08435, 2024.
