---
name: docs-change
description: Prepare a docs-only cap-evolve PR for review - no real run, no screenshots, just a local link check before going straight to review-cycles. Use when every changed file is a .md doc, site/**/*.html prose, a SKILL.md body, or comments-only. If any code, adapter, or dashboard-frontend file changed too, use testing or dashboard-change for those files instead.
---

# Docs change

Pure documentation changes skip both real runs and screenshots — the only thing
to verify is that nothing broke.

## 1. Confirm the change really is docs-only

Check the diff's file list: `*.md`, `docs/**`, `site/**` prose, `.github/**.md`,
or a `SKILL.md`/`CLAUDE.md` body — and nothing under `core/`, `skills/*/*/scripts`,
`dashboard/`, `ci/benchmarks/lib/`, or any benchmark adapter code. If anything else
changed, route that part through `testing` or `dashboard-change` and only use this
skill for the doc-only portion.

## 2. Link check (the only check that matters here)

Same command CI's `docs-links` job runs:

```bash
lychee --offline --no-progress --include-fragments \
  --exclude-path benchmarks/tau2/examples/airline/run_full \
  --exclude-path benchmarks/skillsbench/examples/shared_skills/run_full \
  "README.md" "docs/**/*.md" "benchmarks/**/*.md" "*.md"
```

(Pre-#959 path layout: `--exclude-path examples/tau2_airline/run_full --exclude-path
examples/skillsbench/run_full` and `"examples/**/*.md"` instead of
`"benchmarks/**/*.md"` — check `ci.yml`'s current args if unsure.)

Zero errors required. A relative link that moved (renamed file, moved directory)
is the most common failure — fix the link, don't exclude the path.

If the change touched `CONTRIBUTING.md`, `README.md`, or any `SKILL.md`'s
documented command, also spot-check that the command still exists:
`grep` it against `core/cap_evolve/cli.py`'s subcommand list, or just run it.

## 3. No real run, no screenshots

Don't dispatch a benchmark workflow and don't take dashboard screenshots for a
docs-only change — there's no behavior to demonstrate. Go straight to
`review-cycles`.
