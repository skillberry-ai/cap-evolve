# antigravity optimizer

Google Antigravity's agent CLI (`agy`) as the edit proposer. Antigravity ships a
full GUI/IDE *and* a CLI that share one agent engine; the CLI has a real headless
print mode. Two facts make a fixed command unsafe to ship, so this row is a
**configurable wrapper** (like `openclaw`): you set the full command via env.

```bash
# best-guess for current builds — verify with `agy --help` before relying on it:
export CAPEVOLVE_ANTIGRAVITY_CMD='agy -p {prompt_text} --model <id>'
```

The `{workdir}`, `{prompt}`, `{prompt_text}`, and `{model}` placeholders are
substituted into whatever you set; the command runs with `cwd=<workdir>`.

- **Install:** `curl -fsSL https://antigravity.google/cli/install.sh | bash`
  (docs: https://antigravity.google/docs/cli-overview)
- **Auth — the catch:** Antigravity authenticates via **Google Sign-In / OS keyring**.
  There is **no documented CI-usable API-key env var**, so fully-unattended runs are not
  guaranteed; sign in interactively first (`agy` will print an auth URL over SSH).
- **Auto-approve — the second catch:** `agy -p` is genuinely headless and a
  `proceed-in-sandbox` permission mode auto-approves commands inside the sandbox, but the
  exact non-interactive flag/value to *set* that mode (and any `--cwd`) is not spelled out
  in the public docs. Confirm against your installed build and bake the right flags into
  `CAPEVOLVE_ANTIGRAVITY_CMD`.

## Native skills, instructions, and subagents

Antigravity supports plugins (`agy plugin install <repo>`). The registry leaves
`skills_dir`/`instructions_file` blank pending verification, so cap-evolve relies on its
guaranteed channel: the capability + diagnose skills under `./guidance/` plus an explicit
pointer in the `./INSTRUCTIONS.md` prompt.
