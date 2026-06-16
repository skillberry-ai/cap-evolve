---
name: ibm-bob
description: Use IBM Bob Shell (the `bob` CLI) as the edit proposer. Use when your optimizer is IBM Bob. Runs Bob non-interactively in the candidate working directory (`bob --accept-license --yolo --chat-mode code "<instructions>"`) so it reads the diagnosis and edits the capability files in place. Documents how to install Bob, authenticate it, and drive it well.
component: optimizer
argument-hint: "--workdir DIR --prompt FILE [--model ID]"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: []
sources: []
---

# ibm-bob optimizer

Drives [IBM Bob Shell](https://bob.ibm.com) — the `bob` CLI — to propose edits.

## Install
```bash
curl -fsSL https://bob.ibm.com/download/bobshell.sh | bash -s -- --package-manager npm
bob --version    # verify
```

## Authenticate
Bob reads the **`BOBSHELL_API_KEY`** environment variable. This skill populates it
automatically from `BOBSHELL_API_KEY`, or `BOB_API_KEY` (env or the repo `.env`):
```bash
export BOB_API_KEY=...      # the skill maps this to BOBSHELL_API_KEY for the run
```

## Invocation
```bash
bob --accept-license --yolo --chat-mode code "<instructions>"     # cwd = the candidate dir
```
- positional prompt = non-interactive **one-shot** (`-p/--prompt` is deprecated upstream).
- `--yolo` (≡ `--approval-mode yolo`) auto-approves all actions so Bob can **write
  files** (off by default). The workdir is a throwaway candidate copy, so this is safe.
- `--accept-license` accepts the IBM license on the first run in a fresh env.
- `--chat-mode code` selects the coding mode; `--hide-intermediary-output` keeps stdout clean.
- `-m/--model` (or `CAPEVOLVE_OPTIMIZER_MODEL`) picks the model.

## Using it well
- The loop writes the reflection (diagnosis + rejected-memory + a pointer to the run
  dir) into `INSTRUCTIONS.md`; richer diagnosis → better edits.
- Cap spend with `--max-coins N` (Bob exits non-zero if exceeded) if needed.

## Availability
`scripts/run.py` checks for `bob` on PATH and prints the install command if missing;
`scripts/check.py` passes without the CLI so CI is not blocked.
