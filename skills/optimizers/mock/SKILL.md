---
name: mock
description: A deterministic, zero-cost edit proposer for testing and CI. Use as the optimizer when you want to exercise the full optimize loop (propose → evaluate → gate → finalize) with no model calls and a reproducible outcome — e.g. validating an adapter, a new algorithm skill, or the end-to-end wiring. Driven by a JSON edit script rather than an LLM.
component: optimizer
argument-hint: "--workdir DIR --prompt FILE"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: []
sources: []
---

# mock optimizer

The mock optimizer plays the role of the edit-proposer agent without calling any model.
Given a working directory (a copy of the parent candidate) it applies a scripted set of
edits to the files in place — exactly the contract a real optimizer follows — so the rest
of the pipeline can be tested deterministically.

## When to use
- Building/validating an adapter (`acapo check` is green; now prove the loop runs).
- Developing a new algorithm or capability skill (no API spend per iteration).
- CI: the end-to-end proof slice uses `mock` so it costs nothing and never flakes.

## How it works
It reads an edit script — `ACAPO_MOCK_SCRIPT` env var, or `mock_script.json` in the workdir
(or its parent) — of the form:
```json
{ "edits": [ { "file": "prompt.txt", "op": "ensure_contains", "text": "..." } ] }
```
Ops:
- `ensure_contains` — idempotent append: adds `text` only if not already present.
- `append` — always append `text` to `file`.
- `set` — overwrite `file` with `text`.

The loop still writes `INSTRUCTIONS.md` (plus `MEMORY.md` / `STATE.md`) into the workdir,
but — being a mock — this optimizer does **not** interpret them; the JSON script alone
decides the edits, which is what makes the outcome reproducible. With no script present it
makes no edits and exits 0 (candidate == parent for that iteration).

## How to run
```bash
python scripts/check.py                                   # smoke-test the edit engine
python scripts/run.py --workdir <copy> --prompt <INSTRUCTIONS.md>
ACAPO_MOCK_SCRIPT=/path/to/edits.json python scripts/run.py --workdir <copy> --prompt <f>
```

## References
- `references/concepts.md` — the universal edit-proposer contract + per-CLI notes + sources.
