# Installation

cap-evolve has one small required install (the honest-eval core) and a few optional
add-ons depending on how you want to drive it. Requires **Python 3.10+** and **git**.

```bash
git clone https://github.com/skillberry-ai/cap-evolve.git
cd cap-evolve
python3.11 -m venv .venv && source .venv/bin/activate   # recommended: isolated env (pin a specific 3.10+ interpreter)
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
