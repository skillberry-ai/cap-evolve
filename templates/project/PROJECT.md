# Acapo project — <target name>

Filled by the `intake` skill. Records the decisions behind this run so anyone
(human or agent) can understand and reproduce it.

## What we're optimizing
- Capability: <skill-package | tools | mcp-tool | system-prompt | ...>
- Artifact: `<path>`
- Allowed edits: <...>

## How we run the target (the RUNNER)
- Agent under test: <...>
- How `run_target` invokes it: <...>

## How we score
- Metric: <...> (reward in [0,1])
- Feedback signal: <what the scorer reports back as the learning signal>

## Data
- Source: `<path or "adapter">`
- Split: train/val/test (seed <n>) — test is sealed, scored once at finalize.

## Optimizer + algorithm
- Optimizer (proposer): <claude-code | codex | gemini-cli | ... | mock>
- Algorithm: <all-at-once | cyclic | gepa-reflective | ...>
- Budget: <iterations / metric-calls / usd / stall>

## Inputs status
- NEEDED inputs resolved: <list>
- RECOMMENDED inputs skipped: <list + why>
