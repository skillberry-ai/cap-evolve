# cap-evolve — notes for Claude Code sessions

cap-evolve optimizes an agent capability (prompt/skill/tools) against a benchmark,
honestly: gate on val, seal test. `core/cap_evolve` is the loop; `skills/` are
self-contained capabilities/algorithms/optimizers; `benchmarks/` holds the
adapters; `dashboard/` is the FastAPI backend + React frontend.

## Developing here — use the skills

Every development task in this repo starts with `.claude/skills/open-pr`, which
routes to the rest by the change's track:

| Skill | When |
|---|---|
| `open-pr` | Start here for any implement/fix/PR task — branches, identity, picks the track below |
| `testing` | Any code change (`core/cap_evolve`, `skills/*/*/scripts`, `dashboard/backend`, adapters, CI) — unit tier always, real end-to-end run when the change can affect one |
| `dashboard-change` | `dashboard/frontend/src/**` only — build + before/after screenshots, no real run |
| `docs-change` | Docs-only diffs — link check only |
| `review-cycles` | 3 rounds of two independent reviewers (GLM/Bob/Claude), after the relevant skill above has produced its evidence |

## DCO: every commit must be signed off

This repo's CI runs a DCO check (`probot/dco`) that fails a PR whose commits lack
a `Signed-off-by` trailer. Always commit with `git commit -s` (or `--amend -s` to
fix a commit made without it) — never open or push a PR with an unsigned commit.
If a PR's DCO check is already failing, fix it by rebasing with
`git rebase --exec 'git commit --amend --no-edit -s' <base>` and force-pushing,
rather than leaving it for a human to notice.

## Benchmark CI: which model provider to use

Benchmark runs reach models through three IBM providers, in this order: **RITS**
(`ibm-rits/…`, no budget) → **ETE-INT** (`ibm-ete-int/…`, the team's main
gateway) → **ETE** (`ibm-ete/…`, a second gateway with its own budget, only when
ETE-INT can't serve the model or is over budget). Pick a **plain model name**
when dispatching `benchmarks.yml`/`integration-tests.yml` and CI applies this
order itself. Full detail, the model catalog, and how to read which provider
actually served a run: the `testing` skill, and `ci/benchmarks/README.md`
("Model providers and their order").
