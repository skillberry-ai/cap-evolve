# cursor optimizer

Cursor's headless agent CLI (`cursor-agent`, NOT the IDE) as the edit proposer.

    cursor-agent -p "<instructions>" --force [--model <model>]

run with `cwd=<workdir>`. `-p`/`--print` runs non-interactively and exits;
`--force` (alias `--yolo`) auto-approves edits and shell unless explicitly denied.
`--workspace <path>` is available but unnecessary here — the runner already sets
cwd to the candidate dir, so relative edits land there.

- **Install:** `curl https://cursor.com/install -fsS | bash`
  (docs: https://cursor.com/docs/cli)
- **Auth:** `cursor-agent login`, or `CURSOR_API_KEY` (`--api-key` also accepted).
- **JSON / cost:** `--output-format json` emits a structured result; the runner
  appends it (and best-effort parses `total_cost_usd`/`usage`) when called with
  `--json`. If the installed version omits cost, the loop continues without a figure.

## Native skills, instructions, and subagents

- **Always-on instructions:** Cursor reads `AGENTS.md` at the workspace root, so the
  registry sets `instructions_file: AGENTS.md` and cap-evolve writes its pointer there
  (to `./INSTRUCTIONS.md`, the native skills dir, `./guidance/`, `./MEMORY.md`/`./STATE.md`).
- **Native skills:** `skills_dir: .cursor/skills` is set on the optimistic, install.sh-aligned
  assumption that `cursor-agent` discovers `SKILL.md` packages there. This is **not strongly
  documented** for the headless CLI — verify against your installed build; cap-evolve's
  guaranteed channel (skills under `./guidance/` + the `./INSTRUCTIONS.md` pointer) works
  regardless.
