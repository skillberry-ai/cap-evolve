# Installation

cap-evolve has one small required install (the honest-eval core) and a few optional
add-ons depending on how you want to drive it. Requires **Python 3.10+** and **git**.

```bash
git clone https://github.com/skillberry-ai/cap-evolve.git
cd cap-evolve
python3 -m venv .venv && source .venv/bin/activate   # recommended: isolated env
```

## Required — the core (honest-eval substrate + CLI)

```bash
pip install ./core        # package: cap-evolve-core · CLI: cap-evolve · zero runtime deps
cap-evolve version        # verify
```

> If your default pip index requires auth, append `--index-url https://pypi.org/simple`
> (cap-evolve-core itself has no runtime dependencies).

The `cap-evolve` CLI has six subcommands: `version`, `splits`, `check`, `run`,
`estimate`, `dashboard`.

## Optional — the live dashboard (separate package)

```bash
pip install ./dashboard/backend            # package: capevolve-dashboard
cap-evolve dashboard --base .capevolve --port 7878   # or: cap-evolve run --dashboard auto
```

No backend needed to watch a run in the terminal: `cap-evolve run --follow` prints live
progress, and `cap-evolve tail [run_dir]` attaches to a run started elsewhere.

A prebuilt frontend is committed under `dashboard/frontend/dist/`. Every run also writes a
self-contained static `dashboard.html` you can open with no backend.

## Choose your path

### A. Claude Code plugin (recommended for Claude Code users)

Loads every phase/algorithm/optimizer skill as a `/cap-evolve:<skill>` command and arms
honesty hooks (deny edits to the sealed test/gold; block finishing until `cap-evolve
check` + the gate are green):

```bash
claude --plugin-dir ./plugins/cap-evolve
pip install ./core
```

Then point the agent at [`../RUN.md`](../RUN.md) (or just say "optimize X" — the
`using-cap-evolve` router auto-triggers).

### B. Another coding-agent host (Codex, Gemini, opencode, Cursor, Droid, Copilot, Kimi, Pi, Antigravity, openclaw, IBM Bob, bare)

`install.sh` copies the skills into your host's skills directory and rebuilds the registry
manifest — it does **not** install the Python package (do that separately):

```bash
./install.sh                 # auto-detect host skills dir; or:
./install.sh --host codex    # pick a known host   (claude|codex|gemini|opencode|cursor|droid|copilot|kimi|pi|antigravity|openclaw|bob)
./install.sh --dest DIR      # explicit destination
./install.sh --link          # symlink instead of copy (dev)
pip install ./core           # or: export CAPEVOLVE_CORE="$PWD/core"
```

Destination precedence: `$CAPEVOLVE_SKILLS_DIR` > `--host` mapping > `./.claude/skills` >
`~/.claude/skills` > `~/.capevolve/skills`.

### C. Manual adapter + CLI (any language/agent)

```bash
pip install ./core
# scaffold, implement the adapter, then:
cap-evolve check .capevolve/project                             # hard gate — must print {"ok": true}
cap-evolve run   --spec .capevolve/project/capevolve.yaml --project .capevolve/project
```

See [`OPTIMIZE_YOUR_OWN.md`](OPTIMIZE_YOUR_OWN.md) and [`ADAPTER_CONTRACT.md`](ADAPTER_CONTRACT.md).

## Credentials (only for real runs)

The toy example needs none. Optimizing a real agent needs, in a repo-root `.env`:
- a **coding-agent CLI** to act as the optimizer (e.g. `claude`, `codex`, `gemini`) with
  its credentials (e.g. a logged-in Claude Code session or `ANTHROPIC_API_KEY`);
- your **runner** model credentials (e.g. `OPENAI_API_KEY`, `RITS_API_KEY` + `RITS_API_URL`,
  `WATSONX_*`, or an `ANTHROPIC_BASE_URL` gateway).

Never hardcode a secret; cap-evolve executes untrusted optimizer/adapter/tool code — see
[`../SECURITY.md`](../SECURITY.md). Trouble? [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).

### Resolution order (provider + credentials)

One documented precedence, applied **per field** (`provider`, `provider_base_url`,
`provider_credential_env`) — the highest layer that sets a non-empty value wins:

**CLI flag > project `capevolve.yaml` > user config (`~/.capevolve/config.yaml`, or
`$CAPEVOLVE_CONFIG`) > built-in default.**

CLI flags: `--provider`, `--provider-base-url`, `--provider-credential-env`,
`--probe-provider`. Spec keys: `provider`, `provider_base_url`,
`provider_credential_env`. With no `provider` anywhere, it is inferred from
`optimizer_skill` (`claude-code`→`anthropic`, `codex`→`openai`, …).

### Credentials are provider-scoped

Each provider reads **only its own** env vars. A key for provider A is **never** applied
to provider B — cap-evolve fails with a message naming the vars B accepts. This is the
whole point: a stale `ANTHROPIC_API_KEY` from another project cannot silently
authenticate (or confusingly fail) an `openai` run.

| provider | credential env vars (first set wins) | base URL env | built-in base URL |
|---|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` | `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` |
| `openai` | `OPENAI_API_KEY` | `OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| `gemini` | `GEMINI_API_KEY`, `GOOGLE_API_KEY` | `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta` |
| `rits` | `RITS_API_KEY` | `RITS_API_URL` | — (required) |
| `watsonx` | `WATSONX_APIKEY`, `WATSONX_API_KEY` | `WATSONX_URL` | — (required) |
| `moonshot` | `MOONSHOT_API_KEY`, `KIMI_API_KEY` | `MOONSHOT_BASE_URL` | `https://api.moonshot.ai/v1` |
| `github-copilot` | `COPILOT_GITHUB_TOKEN`, `GH_TOKEN`, `GITHUB_TOKEN` | `COPILOT_BASE_URL` | `https://api.githubcopilot.com` |
| `bob` | `BOBSHELL_API_KEY`, `BOB_API_KEY` | `BOBSHELL_URL` | — (required) |
| `cursor` | `CURSOR_API_KEY` | `CURSOR_BASE_URL` | — (required) |
| `factory` | `FACTORY_API_KEY` | `FACTORY_BASE_URL` | — (required) |
| `mock` | none (offline) | — | — |

`provider_credential_env` names an **env var**, never a pasted key — a value belonging to
a different provider is refused. Secret **values** live only in the process environment;
cap-evolve reports presence/absence and never logs a value (not a prefix, not a length).

### `provider: auto`

`provider: auto` (or `--provider auto`) picks the first provider in the table above that
has **its own** credential set, and prints which and why. Add `--probe-provider` to also
require that candidate's endpoint answer before selecting it. A probe only ever sends a
credential to the base URL of the **same** provider row the credential came from, so a
token can never reach a third party.

```
$ cap-evolve run --provider auto --probe-provider --spec ...
{"step": "provider", "provider": "anthropic", "credential_env": "ANTHROPIC_API_KEY",
 "credential_present": true, "base_url": "https://api.anthropic.com",
 "reason": "auto selected 'anthropic': ANTHROPIC_API_KEY is set and it is the
            highest-priority provider with its own credential; probe of anthropic
            base URL succeeded."}
```
