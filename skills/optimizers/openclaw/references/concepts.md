# Concepts: the edit-proposer contract (openclaw)

## The universal edit-proposer contract

Every cap-evolve optimizer — claude-code, codex, gemini-cli, opencode, openclaw, generic,
mock — implements the **same** contract. The optimize loop, not the agent, owns the
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
3. **The loop invokes the optimizer's `scripts/run.py`** as
   `run.py --workdir <copy> --prompt <copy>/INSTRUCTIONS.md`. `run.py` shells out to the
   agent with **cwd = `<copy>`**, non-interactively, with writes auto-approved.
4. **The agent edits files in place and exits.** Exit code 0 = success; non-zero is a failed
   proposal — the loop tolerates it and keeps the parent for that iteration.
5. **The loop evaluates the mutated workdir**, gates it against the parent, and either
   accepts it as the new best or rejects it (recording the reason into memory).

The agent only ever sees a directory of files, a task, and its memory — which is what lets
*any* headless coding CLI serve as the optimizer.

## This CLI: OpenClaw (`openclaw`) — configurable wrapper

OpenClaw stores skills under `~/.openclaw/workspace/skills/<skill>/SKILL.md` and is driven by
`AGENTS.md` / `SOUL.md` / `TOOLS.md`. Unlike claude-code / codex / gemini / opencode it does
**not** expose a single, stable, documented headless "edit these files and exit" command —
the subcommand/flag surface varies by build and configuration. So this skill is a
configurable wrapper, not a hard-coded invocation.

- **Configure**: `export CAPEVOLVE_OPENCLAW_CMD='openclaw run --workspace {workdir} "{prompt_text}"'`
  (default best-guess). Placeholders: `{workdir}`, `{prompt}` (path to INSTRUCTIONS.md),
  `{prompt_text}` (its contents).
- **The command must**: run non-interactively (no TTY prompts), auto-approve its file writes
  (put whatever `--auto`/`--yolo`-style flag your build uses into the template), edit files
  under `{workdir}`, and exit 0 on success.
- **Verify against your build**: use `openclaw --help` / `openclaw run --help`. If you can't
  produce a reliable headless edit command, use the `generic` optimizer instead (identical
  contract).
- **Why a wrapper**: there is no authoritative, stable public reference for a one-shot
  headless edit invocation that matches this skill-store flavor of OpenClaw, so we keep the
  exact command in your hands rather than hard-coding a guess that breaks across builds.

## Sources
- cap-evolve `generic` optimizer (the same configurable-template contract, recommended
  fallback): `skills/optimizers/generic/SKILL.md`
- For comparison, the CLIs that *do* publish stable headless commands:
  Claude Code https://code.claude.com/docs/en/cli-reference ·
  Codex https://developers.openai.com/codex/cli/reference ·
  Gemini https://www.geminicli.com/docs/cli/cli-reference/ ·
  opencode https://opencode.ai/docs/cli/
