# The blackbox approach

In the **blackbox approach** the optimizer process never touches the benchmark.

Some clients, such as enterprises, cannot share their agent's code, sources or behaviour with an
external optimization process. For them the optimization runs indirectly, without inspecting or
directly modifying their agents.

An **approach** is how a candidate reaches the model under test:

- **Direct** (the default): the benchmark's runner loads the candidate's files in its own process.
- **Blackbox** (`intervention: blackbox`): the candidate is deployed to the
  [**Skillberry Store**](https://github.com/skillberry-ai/skillberry-store), and the
  [**Skillberry Proxy-Agent**](https://github.com/skillberry-ai/skillberry-agent) (SPA) injects it
  into the agent's LLM calls.

  The benchmark never sees a skill file, a mounted directory, or an edited prompt: the agent is
  left unchanged and receives the optimized response from Skillberry.

The optimized capabilities can be used in two ways:

1. **Through the Skillberry service** (a paid service): the client never changes its benchmark.
   The benchmark is optimized through the responses the Skillberry Proxy-Agent returns.
2. **By exporting the optimized capabilities** from the Skillberry Store and patching them back
   into the client's benchmark.

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
