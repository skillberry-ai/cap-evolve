# tau2_harness — the agent-harness A/B arm of the tau2 leg

`tau2_harness` is the plain `tau2` leg (airline, `benchmarks/tau2/template/adapter.py`) with
one factor changed: the **agent-harness** capability is added to what the optimizer may edit.

| | `tau2` (control) | `tau2_harness` (treatment) |
|---|---|---|
| capabilities | `[system-prompt, tools]` | `[system-prompt, tools, agent-harness]` |
| seed | `benchmarks/tau2/examples/airline/seed_capability` | the same, plus `harness_seed/{harness.json, harness_policy.json, memory/}` |
| seed agent | tau2 `llm_agent` | the adapter's harness agent; with the seed settings it sends the same prompt and tools as `llm_agent` |
| optimizer instructions | the default template | the default template plus `harness_seed/OPTIMIZER_NOTE.md` |
| tasks, models, trials, iterations, gate | tier defaults | identical (the `tasks.json` files here are copies of `../tau2/<tier>/`; a test keeps them equal) |

## How to run the pair

Dispatch both legs on the SAME commit and the same inputs, or add both labels to one PR:
`benchmark-smoke-tau2` and `benchmark-smoke-tau2_harness`. Compare:

- base→opt reward of each leg (the baselines should agree within noise: the seed agents are the same);
- the treatment leg's accepted candidates: did any accepted edit touch `harness.json` or
  `memory/lessons.jsonl`? A gain with no harness edit says the extra surface was not used;
- the `tau2-bench @ <commit>` line in each leg's setup log: the two legs are comparable only
  if they ran the same tau2 checkout.

The tau2 smoke tier is a no-holdout fit (train = val = test = the 10 tier tasks). A difference
between the two legs on smoke is evidence about fit, not about generalization; repeat it, or
use `full`, before reading it as a result.
