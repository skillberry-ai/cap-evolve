---
name: codex
description: Use OpenAI's Codex CLI headless as the edit proposer. Use when you want Codex to propose capability edits. Runs `codex exec --sandbox workspace-write -m <model> "<instructions>"` with cwd set to the candidate working directory so Codex edits files in place. Documents the verified install, auth, the non-interactive `exec` command, the sandbox flag (replacing the deprecated --full-auto), and how to drive it well.
component: optimizer
argument-hint: "--workdir DIR --prompt FILE [--model ID]"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: []
sources: []
---

# codex optimizer

Drives the [OpenAI Codex CLI](https://developers.openai.com/codex/cli) in its
non-interactive `exec` mode. The loop hands it a throwaway copy of the candidate plus an
`INSTRUCTIONS.md`; Codex edits the files in that directory in place and exits.

## Install
```bash
npm install -g @openai/codex            # also: brew install codex
# or: curl -fsSL https://chatgpt.com/codex/install.sh | sh
codex --version                          # verify on PATH
```

## Authenticate
On first run Codex prompts you to sign in. For headless/CI use, pick one:
- **`codex login --with-api-key`** — reads the key from stdin (`echo $OPENAI_API_KEY | codex login --with-api-key`), or just export **`OPENAI_API_KEY`** in the environment / repo `.env`.
- **`codex login`** — browser OAuth with a ChatGPT account (cached under `~/.codex/`); good locally, not for fresh CI. `--device-auth` helps on headless boxes.

## Invocation
```bash
codex exec --sandbox workspace-write -m <model> "<instructions>"     # cwd = the candidate dir
```
Key flags (verified against the Codex CLI reference):
- `codex exec` (alias `codex e`) — the non-interactive subcommand. The prompt is the
  positional arg, or pass `-` to read it from stdin.
- `--sandbox` / `-s` — file-access level: `read-only`, `workspace-write` (edit files in the
  workspace, no network), or `danger-full-access`. Use **`workspace-write`** here; the
  workdir is a throwaway candidate copy, so writing into it is safe. `--full-auto` is a
  **deprecated** compatibility flag — prefer `--sandbox workspace-write`.
- `-m` / `--model <id>` — choose the model; also via `CAPEVOLVE_OPTIMIZER_MODEL`.
- `--cd` / `-C <dir>` — set the workspace root (the skill instead sets cwd to `--workdir`,
  which is equivalent and what the loop expects).
- `--json` — emit newline-delimited JSON events instead of prose; pair with
  `--output-last-message <file>` to capture a final summary in CI.
- `-c key=value` (repeatable) — override any config value, e.g. `-c model_reasoning_effort=high`.
- `--skip-git-repo-check` — allow running when the workdir is not a git repo.

## How it edits files
`run.py` reads `INSTRUCTIONS.md`, then runs `codex exec` with **cwd = `--workdir`**, so
Codex edits the candidate copy in place. Codex also reads an `AGENTS.md` file from the
workdir (and parent dirs) for standing project guidance — you can add persistent
optimizer hints there. The loop's `MEMORY.md` / `STATE.md` live in the same dir.

## Using it well
- Instructions come from `INSTRUCTIONS.md` (the loop's diagnosis + rejected memory); the
  richer the diagnosis, the better the edits.
- Put durable, cross-iteration guidance in `AGENTS.md`; put the per-iteration task in
  `INSTRUCTIONS.md`.
- Tune effort with `-c model_reasoning_effort=...` rather than a giant single edit.
- Version-dependent: the auto-approve surface has shifted (`--full-auto` → `--sandbox`).
  Confirm with `codex exec --help` for your installed version.

## Availability
`scripts/run.py` checks for `codex` on PATH; `scripts/check.py` passes without it.

## How to run
```bash
python scripts/check.py
python scripts/run.py --workdir <copy> --prompt <INSTRUCTIONS.md> --model <id>
```

## References
- `references/concepts.md` — the universal edit-proposer contract + per-CLI notes + sources.
