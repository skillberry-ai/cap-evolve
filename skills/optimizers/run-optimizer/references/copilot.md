# copilot optimizer

GitHub Copilot CLI — the standalone `copilot` (2025) — as the edit proposer.

    copilot -p "<instructions>" --allow-all-tools [--model <model>]

run with `cwd=<workdir>`. `-p`/`--prompt` runs a single prompt and exits;
`--allow-all-tools` auto-approves all tools (scope it instead with
`--allow-tool='write'` for edits, `--deny-tool` takes precedence). The working
directory is the cwd (no documented `--cwd`); `--cloud` would run cloud-hosted.

**Use the standalone `copilot`, not the old `gh copilot` extension** — the latter
only suggests/explains shell commands and cannot edit files.

- **Install:** `npm install -g @github/copilot`
  (docs: https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli)
- **Auth (precedence):** `copilot /login`, or `COPILOT_GITHUB_TOKEN` → `GH_TOKEN` →
  `GITHUB_TOKEN` (a fine-grained PAT with the "Copilot Requests" permission).
- **JSON / cost:** no structured cost output documented, so `json_flag` is blank;
  the optimizer runs prose-fed.

## Native skills, instructions, and subagents

- **Always-on instructions:** the registry sets `instructions_file: AGENTS.md`
  (Copilot CLI honors `AGENTS.md`; it also reads `.github/copilot-instructions.md`).
  cap-evolve writes its pointer into `AGENTS.md`.
- **Native skills:** left blank — Copilot's plugin install (`copilot plugin ...`) is not a
  simple in-repo `SKILL.md` dir, so cap-evolve relies on its guaranteed channel (skills
  under `./guidance/` + the `./INSTRUCTIONS.md` pointer).
