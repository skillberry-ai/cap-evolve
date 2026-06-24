# Design: multi-agent support parity with obra/superpowers

**Date:** 2026-06-24
**Status:** Approved (design); implementation pending

## Goal

Bring cap-evolve's supported coding-agent set up to parity with
[obra/superpowers](https://github.com/obra/superpowers). Superpowers supports 11
harnesses; cap-evolve already covers the overlapping ones (Claude Code, Codex,
Gemini CLI, opencode). This adds the **6 agents cap-evolve lacks**:

- **Cursor** (`cursor-agent` CLI)
- **Factory Droid** (`droid` CLI)
- **GitHub Copilot CLI** (`copilot` CLI)
- **Kimi** (`kimi` CLI, Moonshot AI)
- **Pi** (`pi` CLI, earendil-works)
- **Antigravity** (`agy` CLI, Google)

Support is added across **both layers** that "supporting an agent" means in
cap-evolve:

- **(a) Optimizer / edit-proposer** — the agent can DRIVE the optimization loop
  (a `registry.yaml` row + verified headless command).
- **(b) Install host** — cap-evolve's skills can be INSTALLED into that agent's
  skills dir (`install.sh --host <name>`).

## Architecture fit

The current (top-level) tree already abstracts every optimizer behind one
`run-optimizer` runner driven by `skills/optimizers/registry.yaml`. The generic
`scripts/run.py` already:

- expands `{workdir}`, `{prompt}`, `{prompt_text}`, `{model}`, `{self_dir}`,
  and `${ENV}` placeholders,
- drops the `-m`/`--model` flag group when no model is set,
- appends `json_flag` / `budget_flag` / `usd_budget_flag` on demand,
- checks the CLI is on `PATH` and reports which auth env vars are present.

**Therefore no Python changes are required.** Each new agent is **one YAML row +
one prose reference file**, plus enumeration updates in docs/installer.

## 1. Registry rows (`skills/optimizers/registry.yaml`)

Verified headless commands (researched against official docs/repos):

| key | command_template | auth env | json_flag | pattern |
|---|---|---|---|---|
| `cursor` | `cursor-agent -p {prompt_text} --force --model {model}` | `CURSOR_API_KEY` | `--output-format json` | verified |
| `droid` | `droid exec --auto low -m {model} {prompt_text}` | `FACTORY_API_KEY` | `--output-format json` | verified |
| `copilot` | `copilot -p {prompt_text} --allow-all-tools --model {model}` | `COPILOT_GITHUB_TOKEN,GH_TOKEN,GITHUB_TOKEN` | `""` | verified |
| `kimi` | `kimi -p {prompt_text} -m {model}` | `MOONSHOT_API_KEY,KIMI_API_KEY` | `""` | verified cmd; auth env unverified |
| `pi` | `pi -p {prompt_text} --model {model}` | `ANTHROPIC_API_KEY,OPENAI_API_KEY` | `""` | verified; no approve flag by design |
| `antigravity` | `${CAPEVOLVE_ANTIGRAVITY_CMD}` | `CAPEVOLVE_ANTIGRAVITY_CMD` | `""` | configurable wrapper (like `openclaw`) |

Common fields: `budget_flag: ""`, `usd_budget_flag: ""`, `offline: "false"`.
`instructions_file: AGENTS.md` for the agents that read it (cursor/droid/copilot/
kimi). `skills_dir` is set only where native skill discovery is documented;
otherwise omitted and explained in prose (honest about what is unverified).

### Why Antigravity is a configurable wrapper

`agy -p` is a real headless print mode, but research could not confirm (1) a
CI-usable API-key env var — auth is Google Sign-In / OS keyring — nor (2) the exact
non-interactive auto-approve flag. Rather than ship an unverified command, it
mirrors the `openclaw` escape-hatch: the user sets the full command via
`CAPEVOLVE_ANTIGRAVITY_CMD` (recommended best-guess documented in its reference).

## 2. Reference prose (`skills/optimizers/run-optimizer/references/<name>.md`)

One file per agent (`cursor.md`, `droid.md`, `copilot.md`, `kimi.md`, `pi.md`,
`antigravity.md`), modeled on the existing `codex.md`: install, auth, the headless
invocation, JSON/cost notes, native-skills/instructions conventions, and explicit
caveats (Kimi auth, Pi no-prompts, Antigravity OAuth-only).

## 3. Cross-cutting enumeration + installer updates

Every place that lists the optimizer set (found via grep):

- `skills/optimizers/run-optimizer/SKILL.md` — description (line ~3) + known
  optimizers list (lines ~42–43).
- `README.md` — inline lists (~329, ~374) + feature-matrix optimizers row (~504)
  + install/hosts prose.
- `install.sh` — `--host` detection: add `antigravity`, `droid`/`factory`,
  `copilot`, `kimi`, `pi` skills-dir cases (`cursor` already present).
- `templates/project/capevolve.yaml`, `templates/project/PROJECT.md` — optimizer
  enumeration comments.
- `skills/phases/intake/inputs/INPUTS.md` — optimizer enumeration.
- `RUN.md`, `llms.txt` — optimizer enumerations.
- `CHANGELOG.md` — `[Unreleased] / Added` entry.

## 4. Verification

- `python skills/optimizers/run-optimizer/scripts/run.py --list` lists all 14
  optimizers (8 existing + 6 new).
- For each new name, run with `--name <agent>` against a throwaway workdir with the
  CLI absent → expect the clean `"<cli>" not on PATH` JSON with install + auth hint
  (proves the row resolves and the command builds).
- `mock` end-to-end stays green; `run-optimizer/scripts/check.py` passes.

## Out of scope (YAGNI)

- No Python changes (the registry-driven runner already generalizes).
- No per-agent skill folders (the registry replaced those).
- No live API calls to the 6 CLIs (cannot verify creds in this environment).
- The deleted nested `cap-evolve/` tree is not touched.
