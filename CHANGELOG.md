# Changelog

All notable changes to AgentCapTune are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres to
[Semantic Versioning](https://semver.org/) (currently `0.x` — anything may change).

## [Unreleased]
### Added
- Honest-eval core (`agent_capo`): seeded splits with a sealed test set,
  significance gate, multi-trial variance, pass^k + pass@k, bootstrap CIs.
- 26 Agent Skills: phases (intake, implement-and-check, baseline, evaluate,
  diagnose, gate, finalize, report), capabilities (system-prompt, tools, mcp-tool,
  skill-package), algorithms (all-at-once, cyclic, hardest-first,
  gepa-reflective), optimizers (claude-code, codex, gemini-cli, opencode, openclaw,
  ibm-bob, generic, mock), and orchestrate.
- Git-backed iteration store (default) + optimizer memory (MEMORY.md/STATE.md/rejected.jsonl).
- Single-file `dashboard.html`; host-agnostic installer; Claude Code plugin/marketplace.
- Examples: toy_calc, json_extract, tau2_airline (real run: 0.46 → 0.80 on 50 tasks).
- `--resume` to continue a run from its current best.

### Notes
- Skill names are hyphenated to comply with the Agent Skills `[a-z0-9-]` rule.
