# kimi optimizer

Moonshot AI's Kimi coding CLI (`kimi`, the Node-based `kimi-code`) as the edit
proposer.

    kimi -p "<instructions>" [-m <model>]

run with `cwd=<workdir>`. `-p`/`--prompt <prompt>` runs a single prompt
non-interactively, streams to stdout, and does not open the TUI; under `-p` tool
calls run on the auto permission policy (no human approval), so **`-p` cannot be
combined with `--yolo`/`--auto`/`--plan`** — it already auto-approves. Working
directory is the cwd (no documented `--cwd`).

- **Install:** `curl -fsSL https://code.kimi.com/kimi-code/install.sh | bash` ·
  `brew install kimi-code` (repo: https://github.com/MoonshotAI/kimi-code).
  Note: the older Python `MoonshotAI/kimi-cli` is being wound down in favor of `kimi-code`.
- **Auth:** `kimi login` (Kimi OAuth or a Moonshot API key) is the safe path.
  ⚠️ A model-auth env var (`MOONSHOT_API_KEY`/`KIMI_API_KEY`) is listed in the
  registry as a convenience but is **unverified** against current docs — prefer
  `kimi login` for unattended runs until confirmed.
- **JSON / cost:** `--output-format text|stream-json` exists (only with `-p`), but no
  documented `total_cost_usd`, so `json_flag` is blank and the optimizer runs prose-fed.

## Native skills, instructions, and subagents

- **Always-on instructions:** the registry sets `instructions_file: AGENTS.md`; cap-evolve
  writes its pointer there.
- **Native skills:** left blank — Kimi installs plugins via `/plugins`, not a simple
  in-repo `SKILL.md` dir, so cap-evolve relies on its guaranteed channel (skills under
  `./guidance/` + the `./INSTRUCTIONS.md` pointer).
