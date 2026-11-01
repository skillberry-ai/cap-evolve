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

These pages walk through optimizing a benchmark with the blackbox approach, step by step. The worked
example is τ²-bench airline on vanilla upstream tau2:
[`examples/tau2_sierra_airline/blackbox`](../../examples/tau2_sierra_airline/blackbox/).

Read them in order:

1. [Concepts](01-concepts.md): intervention vs capability, direct vs blackbox, and what a
   benchmark must provide.
2. [Architecture](02-architecture.md): the services, ports and headers, and one trial's
   session.
3. [Quickstart](03-quickstart.md): setup, smoke run, full run, stop.
4. [The candidate](04-the-candidate.md): what the optimizer edits and the delivery rules.
5. [Reading the results](05-results.md): dashboard, run directory, the blackbox checks.
6. [Troubleshooting](06-troubleshooting.md): symptom → cause → fix.

**Primary sources:**
- [`skills/interventions/llm-proxies/blackbox/SKILL.md`](../../skills/interventions/llm-proxies/blackbox/SKILL.md):
  the intervention;
- [`core/cap_evolve/intervention.py`](../../core/cap_evolve/intervention.py): the preflight;
- [`examples/tau2_sierra_airline/PROMPT.md`](../../examples/tau2_sierra_airline/PROMPT.md): the
  onboarding prompt that produced the example.
