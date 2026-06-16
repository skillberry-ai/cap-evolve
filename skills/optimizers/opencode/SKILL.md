---
name: opencode
description: Use opencode headless as the edit proposer. Use when you want opencode to propose capability edits. Runs `opencode run --dangerously-skip-permissions "<instructions>"` with cwd set to the candidate working directory so opencode edits files in place. opencode reads Anthropic-compatible SKILL.md and .claude/skills natively, making it a natural cap-evolve host. Documents the verified install, auth, and useful flags.
component: optimizer
argument-hint: "--workdir DIR --prompt FILE [--model PROVIDER/ID]"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: []
sources: []
---

# opencode optimizer

Drives [opencode](https://opencode.ai/docs) — the `opencode` command — in headless `run`
mode. The loop hands it a throwaway copy of the candidate plus an `INSTRUCTIONS.md`;
opencode edits the files in that directory in place and exits.

## Install
```bash
curl -fsSL https://opencode.ai/install | bash      # or: npm install -g opencode-ai
# or: brew install anomalyco/tap/opencode
opencode --version                                  # verify on PATH
```

## Authenticate
opencode is provider-agnostic (models via models.dev). Configure credentials with:
```bash
opencode auth login     # pick a provider (OpenCode Zen, Anthropic, OpenAI, …) and paste the key
opencode auth list      # show configured providers
```
For unattended/CI runs, set the relevant provider key in the environment (e.g.
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) so no interactive step is needed.

## Invocation
```bash
opencode run --dangerously-skip-permissions "<instructions>"     # cwd = the candidate dir
```
Key flags (verified against the opencode CLI reference):
- `opencode run [message..]` — headless one-shot (bare `opencode` opens the TUI). The
  prompt is the positional arg; stdin is also accepted.
- `--dangerously-skip-permissions` — auto-approve permissions not explicitly denied, so
  opencode can write files unattended. The workdir is a throwaway candidate copy, so this
  is safe. (Finer control: set `OPENCODE_PERMISSION` to an inlined JSON permissions config
  instead of blanket-approving.)
- `-m` / `--model <provider/model>` — pin the model in `provider/model` form (e.g.
  `anthropic/claude-sonnet-4-6`); also via `CAPEVOLVE_OPTIMIZER_MODEL`.
- `--agent <name>` — select a configured agent persona.
- `--format json` — raw JSON event stream instead of formatted text.
- `--continue` / `-c`, `--session` / `-s` — continue a prior session (not used by the
  loop, which runs each iteration fresh in a new workdir).

## How it edits files
`run.py` reads `INSTRUCTIONS.md`, then runs `opencode run` with **cwd = `--workdir`**, so
opencode edits the candidate copy in place. The loop's `MEMORY.md` / `STATE.md` are in the
same dir for it to read and update.

## Why opencode is a first-class cap-evolve host
opencode reads Anthropic-compatible `SKILL.md` and even `.claude/skills/` natively, so the
cap-evolve skill library installs with zero translation — the same skills you ship for
Claude Code work here unchanged.

## Using it well
- The per-iteration task arrives in `INSTRUCTIONS.md` (the loop's diagnosis + rejected
  memory). Richer diagnosis → better edits.
- For repeated runs, `opencode serve` + `opencode run --attach http://localhost:PORT`
  avoids MCP cold-boot overhead.
- Version-dependent: confirm the model id format and flags with `opencode run --help`.

## Availability
`scripts/run.py` checks for `opencode` on PATH; `scripts/check.py` passes without it.

## How to run
```bash
python scripts/check.py
python scripts/run.py --workdir <copy> --prompt <INSTRUCTIONS.md> --model <provider/id>
```

## References
- `references/concepts.md` — the universal edit-proposer contract + per-CLI notes + sources.
