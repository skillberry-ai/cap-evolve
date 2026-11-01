# Concepts

## Intervention vs capability

cap-evolve separates two things:

| | What it answers | Set in `capevolve.yaml` by |
|---|---|---|
| **Capability** | *What* gets edited: a system prompt, tools, an MCP tool surface, a skill package | `capabilities:` |
| **Intervention** | *How* the edited candidate reaches the model under test | `intervention:` (`direct`, the default, or `blackbox`) |

They are independent: the same capability can be delivered either way. In the worked example
both approaches optimize the same thing, the airline agent's tools (`capabilities: [tools]`). They
differ only in delivery.

## Direct vs blackbox

| | Direct | Blackbox |
|---|---|---|
| Delivery | the runner loads the candidate's tool code in its own process | the candidate becomes a skill in the Skillberry Store; the agent-proxy injects it into the agent's LLM calls |
| What the agent calls | the gateway model | the sentinel model `ibm/skillberry-local`, which routes to the proxy; the proxy calls the real model (`SPA_MODEL_NAME`) |
| Extra services | none | Skillberry Store (`:8000`), Skillberry Proxy-Agent (`:7000`), the benchmark's environment service (tau2: `:8004`) |
| Concurrency in the example | 125 | 5 |
| Agent cost / tokens | reported by tau2 | not reported: the proxy returns no token usage, so agent cost reads 0 |
| Spec | — | `intervention: blackbox`, `skill_name: my_skill` |

The user simulator, judges and verifiers **never** go through the proxy. They call the gateway
directly, so only the agent under test sees the candidate.

## What a benchmark must provide

Blackbox is not a switch on any benchmark. The runner must be **blackbox-aware**, and the
environment must be reachable over HTTP. For tau2, all of this is added from outside the
benchmark by
[`adapters/tau2_tailoring.py`](../../examples/tau2_sierra_airline/blackbox/adapters/tau2_tailoring.py);
the tau2 clone itself is never edited.

1. **Sentinel routing.** Only the agent's LLM calls go to the proxy, as model
   `ibm/skillberry-local` with `base_url` = the proxy.
2. **Context headers** on every agent call, so the store can route each tool call to the right
   trial: `skillberry-context-plugin`, `skillberry-context-env_id` and
   `skillberry-context-task_id`.
3. **An environment service.** The skill's tools run inside the store, so they reach the
   benchmark's state over HTTP. tau2 ships one, its `EnvironmentManager`.
4. **A session per trial.**
   - Each trial opens one remote environment (`/start_environment`).
   - It closes it in a `finally`, as does the proxy session (`/disconnect`), so an errored trial
     cleans up too.
5. **Both trajectories merged into the benchmark's own, in the right windows:**
   - the environment service's trajectory BEFORE evaluation, so the scorer replays the real
     database writes;
   - the proxy's trajectory AFTER, so the optimizer sees the skill's composite tool calls.
6. **Deploy in the adapter's `apply()`.**
   - Make the candidate the only skill in the store (`reset_store_to_skill`), then restart the
     proxy on it (`restart_spa`).
   - `apply()` never raises: a failed deploy marks the candidate's rollouts as errored, so it is
     excluded rather than scored 0.

A benchmark that lacks these cannot be optimized with the blackbox approach. Declaring
`intervention: blackbox` is not enough: see
[Troubleshooting](06-troubleshooting.md#services-already-running-from-an-earlier-run).
