# ibm-bob optimizer

IBM Bob Shell (the `bob` CLI) as the edit proposer, run non-interactively in the
candidate workdir:

    bob --accept-license --yolo --chat-mode code --hide-intermediary-output [-m <model>] "<instructions>"

- `--yolo` (a.k.a. `--approval-mode yolo`) auto-approves all actions so Bob can
  write files (the workdir is a throwaway candidate copy).
- `--accept-license` accepts the IBM license on first run (needed in fresh/CI envs).
- The positional prompt is the non-interactive one-shot form (`-p/--prompt` is
  deprecated upstream).
- **Auth:** Bob reads `BOBSHELL_API_KEY`. The runner populates it from
  `BOBSHELL_API_KEY` → `BOB_API_KEY` (env or the nearest repo `.env`).
- **Install:** `curl -fsSL https://bob.ibm.com/download/bobshell.sh | bash -s -- --package-manager npm`

## Native skills, instructions, and subagents

- **Native skills:** `.bob/skills/<name>/SKILL.md` (the Bob convention — NOT
  `.claude/skills`; not Claude-compatible). Discovered at startup, loaded once per
  conversation, activation inferred from the `description`, auto-approved under `--yolo`.
  cap-evolve copies the capability + diagnose skills there. (One source notes skills may be
  Advanced-mode only — treat as likely-but-unverified under `--chat-mode code`.)
- **Always-on instructions:** `AGENTS.md` is the canonical project memory file
  (auto-applied to new conversations; supports `@./file.md` imports to depth 5; global rules
  in `~/.bob/rules/*.md`). cap-evolve writes its pointer here — the most reliable channel
  since skills are description-triggered and possibly mode-gated.
- **Subagents / parallelism:** **No public subagent/parallelism feature** — Bob exposes
  named modes only (Code / Ask / Plan / Advanced; cap-evolve uses `--chat-mode code`).
  Treat per-cluster work as a single-agent serial pass: diagnose all clusters, then make one
  merged candidate edit that addresses them together. No git-worktree isolation.
