---
name: generic
description: Use ANY shell-invokable coding agent as the edit proposer. Use when your optimizer of choice has a CLI but no dedicated agent-capo optimizer skill yet — set ACAPO_OPTIMIZER_CMD to its edit command (with {workdir} and {prompt} placeholders) and it plugs into the loop. This is the escape hatch that makes "any optimizer" literally true.
component: optimizer
argument-hint: "--workdir DIR --prompt FILE [--cmd 'agent --dir {workdir} --inst {prompt}']"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: []
sources: []
---

# generic optimizer

Bridges the loop to any agent CLI. The loop hands this skill a workdir (a copy of the
candidate) and an `INSTRUCTIONS.md`; it runs your configured command with **cwd = workdir**
so the agent edits files in place and exits.

## Configure
```bash
export ACAPO_OPTIMIZER_CMD='my-agent edit --dir {workdir} --instructions {prompt}'
# or pass it per-run with --cmd '...'
```
Placeholders substituted at run time:
- `{workdir}` — the candidate working directory (also set as the subprocess cwd).
- `{prompt}` — the path to `INSTRUCTIONS.md` (the loop's diagnosis + rejected memory).

If your agent takes the task inline rather than as a file path, point it at the path and
let it read the file, or wrap it in a tiny shell snippet (e.g.
`sh -c 'my-agent "$(cat {prompt})"'`).

## Requirements for the wrapped agent
- Non-interactive / headless mode (no TTY prompts) — it must run to completion unattended.
- Auto-approves its own file writes (most agents need an explicit `--yes`/`--auto`/
  `--yolo`/`--dangerously-skip-permissions`-style flag — include it in the template).
- Edits files under `{workdir}` (relative paths resolve there because cwd = workdir).
- Exit code 0 on success; non-zero signals a failed proposal (the loop tolerates this and
  keeps the parent candidate for that iteration).

## How it edits files
`run.py` substitutes the placeholders and runs the command with cwd = workdir. The loop
also drops `MEMORY.md` and `STATE.md` into the same directory; reference them from
`INSTRUCTIONS.md` if your agent should use them.

## When to prefer a dedicated skill
The `claude-code`, `codex`, `gemini-cli`, and `opencode` skills already encode the verified
headless command, auth, and flags for those CLIs — use them directly. Reach for `generic`
only when no dedicated skill exists for your agent.

## How to run
```bash
python scripts/check.py
ACAPO_OPTIMIZER_CMD='...' python scripts/run.py --workdir <copy> --prompt <INSTRUCTIONS.md>
```

## References
- `references/concepts.md` — the universal edit-proposer contract + per-CLI notes + sources.
