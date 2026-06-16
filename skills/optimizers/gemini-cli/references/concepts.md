# Concepts: the edit-proposer contract (gemini-cli)

## The universal edit-proposer contract

Every cap-evolve optimizer — claude-code, codex, gemini-cli, opencode, openclaw, generic,
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
  workdir), **cwd = workdir**, **model selectable** (`--model` / `CAPEVOLVE_OPTIMIZER_MODEL`),
  and **clear absence handling** (errors with guidance if the CLI is missing; `check.py`
  still passes).

## This CLI: Gemini CLI (`gemini`)

- **Headless command**: `gemini -p "<instructions>" --approval-mode=yolo -m <model>`.
- **`-p` / `--prompt`** supplies the prompt and **forces non-interactive mode** (also
  triggered by a non-TTY environment).
- **`--approval-mode`**: `default` | `auto_edit` (auto-accept edits only) | `yolo`
  (auto-approve everything) | `plan`. Use `yolo` to write files unattended. **`--yolo` / `-y`
  is a deprecated alias** — the docs say to use `--approval-mode=yolo`.
- **Model**: `-m` / `--model` (default `auto`); also `CAPEVOLVE_OPTIMIZER_MODEL`.
- **Auth**: `GEMINI_API_KEY` (headless/CI; key from aistudio.google.com/apikey), Google OAuth
  (`gemini` then sign in), or Vertex (`GOOGLE_API_KEY` + `GOOGLE_GENAI_USE_VERTEXAI=true`).
- **Context file**: reads `GEMINI.md` from the workdir.
- **Other flags**: `--output-format`/`-o` (`text`|`json`|`stream-json`),
  `--include-directories`, `--sandbox`/`-s`.
- **Version note**: `--yolo` still works but is deprecated; the approval surface is
  mid-migration — confirm with `gemini --help`.

## Sources
- Gemini CLI reference / cheatsheet (`--approval-mode` values + `--yolo` deprecation, `-p`,
  `-m`, `--output-format`, `--include-directories`, `--sandbox`):
  https://www.geminicli.com/docs/cli/cli-reference/
- Gemini CLI headless/scripting mode: https://www.geminicli.com/docs/cli/headless
- Gemini CLI install + auth (npm `@google/gemini-cli`, `GEMINI_API_KEY`, OAuth, Vertex):
  https://github.com/google-gemini/gemini-cli
- Context files (GEMINI.md): https://www.geminicli.com/docs/cli/gemini-md
