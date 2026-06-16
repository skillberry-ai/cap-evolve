# Concepts: the edit-proposer contract (generic)

## The universal edit-proposer contract

Every cap-evolve optimizer — claude-code, codex, gemini-cli, opencode, openclaw, generic,
mock — implements the **same** contract. The `generic` skill is the canonical, minimal
expression of it: a templated shell command. The optimize loop, not the agent, owns the
orchestration:

1. **The loop prepares a workdir.** It copies the current best candidate into a fresh,
   throwaway directory (`<run>/work/<candidate-id>/`). Because it is a copy, the agent may
   edit freely — auto-approving writes is safe.
2. **The loop writes context files into that workdir:**
   - `INSTRUCTIONS.md` — the task: why the current candidate underperforms + what to try
     (and a pointer to the run-output dir).
   - `MEMORY.md` — rejected approaches + accepted history, so the agent doesn't repeat dead ends.
   - `STATE.md` — a scratchpad the agent updates with its running diagnosis/plan; it persists
     across accepted iterations.
3. **The loop invokes `scripts/run.py`** as
   `run.py --workdir <copy> --prompt <copy>/INSTRUCTIONS.md`. `run.py` substitutes the
   `{workdir}` / `{prompt}` placeholders in `CAPEVOLVE_OPTIMIZER_CMD` and runs the resulting
   command with **cwd = `<copy>`**.
4. **The agent edits files in place and exits.** Exit code 0 = success; non-zero is a failed
   proposal — the loop tolerates it and keeps the parent for that iteration.
5. **The loop evaluates the mutated workdir**, gates it against the parent, and either
   accepts it as the new best or rejects it (recording the reason into memory).

The agent only ever sees a directory of files, a task, and its memory — which is what lets
*any* headless coding CLI serve as the optimizer.

## This skill: generic templated command

- **Configure**: `export CAPEVOLVE_OPTIMIZER_CMD='my-agent edit --dir {workdir} --instructions {prompt}'`
  (or pass `--cmd` per run). Placeholders: `{workdir}` (also the cwd), `{prompt}` (path to
  `INSTRUCTIONS.md`).
- **Requirements for the wrapped agent**:
  - Non-interactive / headless (no TTY prompts) — runs to completion unattended.
  - Auto-approves its own file writes (include the agent's `--yes`/`--auto`/`--yolo`/
    `--dangerously-skip-permissions`-style flag in the template).
  - Edits files under `{workdir}` (relative paths resolve there because cwd = workdir).
  - Exit code 0 on success.
- **Inline prompts**: if your agent takes the task inline, wrap it, e.g.
  `sh -c 'my-agent "$(cat {prompt})"'`.
- **Prefer a dedicated skill** when one exists (claude-code, codex, gemini-cli, opencode):
  those encode the verified command, auth, and flags for you.

## Sources
- Dedicated optimizer skills that encode the verified per-CLI commands:
  Claude Code https://code.claude.com/docs/en/cli-reference ·
  Codex https://developers.openai.com/codex/cli/reference ·
  Gemini https://www.geminicli.com/docs/cli/cli-reference/ ·
  opencode https://opencode.ai/docs/cli/
