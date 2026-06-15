---
name: openclaw
description: Use OpenClaw as the edit proposer. Use when your optimizer is OpenClaw. Because OpenClaw's headless edit invocation is not standardized, this skill is a configurable wrapper — set ACAPO_OPENCLAW_CMD to OpenClaw's non-interactive edit command (with {workdir}/{prompt}/{prompt_text} placeholders); it defaults to a best-guess `openclaw run` form you should verify against your installed version.
component: optimizer
argument-hint: "--workdir DIR --prompt FILE"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: []
sources: []
---

# openclaw optimizer

OpenClaw stores skills under `~/.openclaw/workspace/skills/<skill>/SKILL.md` and is driven
by `AGENTS.md` / `SOUL.md` / `TOOLS.md`. Unlike claude-code / codex / gemini / opencode, it
does **not** expose a single, stable, documented headless "edit these files and exit"
command — the surface varies by build and configuration. So this skill is a documented,
configurable wrapper rather than a hard-coded invocation: you tell it the exact command and
it plugs into the loop the same way every other optimizer does.

## Install / auth
Follow your OpenClaw distribution's own install + onboarding (typically `openclaw onboard`)
and set whatever provider credentials it expects in the environment. Verify the binary:
```bash
openclaw --version
```

## Configure
```bash
export ACAPO_OPENCLAW_CMD='openclaw run --workspace {workdir} "{prompt_text}"'
```
Placeholders substituted at run time:
- `{workdir}` — the candidate working directory (also set as cwd).
- `{prompt}` — the path to `INSTRUCTIONS.md`.
- `{prompt_text}` — the contents of `INSTRUCTIONS.md` (use this if your build takes the
  task inline rather than as a file path).

The wrapped command **must** edit files under `{workdir}` and exit non-interactively
(no TTY prompts), returning exit code 0 on success. Whatever flag your build uses to
auto-approve writes (an `--auto`/`--yolo`-style switch, or a config setting) belongs in
this template — find it with `openclaw --help` / `openclaw run --help`. If you can't get a
reliable headless edit command, use the `generic` optimizer instead (same contract).

## How it edits files
`run.py` substitutes the placeholders, then runs the resolved command with
**cwd = `{workdir}`** so edits land in the candidate copy. The loop's `INSTRUCTIONS.md`,
`MEMORY.md`, and `STATE.md` are all present in that directory for OpenClaw to read.

## Using it well
- The per-iteration task is in `INSTRUCTIONS.md`; put durable guidance in OpenClaw's
  `AGENTS.md`/`SOUL.md` if your build reads them from the workspace.
- Verify the real flags against your installed version — this default is a best guess, and
  the binary's subcommands change between builds.

## Availability
`scripts/run.py` checks the resolved command's binary on PATH and errors clearly if it is
absent (telling you to set `ACAPO_OPENCLAW_CMD` or fall back to `generic`).
`scripts/check.py` passes without the CLI so CI is not blocked.

## How to run
```bash
python scripts/check.py
ACAPO_OPENCLAW_CMD='openclaw run --workspace {workdir} "{prompt_text}"' \
  python scripts/run.py --workdir <copy> --prompt <INSTRUCTIONS.md>
```

## References
- `references/concepts.md` — the universal edit-proposer contract + per-CLI notes + sources.
