# Concepts: the edit-proposer contract (codex)

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

## This CLI: OpenAI Codex (`codex`)

- **Headless command**: `codex exec --sandbox workspace-write -m <model> "<instructions>"`.
- **`codex exec`** (alias `codex e`) is the non-interactive subcommand; prompt is positional
  or `-` for stdin.
- **`--sandbox` / `-s`**: `read-only` | `workspace-write` | `danger-full-access`. Use
  `workspace-write` (edit files, no network). **`--full-auto` is deprecated** in favor of
  `--sandbox workspace-write`.
- **Model**: `-m` / `--model`; also `ACAPO_OPTIMIZER_MODEL`. Reasoning effort via
  `-c model_reasoning_effort=high`.
- **Auth**: `codex login` (ChatGPT OAuth, cached under `~/.codex/`) or
  `codex login --with-api-key` / `OPENAI_API_KEY` for headless/CI; `--device-auth` for
  headless boxes.
- **Context file**: reads `AGENTS.md` from the workdir (and parents) for standing guidance.
- **Other flags**: `--cd`/`-C` (workspace root), `--json` (+ `--output-last-message`),
  `--skip-git-repo-check`, `-c key=value` config overrides.
- **Version note**: the auto-approve surface shifted (`--full-auto` → `--sandbox`); confirm
  with `codex exec --help`.

## Sources
- Codex CLI reference (`codex exec`, `--sandbox`, `-m`, `--full-auto` deprecation, `--json`,
  `--cd`, `-c`, `--skip-git-repo-check`): https://developers.openai.com/codex/cli/reference
- Codex CLI install + auth (`codex login`, `--with-api-key`, `OPENAI_API_KEY`):
  https://developers.openai.com/codex/cli
- AGENTS.md guidance: https://developers.openai.com/codex/guides/agents-md
- Codex CLI repo: https://github.com/openai/codex
