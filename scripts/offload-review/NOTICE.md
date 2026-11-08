# Provenance

`offload-review.sh` and `backends/{glm,bob,claude}.sh` are ported from
[rossoctl/context-guru](https://github.com/rossoctl/context-guru)'s
`.claude/skills/offload-review` (Apache License 2.0), adapted for cap-evolve:

- `OFFLOAD_MAX_ROUNDS` defaults to **3** here (was 2).
- Prompt files (`review-prompt.md`, `review-prompt-later-rounds.md`) moved to
  `.claude/skills/review-cycles/` and rewritten for this repo's house rules
  (`CLAUDE.md`, `CONTRIBUTING.md`, the honesty/host-agnostic/test-coverage
  invariants) instead of context-guru's.
- The backend mechanism (GLM via Claude Code + `apiKeyHelper`, IBM Bob Shell, the
  user's own Claude Code as fallback) is otherwise unchanged.
- `self_check.sh` is new (not in the upstream skill).
