# Optimizing using the blackbox approach

In the **blackbox approach** the optimizer process never touches the benchmark.

## Introduction

Some clients, such as enterprises, cannot share their agent's code, sources or behaviour with an
external optimization process. For them the optimization runs indirectly, without inspecting or
directly modifying their agents.

The approach introduces two additional services:

- [**Skillberry Store**](https://github.com/skillberry-ai/skillberry-store): a smart repository of
  tools and skills for agentic workflows.
- [**Skillberry Proxy-Agent**](https://github.com/skillberry-ai/skillberry-agent): a proxy that sits
  between the client agent and the LLM provider, uses the optimized skills and tools, and returns an
  optimized response to the agent.

In the blackbox approach, cap-evolve deploys the capabilities to optimize (system prompts, tools,
skills) into the Skillberry Store, and the Skillberry Proxy-Agent reads them and injects them into the
agent's LLM calls. The benchmark agent is left unchanged; it receives the optimized response from
Skillberry.

The optimized capabilities can be used in two ways:

1. **Through the Skillberry service** (a paid service): the client never changes its benchmark.
   The benchmark is optimized through the responses the Skillberry Proxy-Agent returns.
2. **By exporting the optimized capabilities** from the Skillberry Store and patching them back
   into the client's benchmark.

## How it works

```
                      sentinel + headers                     upstream call
 ┌──────────────────┐                  ┌──────────────────┐                  ┌──────────────────┐
 │ agent under test │─────────────────►│Proxy-Agent :7000 │─────────────────►│  the real model  │
 │                  │◄─ ─ ─ ─ ─ ─ ─ ─ ─│ serves my_skill  │◄─ ─ ─ ─ ─ ─ ─ ─ ─│ routes requests  │
 └──────────────────┘                  └──────────────────┘                  │    to the LLM    │
                      optimized response     │      ▲         model reply    └──────────────────┘
                                   tool call │      ┆ tool result
                                             ▼      ┆
                                       ┌──────────────────┐  env_<tool>(…)   ┌──────────────────┐
                                       │   Store :8000    │─────────────────►│remote env service│
                                       │the skill's tools │                  │      :8004       │
                                       │     run here     │◄─ ─ ─ ─ ─ ─ ─ ─ ─│ hosts benchmark  │
                                       └──────────────────┘   env result     │  tool execution  │
                                                                             └──────────────────┘

                      the gateway directly
 ┌──────────────────┐
 │  user simulator  │───────────────────────────────────────────────────────────────────────────►
 └──────────────────┘◄─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
                      reply

 ───►  request        ◄─ ─ ─  response
```

The diagram above shows the flow between the benchmark agent and the real model it reaches. The agent
receives an optimized response without being modified.

## Building blocks

### The intervention skill

The blackbox approach is delivered by an intervention skill that owns the whole Skillberry stack:
it provisions the Store and the Proxy-Agent, starts and stops them, and deploys each candidate as
the one skill the Proxy-Agent serves. A run selects it with `intervention: blackbox` and
`skill_name:` in `capevolve.yaml`.

Reference: [`skills/interventions/llm-proxies/blackbox/SKILL.md`](../skills/interventions/llm-proxies/blackbox/SKILL.md)

### The preflight

Before any budget is spent, cap-evolve validates the declared intervention and checks that the
Store and the Proxy-Agent are actually up. A misspelled intervention or a stack that is not running
stops the run with a message naming the problem, instead of a run that errors every rollout and
measures nothing.

Reference: [`core/cap_evolve/intervention.py`](../core/cap_evolve/intervention.py)

## An onboarding example (τ²-bench)

A coding agent onboards a benchmark for the blackbox approach by following the prompt below and
answering `blackbox` when it asks which approach to use. It installs the benchmark unmodified, seeds
the capability from the benchmark's own source, and adds the tailoring the approach needs from
outside the benchmark. It then passes the `cap-evolve check` gate and runs the optimization loop: it
proposes edits, keeps only those that clear the significance gate, scores the sealed test once, and
writes a report.

Reference: [`benchmarks/tau2/examples/sierra_airline/PROMPT.md`](../benchmarks/tau2/examples/sierra_airline/PROMPT.md)
