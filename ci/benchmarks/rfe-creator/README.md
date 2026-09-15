# rfe-creator

**RFE-Creator** ([`opendatahub-io/rfe-creator`](https://github.com/opendatahub-io/rfe-creator))
is Red Hat's OpenDataHub project for turning a raw feature request into a
well-formed RFE (Request For Enhancement): a Claude Code skill pipeline
(`rfe.speedrun` orchestrating `rfe.create`, `rfe.auto-fix`, `rfe.review`,
`rfe-feasibility-review`, `rfe.split`, `rfe.submit`) that drafts, scores,
auto-revises, and files the result.

This benchmark evaluates cap-evolve's ability to optimize those 7 skills
together against [`opendatahub-io/agent-eval-harness`](https://github.com/opendatahub-io/agent-eval-harness)'s
RFE-creation eval: 25 curated real-world feature-request cases, scored by a
mix of deterministic checks and two LLM judges (`rfe_quality`,
`revision_quality`) into a single weighted reward.

## Unlicensed, so nothing is vendored

Both upstream repos are **public but carry no LICENSE file** — there is no
grant to copy their code or data into this repo. So, same convention as
`spreadsheetbench/fetch_data.sh` and the `parsec` local-shadow pattern:

- **Nothing upstream is committed here.** `utils/fetch_data.sh` clones both
  repos at run time into a cache dir; the adapter reads the 25 cases and the 7
  seed skills straight from those clones, never from this repo.
- **`reward_overlay.yaml` in this directory is this repo's own original
  content** — a runner-model downgrade for CI cost plus the weighted-reward
  formula that turns the eval's judge scores into cap-evolve's scalar reward.
  `fetch_data.sh` merges it onto the upstream `eval.yaml` at run time; the
  merged file (`eval.merged.yaml`) is never committed.
- Only `<tier>/tasks.json` (ids + tags + provenance agent) is committed, same
  as every other bench here.

## Cost

This is not a cheap smoke test. A `full` run — 25 tasks x `num_trials` x
`max_iterations` — measured **$234.64 runner + $34.77 optimizer, 6.4
runner-hours** for just 3 of a 10-iteration budget. Dispatch `full`
deliberately, not routinely; `smoke` (5 tasks, calibrated for headroom from
that same run's per-task baseline rewards) is the cheap regression signal.

## Reproducing the original run

The run that established this bench's baseline->champion numbers
(0.897 -> 0.925 val reward, in-progress: 3 of 10 iterations, not sealed) lives
in the private `cap-evolve-internal` repo under
`cap-evolve-agent-eval-harness/integration/.capevolve/run_20260909_092628/`,
including its own git history (bundled) and a dashboard export. It predates
this benchmark's CI wiring and was run directly against a local checkout, not
through `run_suite.sh` — a fresh CI dispatch of `rfe-creator`/`full` is the
way to get a *sealed*, benchmark-history-published result.
