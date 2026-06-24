# pi optimizer

The Pi coding agent (`pi`, `@earendil-works/pi-coding-agent`) as the edit proposer.

    pi -p "<instructions>" [--model <pattern>]

run with `cwd=<workdir>`. `-p`/`--print` prints the response and exits (the prompt
is positional, also accepts stdin). Pi has **no permission popups by design** — in
non-interactive mode it applies edits without confirmation, so there is no
`--yolo`/`--auto` flag to add. `--model <pattern>` selects the model (e.g.
`sonnet:high`, which implies the provider); `--provider <name>` is available if you
need to pin it. Sessions are keyed by cwd (no `--cwd`); `--mode json`/`--mode rpc`
give structured/process integration.

- **Install:** `npm install -g --ignore-scripts @earendil-works/pi-coding-agent` ·
  or `curl -fsSL https://pi.dev/install.sh | sh` (repo: https://github.com/earendil-works/pi)
- **Auth:** provider-native — `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc., or `pi /login`.
  (`PI_API_KEY` is not a thing.)
- **JSON / cost:** no documented `total_cost_usd`, so `json_flag` is blank and the
  optimizer runs prose-fed.

## Native skills, instructions, and subagents

- **Native skills:** Pi has **native skills** (`pi install git:...`; local dev `pi -e <dir>`)
  and loads them without a compatibility `Skill` tool. cap-evolve does not assume a fixed
  in-repo skills dir, so the registry leaves `skills_dir`/`instructions_file` blank and
  relies on its guaranteed channel (skills under `./guidance/` + the `./INSTRUCTIONS.md`
  pointer). If you package the capability/diagnose skills for Pi natively, point Pi at them
  per its docs.
