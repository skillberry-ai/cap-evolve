# tau2 airline — agent-harness seed overlay

Copied over `seed_capability/` by the `tau2_harness` CI leg (`ci/benchmarks/lib/run_suite.sh`),
which then optimizes `[system-prompt, tools, agent-harness]` instead of the `tau2` leg's
`[system-prompt, tools]`. Everything else in the two legs is the same, so the pair measures
what the agent-harness capability adds.

| File | What it holds |
|---|---|
| `harness.json` | The settings the tau2 adapter wires, at the values plain tau2 uses: 100 steps, no think tool, no repeat nudge, memory on with no lessons. The seed agent therefore behaves like the plain `llm_agent`. |
| `harness_policy.json` | Allowed edit kinds (`config`, `lesson`; hooks are not wired in tau2) and the wired settings. |
| `memory/lessons.jsonl` | Empty. The optimizer adds lessons from train/val traces; the agent reads them, read-only, at the start of each conversation. |
| `OPTIMIZER_NOTE.md` | Not part of the candidate. Appended to the optimizer instructions: it names the wired settings and the lesson rules. |

How the adapter applies each setting: `benchmarks/tau2/template/adapter.py`, section
"agent-harness capability".
