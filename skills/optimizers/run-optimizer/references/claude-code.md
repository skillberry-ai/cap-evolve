# claude-code optimizer

Claude Code headless as the edit proposer.

    claude -p "<instructions>" --permission-mode acceptEdits [--model <id>]

run with `cwd=<workdir>`. `-p/--print` runs non-interactively and exits;
`--permission-mode acceptEdits` lets it write files without prompting.

- **Install:** https://docs.claude.com/claude-code
- **Auth:** a logged-in Claude Code session, or `ANTHROPIC_API_KEY`.
- **JSON / cost:** `--output-format json` makes the result a JSON object with
  `total_cost_usd`, `usage` (input/output tokens), and per-model cost under
  `modelUsage`. The runner appends this when called with `--json` and parses
  `total_cost_usd`. Add `--json-schema '<JSONSchema>'` (the runner forwards it
  when the row's json_flag contains `--output-format`) to also get
  `.structured_output` — useful for headless decision steps.
