# Concepts: the edit-proposer contract (claude-code)

## The universal edit-proposer contract

Every cap-evolve optimizer — claude-code, codex, gemini-cli, opencode, openclaw, generic,
mock — implements the **same** contract. The optimize loop, not the agent, owns the
orchestration:

1. **The loop prepares a workdir.** It copies the current best candidate into a fresh,
   throwaway directory (`<run>/work/<candidate-id>/`). Because it is a copy, the agent may
   edit freely — accepting/bypassing edit permissions is safe.
2. **The loop writes context files into that workdir:**
   - `INSTRUCTIONS.md` — the task: the diagnosis of why the current candidate underperforms,
     plus what to try (and a pointer to the run-output dir).
   - `MEMORY.md` — rejected approaches + accepted history, so the agent doesn't repeat dead ends.
   - `STATE.md` — a scratchpad the agent updates with its running diagnosis/plan; it persists
     across accepted iterations.
3. **The loop invokes the optimizer's `scripts/run.py`** as
   `run.py --workdir <copy> --prompt <copy>/INSTRUCTIONS.md`. `run.py` reads the prompt and
   shells out to the agent CLI with **cwd = `<copy>`**, in a non-interactive/headless mode
   that auto-approves file writes.
4. **The agent edits files in place and exits.** It mutates the capability files inside the
   workdir (relative paths resolve there) and returns. Exit code 0 = success; non-zero is a
   failed proposal — the loop tolerates it and keeps the parent for that iteration.
5. **The loop evaluates the mutated workdir** (runs the candidate on the val split), gates
   it against the parent, and either accepts it as the new best or rejects it (recording the
   reason into memory).

The agent never sees the eval harness, the gate, or the version store — it only sees a
directory of files, a task, and its memory. That is what lets *any* headless coding CLI
serve as the optimizer: the loop adapts to the contract, not the other way around.

### What a good `run.py` invocation guarantees
- **Headless**: no REPL, no TTY prompts — runs to completion unattended.
- **Write-enabled**: edits are auto-approved (the workdir is disposable).
- **cwd = workdir**: so the agent's file edits land on the candidate copy.
- **Model selectable**: via `--model` / `CAPEVOLVE_OPTIMIZER_MODEL`.
- **Clear absence handling**: if the CLI isn't on PATH, `run.py` errors with guidance
  (use `generic` or `mock`); `check.py` still passes so CI isn't blocked.

## This CLI: Claude Code (`claude`)

- **Headless command**: `claude -p "<instructions>" --permission-mode acceptEdits [--model <id>]`.
- **`-p` / `--print`** runs non-interactively and exits.
- **`--permission-mode acceptEdits`** auto-approves edits while still gating other actions
  (values: `default`, `acceptEdits`, `plan`, `auto`, `dontAsk`, `bypassPermissions`;
  `--dangerously-skip-permissions` ≡ `bypassPermissions`).
- **Model**: `--model` accepts aliases `opus`/`sonnet`/`haiku`/`fable` or a full id; also the
  `ANTHROPIC_MODEL` env var.
- **Auth**: `ANTHROPIC_API_KEY` (headless/CI) or interactive login cached under `~/.claude/`;
  Bedrock/Vertex via `CLAUDE_CODE_USE_BEDROCK` / `CLAUDE_CODE_USE_VERTEX`.
- **Context file**: reads `CLAUDE.md` from the workdir.
- **Structured output**: `--output-format json|stream-json`.
- **Version note**: the CLI evolves fast; treat `claude --help` as the source of truth for
  the exact flags in your installed build.

## Sources
- Claude Code CLI reference (flags: `-p`, `--permission-mode`, `--model`, `--output-format`,
  `--add-dir`, `--allowedTools`, `--append-system-prompt`, `--dangerously-skip-permissions`):
  https://code.claude.com/docs/en/cli-reference
- Claude Code overview / install / headless usage: https://code.claude.com/docs
- Permission modes: https://code.claude.com/docs/en/permission-modes
