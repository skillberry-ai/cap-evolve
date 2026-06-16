# Concepts: the edit-proposer contract (mock)

## The universal edit-proposer contract

Every cap-evolve optimizer — claude-code, codex, gemini-cli, opencode, openclaw, generic,
mock — implements the **same** contract. The optimize loop, not the agent, owns the
orchestration:

1. **The loop prepares a workdir.** It copies the current best candidate into a fresh,
   throwaway directory (`<run>/work/<candidate-id>/`). Because it is a copy, edits are safe.
2. **The loop writes context files into that workdir:**
   - `INSTRUCTIONS.md` — the task (diagnosis + what to try + a pointer to the run-output dir).
   - `MEMORY.md` — rejected approaches + accepted history.
   - `STATE.md` — a persistent scratchpad for the agent's running diagnosis/plan.
3. **The loop invokes the optimizer's `scripts/run.py`** as
   `run.py --workdir <copy> --prompt <copy>/INSTRUCTIONS.md`. A real optimizer shells out to
   an agent CLI (cwd = workdir, headless, writes auto-approved); the mock instead applies a
   scripted set of edits.
4. **The proposer edits files in place and exits.** Exit code 0 = success; non-zero is a
   failed proposal that the loop tolerates (keeping the parent for that iteration).
5. **The loop evaluates the mutated workdir**, gates it against the parent, and accepts or
   rejects it.

The proposer only ever sees a directory of files, a task, and its memory — which is what
lets *any* headless coding CLI (or this deterministic stand-in) play the role.

## This proposer: mock (deterministic, zero-API)

The mock optimizer **fulfils the contract without a model**, so the full loop (propose →
evaluate → gate → finalize) can be exercised in tests and CI with a reproducible outcome.

- **Driven by a JSON edit script**, not an LLM: `CAPEVOLVE_MOCK_SCRIPT` env var, or
  `mock_script.json` in the workdir (or its parent).
- **Script shape**:
  ```json
  { "edits": [ { "file": "prompt.txt", "op": "ensure_contains", "text": "..." } ] }
  ```
- **Ops**: `ensure_contains` (idempotent append — adds `text` only if absent), `append`
  (always append), `set` (overwrite).
- **Ignores INSTRUCTIONS.md by design**: the loop still writes `INSTRUCTIONS.md` /
  `MEMORY.md` / `STATE.md`, but the mock does not interpret them — the script alone decides
  the edits, which is what makes the result deterministic. No script → no edits, exit 0
  (candidate == parent for that iteration).
- **Why it matters**: it's the cheapest, flake-free way to validate an adapter, a new
  algorithm/capability skill, or the end-to-end wiring before spending on a real agent. Real
  optimizer skills (claude-code, codex, …) swap this for an agent that reads INSTRUCTIONS.md
  and edits the files.

## Sources
- cap-evolve optimizer wiring (the `OptimizerFn (workdir, instructions) -> None` model and
  how `run.py` plugs in): `core/cap_evolve/harness.py`
- Real optimizer skills that implement the same contract with live agents:
  `skills/optimizers/{claude-code,codex,gemini-cli,opencode}/SKILL.md`
