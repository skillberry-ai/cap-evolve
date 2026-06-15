---
name: claude-code
description: Use Anthropic's Claude Code CLI headless as the edit proposer. Use when you want a strong general coding agent to propose capability edits. Runs `claude -p "<instructions>" --permission-mode acceptEdits` with cwd set to the candidate working directory, so Claude reads the instructions and edits the capability files in place. Documents the verified install, auth, commands, flags, and features that make it an effective optimizer.
component: optimizer
argument-hint: "--workdir DIR --prompt FILE [--model ID]"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: []
sources: []
---

# claude-code optimizer

Drives [Claude Code](https://code.claude.com/docs) — the `claude` CLI — in headless
("print") mode to propose edits. The loop hands it a throwaway copy of the candidate
plus an `INSTRUCTIONS.md`; Claude edits the files in that directory in place and exits.

## Install
```bash
npm install -g @anthropic-ai/claude-code     # Node 18+; also: brew install claude-code
claude --version                              # verify on PATH
```

## Authenticate
Claude Code uses, in order of convenience:
- **`ANTHROPIC_API_KEY`** — set it in the environment (or the repo `.env`) for fully
  unattended/CI runs. This is the headless-friendly path.
- **Interactive login** — run `claude` once and complete the Claude/Console OAuth flow;
  the token is cached under `~/.claude/`. Fine for local use, not for fresh CI.
- Bedrock/Vertex are supported via `CLAUDE_CODE_USE_BEDROCK=1` / `CLAUDE_CODE_USE_VERTEX=1`
  plus the usual cloud creds.

## Invocation
```bash
claude -p "<instructions>" --permission-mode acceptEdits [--model <id>]   # cwd = the candidate dir
```
Key flags (verified against the current CLI reference):
- `-p` / `--print` — run non-interactively and exit (no REPL). The prompt is the
  positional arg or comes from stdin.
- `--permission-mode acceptEdits` — auto-approve file edits without prompting. Accepted
  values are `default`, `acceptEdits`, `plan`, `auto`, `dontAsk`, `bypassPermissions`.
  `acceptEdits` is the right level here: it lets Claude write files but still gates other
  actions. The workdir is a throwaway candidate copy, so auto-accepting edits is safe.
  (`--dangerously-skip-permissions` ≡ `--permission-mode bypassPermissions` removes *all*
  gates — only reach for it if a sandboxed edit also needs to run shell/network freely.)
- `--model <id>` — pick the model. Accepts the latest-model aliases `opus`, `sonnet`,
  `haiku`, `fable`, or a full id like `claude-sonnet-4-6`. Also settable via
  `ACAPO_OPTIMIZER_MODEL` (the skill maps it to `--model`) or the `ANTHROPIC_MODEL` env var.
- `--output-format json` (or `stream-json`) — structured result if you want to parse the
  run programmatically instead of reading prose stdout.
- `--add-dir <path>` — grant read/edit access to extra directories (rarely needed since
  the candidate dir is already the cwd).
- `--allowedTools "Bash(git diff *)" Read …` — narrow what runs without prompting.
- `--append-system-prompt "<text>"` — inject standing guidance on top of the task.

## How it edits files
`run.py` reads `INSTRUCTIONS.md`, then runs `claude -p` with **cwd = `--workdir`**, so
every relative path Claude touches lands inside the candidate copy. Claude also reads
`CLAUDE.md` from the workdir if present, and the loop's `MEMORY.md` / `STATE.md`
scratchpads are right there for it to consult and update.

## Using it well
- The loop writes the reflection (diagnosis + rejected-memory + a pointer to the run dir)
  into `INSTRUCTIONS.md`; Claude reads it as the task. Richer diagnosis → better edits.
- Keep the candidate dir small and focused so edits stay on-target.
- Prefer multiple cheap iterations (let the gate filter) over one giant edit. Pick
  `sonnet` for fast/cheap iterations and `opus` when an edit needs deeper reasoning.
- Version-dependent: permission-mode values and `--output-format` are stable, but the CLI
  evolves quickly — `claude --help` is the source of truth for your installed version.

## Availability
`scripts/run.py` checks for the `claude` CLI on PATH and returns a clear error if it is
absent (use `generic` or `mock` instead). `scripts/check.py` passes without the CLI so CI
is not blocked.

## How to run
```bash
python scripts/check.py
python scripts/run.py --workdir <copy> --prompt <INSTRUCTIONS.md> --model <id>
```

## References
- `references/concepts.md` — the universal edit-proposer contract + per-CLI notes + sources.
