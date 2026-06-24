# droid optimizer

Factory Droid's headless mode (`droid exec`) as the edit proposer.

    droid exec --auto low [-m <model>] "<instructions>"

run with `cwd=<workdir>`. `droid exec` is the non-interactive CI/CD subcommand;
the prompt is the positional arg (also accepts `-f/--file` or stdin). `--auto low`
permits file create/edit while blocking system changes (`medium` adds installs/
builds/local commits, `high` adds push; the default with no flag is read-only).
`--cwd <path>` exists but is unnecessary — the runner sets cwd to the candidate dir.

- **Install:** `curl -fsSL https://app.factory.ai/cli | sh` · `brew install --cask droid`
  · `npm install -g droid` (docs: https://docs.factory.ai/cli)
- **Auth:** `droid login`, or `FACTORY_API_KEY` (`export FACTORY_API_KEY=fk-...`).
- **JSON / cost:** `-o/--output-format json`; the runner appends it (best-effort
  cost parse) when called with `--json`.

## Native skills, instructions, and subagents

- **Always-on instructions:** Droid reads `AGENTS.md`, so the registry sets
  `instructions_file: AGENTS.md` and cap-evolve writes its pointer there.
- **Native skills:** left blank in the registry — Factory's plugin/skill discovery for
  `droid exec` is installed via `droid plugin` rather than a simple in-repo `SKILL.md`
  dir, so cap-evolve relies on its guaranteed channel (skills under `./guidance/` + the
  `./INSTRUCTIONS.md` pointer). Set `skills_dir` if your build documents an auto-discovered
  path.
