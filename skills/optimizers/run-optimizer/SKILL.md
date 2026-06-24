---
name: run-optimizer
description: Drives any shell-invokable coding agent (Claude Code, Codex, Gemini CLI, opencode, Cursor, Factory Droid, GitHub Copilot CLI, Kimi, Pi, Antigravity, OpenClaw, IBM Bob, or a fully custom command) as the edit proposer in a cap-evolve run, resolving the named optimizer from optimizers/registry.yaml. Use this as the optimizer for every run; pick the concrete agent with --name (or optimizer_skill in the spec). Use --name mock for a deterministic, zero-API proposer in tests and CI.
component: optimizer
argument-hint: "--name NAME --workdir DIR --prompt FILE [--model ID]"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: []
---

# run-optimizer — one runner, a registry of agents

An *optimizer* is the agent that reads the current capability + the failure
diagnosis and proposes an edit. Every such agent follows the same contract: given
a working directory (a copy of the parent candidate) and an `INSTRUCTIONS.md`,
edit the files in place. Because the contract is identical, one runner serves them
all — the only thing that varies per agent is the shell command, which lives as a
row in `optimizers/registry.yaml`. Adding an optimizer is **one YAML row**, not a
new skill directory.

## How it works

1. The loop calls `run.py --name <optimizer> --workdir <copy> --prompt INSTRUCTIONS.md`.
2. The runner reads the registry, resolves the row, and expands its
   `command_template` (placeholders below) into argv.
3. It runs that command with `cwd = workdir`, so the agent edits the candidate
   files directly. Output is summarized as JSON (`returncode`, `auth_present`,
   `stdout_tail`).

### Template placeholders
| placeholder | expands to |
|---|---|
| `{workdir}` | the candidate working copy (also the cwd) |
| `{prompt}` | path to `INSTRUCTIONS.md` |
| `{prompt_text}` | the *contents* of `INSTRUCTIONS.md` (for CLIs that take the prompt inline) |
| `{model}` | the resolved model id; an empty `{model}` drops itself and a preceding `-m`/`--model` |
| `{self_dir}` | the runner's own scripts dir (used by the `mock` row) |
| `${VAR}` | environment expansion (the `generic`/`openclaw`/`antigravity` escape hatches read their command from env) |

## Choosing an optimizer (`--name` / `optimizer_skill`)

`mock`, `generic`, `claude-code`, `codex`, `gemini-cli`, `opencode`, `cursor`,
`droid` (Factory Droid), `copilot` (GitHub Copilot CLI), `kimi`, `pi`,
`antigravity`, `openclaw`, `ibm-bob`. Per-CLI install / auth / flag details are in
`references/<name>.md`.

- **`mock`** is fully offline (runs a shipped JSON-driven editor, never a network
  CLI), so the end-to-end proof slice costs nothing and never flakes.
- **`generic`** / **`openclaw`** / **`antigravity`** read their command from
  `CAPEVOLVE_OPTIMIZER_CMD` / `CAPEVOLVE_OPENCLAW_CMD` / `CAPEVOLVE_ANTIGRAVITY_CMD`
  — the escape hatch that makes "any optimizer" literal. (`antigravity` is a wrapper
  because its auth is Google-Sign-In-only and its headless approve flag is unconfirmed.)
- **`cursor`**, **`droid`**, **`copilot`**, **`kimi`**, **`pi`** are verified
  headless commands; matches the agent set supported by obra/superpowers.

## Standalone use

```bash
# list known optimizers
python scripts/run.py --list
# drive one agent over a candidate dir
python scripts/run.py --name claude-code --workdir ./cand --prompt ./cand/INSTRUCTIONS.md --model claude-opus-4-6
```

In a run, the orchestrator builds this command for you from the spec's
`optimizer_skill` (the optimizer NAME) and `optimizer_model`.

## Headless JSON cost capture (optional, best-effort)

Coding-agent CLIs can emit a structured result that carries the exact spend.
Pass `--json` (or set `CAPEVOLVE_OPTIMIZER_JSON=1`) and the runner appends the
registry row's **`json_flag`** to the command, then parses `total_cost_usd`
(and token usage) out of the output:

```bash
python scripts/run.py --name claude-code --json \
  --workdir ./cand --prompt ./cand/INSTRUCTIONS.md --model claude-opus-4-6
# -> {... "cost": {"total_cost_usd": 0.0123, "tokens": 4210}}
```

Per CLI (verify with `<cli> --help`):
- **claude-code** — `json_flag: --output-format json`; the JSON result has
  `total_cost_usd`, `usage`, and per-model cost under `modelUsage`. Add
  `--json-schema '<JSONSchema>'` (via `--json-schema` here, or
  `CAPEVOLVE_OPTIMIZER_JSON_SCHEMA`) to also get `.structured_output` for a
  decision step. The runner only appends `--json-schema` when the row's json_flag
  contains `--output-format`.
- **codex** — `json_flag: --json` (a JSONL stream); pair with
  `codex exec --json --output-last-message <file>` when you want the final message
  on disk. The runner parses the last JSON line for cost/usage.
- **gemini-cli** — `json_flag: --output-format json`; `total_cost_usd`/`usage` are
  parsed when present.

**This is strictly additive.** With no `--json`, or for a row whose `json_flag` is
empty (`mock`, `generic`, `opencode`, `openclaw`, `ibm-bob`), nothing changes —
the optimizer runs prose-fed exactly as before, and `mock` stays fully offline. If
the output isn't parseable JSON, `cost.total_cost_usd` is `null` and the loop
continues without a cost figure (never an error).

## Back-compat

A spec that still names an old per-CLI optimizer skill (`claude-code`, `ibm-bob`,
…) resolves to the registry row of the same name, so existing specs keep working
without edits.

## References
- `references/<name>.md` — install, auth, and flags for each CLI.
