# Concepts: the edit-proposer contract (opencode)

## The universal edit-proposer contract

Every agent-capo optimizer — claude-code, codex, gemini-cli, opencode, openclaw, generic,
mock — implements the **same** contract. The optimize loop, not the agent, owns the
orchestration:

1. **The loop prepares a workdir.** It copies the current best candidate into a fresh,
   throwaway directory (`<run>/work/<candidate-id>/`). Because it is a copy, the agent may
   edit freely — accepting/bypassing edit permissions is safe.
2. **The loop writes context files into that workdir:**
   - `INSTRUCTIONS.md` — the task: why the current candidate underperforms + what to try
     (and a pointer to the run-output dir).
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
5. **The loop evaluates the mutated workdir**, gates it against the parent, and either
   accepts it as the new best or rejects it (recording the reason into memory).

The agent never sees the eval harness, the gate, or the version store — it only sees a
directory of files, a task, and its memory. That is what lets *any* headless coding CLI
serve as the optimizer.

### What a good `run.py` invocation guarantees
- **Headless** (no REPL/TTY prompts), **write-enabled** (edits auto-approved on a disposable
  workdir), **cwd = workdir**, **model selectable** (`--model` / `ACAPO_OPTIMIZER_MODEL`),
  and **clear absence handling** (errors with guidance if the CLI is missing; `check.py`
  still passes).

## This CLI: opencode (`opencode`)

- **Headless command**: `opencode run --dangerously-skip-permissions "<instructions>"`.
- **`opencode run [message..]`** is the headless one-shot; bare `opencode` opens the TUI.
- **`--dangerously-skip-permissions`** auto-approves permissions not explicitly denied so it
  can write files unattended. Finer control: set `OPENCODE_PERMISSION` to an inlined JSON
  permissions config.
- **Model**: `-m` / `--model <provider/model>` (e.g. `anthropic/claude-sonnet-4-6`); also
  `ACAPO_OPTIMIZER_MODEL`.
- **Auth**: `opencode auth login` (pick provider, paste key), `opencode auth list`; or set the
  provider key in the env for unattended runs. Provider-agnostic via models.dev.
- **Other flags**: `--agent <name>`, `--format json`, `--continue`/`-c`, `--session`/`-s`,
  `--attach <url>` (with `opencode serve` to avoid MCP cold-boot on repeated runs).
- **agent-capo native**: opencode reads Anthropic-compatible `SKILL.md` and `.claude/skills/`
  directly, so the agent-capo skill library installs with zero translation.
- **Version note**: confirm model-id format and flags with `opencode run --help`.

## Sources
- opencode CLI reference (`opencode run`, `-m`, `--dangerously-skip-permissions`, `--format`,
  `--agent`, `auth login`, `OPENCODE_PERMISSION`): https://opencode.ai/docs/cli/
- opencode install + provider/auth setup: https://opencode.ai/docs/
- opencode docs home: https://opencode.ai/docs
