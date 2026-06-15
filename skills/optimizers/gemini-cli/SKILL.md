---
name: gemini-cli
description: Use Google's Gemini CLI headless as the edit proposer. Use when you want Gemini to propose capability edits. Runs `gemini -p "<instructions>" --approval-mode=yolo -m <model>` with cwd set to the candidate working directory so Gemini edits files in place. Documents the verified install, auth, the non-interactive prompt flag, the approval mode (replacing the deprecated --yolo), and GEMINI.md context.
component: optimizer
argument-hint: "--workdir DIR --prompt FILE [--model ID]"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: []
sources: []
---

# gemini-cli optimizer

Drives the [Gemini CLI](https://github.com/google-gemini/gemini-cli) — the `gemini`
command — non-interactively. The loop hands it a throwaway copy of the candidate plus an
`INSTRUCTIONS.md`; Gemini edits the files in that directory in place and exits.

## Install
```bash
npm install -g @google/gemini-cli       # Node 20+; or run with no install: npx @google/gemini-cli
# or: brew install gemini-cli
gemini --version                         # verify on PATH
```

## Authenticate
- **`GEMINI_API_KEY`** — export it (key from https://aistudio.google.com/apikey) for
  unattended/CI runs. This is the headless-friendly path.
- **Google OAuth** — run `gemini` once and "Sign in with Google" in the browser; cached
  locally. Good for local use, not fresh CI.
- **Vertex AI** — `GOOGLE_API_KEY` + `GOOGLE_GENAI_USE_VERTEXAI=true` for enterprise.

## Invocation
```bash
gemini -p "<instructions>" --approval-mode=yolo -m <model>     # cwd = the candidate dir
```
Key flags (verified against the Gemini CLI reference):
- `-p` / `--prompt` — prompt text; **forces non-interactive mode** (also triggered by a
  non-TTY environment).
- `--approval-mode` — auto-approval level: `default`, `auto_edit` (auto-accept edits only),
  `yolo` (auto-approve everything), `plan`. Use **`yolo`** so Gemini can write files
  unattended; the workdir is a throwaway candidate copy, so this is safe. The old
  `--yolo` / `-y` is a **deprecated** alias — the docs say to use `--approval-mode=yolo`.
- `-m` / `--model <id>` — choose the model (default `auto`); also via `ACAPO_OPTIMIZER_MODEL`.
- `--output-format` / `-o` — `text` (default), `json`, or `stream-json` for structured runs.
- `--include-directories <a,b>` — add directories to the workspace (rarely needed since the
  candidate dir is the cwd).
- `--sandbox` / `-s` — run inside Gemini's sandbox; orthogonal to approval mode.

## How it edits files
`run.py` reads `INSTRUCTIONS.md`, then runs `gemini -p` with **cwd = `--workdir`**, so
Gemini edits the candidate copy in place. Gemini loads `GEMINI.md` from the workdir as
context — put standing guidance there. The loop's `MEMORY.md` / `STATE.md` are in the
same dir for it to read and update.

## Using it well
- The per-iteration task arrives in `INSTRUCTIONS.md` (the loop's diagnosis + rejected
  memory); reference durable guidance from `GEMINI.md`. Richer diagnosis → better edits.
- Prefer many cheap iterations (let the gate filter) over one giant edit.
- Version-dependent: `--yolo` still works but is deprecated; pin a version or probe
  `gemini --help` since the approval surface is mid-migration.

## Availability
`scripts/run.py` checks for `gemini` on PATH; `scripts/check.py` passes without it.

## How to run
```bash
python scripts/check.py
python scripts/run.py --workdir <copy> --prompt <INSTRUCTIONS.md> --model <id>
```

## References
- `references/concepts.md` — the universal edit-proposer contract + per-CLI notes + sources.
