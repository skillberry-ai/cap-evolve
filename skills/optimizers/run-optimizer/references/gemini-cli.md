# gemini-cli optimizer

Google Gemini CLI headless as the edit proposer.

    gemini -p "<instructions>" --approval-mode=yolo [-m <model>]

run with `cwd=<workdir>`. `-p` forces non-interactive; `--approval-mode=yolo`
auto-approves actions (`--yolo` is deprecated in favor of it).

- **Install:** https://github.com/google-gemini/gemini-cli
- **Auth:** `gemini` auth flow, or `GEMINI_API_KEY`.
- **JSON / cost:** `--output-format json` emits a structured result; the runner
  parses `total_cost_usd` / `usage` from it when called with `--json` (if the
  installed version reports them — older builds omit cost, in which case the loop
  continues without a figure).

## Native skills, instructions, and subagents

- **Native skills:** `.gemini/skills/<name>/SKILL.md` (alias `.agents/skills/`, alias
  wins). cap-evolve copies the capability + diagnose skills there. Progressive disclosure:
  only name+description load at start; the model must call the `activate_skill` tool to
  load the body (auto-approved under `--approval-mode=yolo`, but the model still chooses
  to activate from the description) — so pair it with the `GEMINI.md` pointer below.
- **Always-on instructions:** `GEMINI.md` (the "memory"), hierarchical and concatenated
  into the system prompt EVERY run, no flag, no consent. This is the most reliable channel;
  cap-evolve writes its pointer here.
- **Subagents / parallelism:** native subagent system, exposed to the main agent as tools,
  each in its own context window (custom subagents: `.gemini/agents/*.md`; built-ins
  `codebase_investigator`, `generalist`, etc.). **Recursion protection: subagents cannot
  call other subagents — one level of fan-out only.** A separate git-worktree feature
  (`gemini --worktree`/`-w`, experimental) gives per-SESSION isolation, not per-subagent.
  **Use** the one-level fan-out to investigate failure clusters in parallel, then merge.
