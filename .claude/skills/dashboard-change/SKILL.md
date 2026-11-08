---
name: dashboard-change
description: Prepare a cap-evolve dashboard (dashboard/frontend) PR for review by attaching before/after screenshots instead of a real end-to-end optimization run. Use for any change under dashboard/frontend/src/** - components, routes, styles, new tabs/panels. Not for backend (dashboard/backend) or core logic changes, which need the testing skill's real-run tier.
---

# Dashboard change

A dashboard-only change doesn't need a real optimization run to review — it needs
to be **seen**. This skill gets screenshots of the changed UI (light + dark, before
and after) into the PR so reviewers can judge it without running anything.

## 1. Build

```bash
cd dashboard/frontend && npm ci && npm run build && npm test
```

`dist/` is committed — if it changed, it's part of the diff. CI fails on a stale
`dist/`.

## 2. Get before/after screenshots

**Preferred: Playwright MCP**, if connected in this session. Serve the dashboard
locally, navigate to each changed tab/route, and capture a screenshot at
1920x1080 in both `data-theme="light"` and the default (dark) — the theme tokens
in `src/index.css` (`--primary`, `--accepted`, `--rejected`, …) must render
correctly in both.

**Fallback: the repo's own screenshot tool**, no MCP needed:

```bash
# serve the committed static export (fixture data, works offline)
python3 scripts/tools/shoot_dashboard.py --out /tmp/dash-after

# or point it at a live dev server for a specific run
cap-evolve dashboard --base <some run dir> --port 7878 --no-open &
python3 scripts/tools/shoot_dashboard.py --live http://127.0.0.1:7878 --run <run-name> --out /tmp/dash-after
```

It captures every tab the UI actually renders (the tab set comes from
`buildTabs()` in `src/routes/RunDeepDive.tsx`), one PNG per tab, dark and at full
content height by default. Run it once on the branch **before** your change
(`git stash` or a sibling worktree on `main`) into `/tmp/dash-before`, and once
after, so the PR shows a real diff, not just the new state.

Only screenshot tabs your change actually touches, plus one overview tab — don't
flood the PR with every tab if only one panel changed.

## 3. Attach to the PR

Push the PNGs to an orphan assets branch (keeps the main history free of binary
diffs) and link them from a PR comment:

```bash
pr=<N>
git worktree add --orphan -b pr-assets/pr-$pr ../wt-pr-assets-$pr
cp /tmp/dash-before/*.png /tmp/dash-after/*.png ../wt-pr-assets-$pr/
git -C ../wt-pr-assets-$pr add -A
git -C ../wt-pr-assets-$pr commit -s -m "screenshots for PR #$pr"
git -C ../wt-pr-assets-$pr push -u origin pr-assets/pr-$pr

repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
{
  echo "## Dashboard screenshots"
  for f in /tmp/dash-after/*.png; do
    name=$(basename "$f")
    echo "### $name"
    echo "![${name}](https://raw.githubusercontent.com/$repo/pr-assets/pr-$pr/$name)"
  done
} > /tmp/pr-$pr-screenshots.md
gh pr comment "$pr" --body-file "/tmp/pr-$pr-screenshots.md"
```

If Playwright MCP produced the screenshots directly into a running session that
can attach images to the PR comment natively, use that path instead of the
orphan-branch upload — same end result, fewer steps.

## 4. No real end-to-end run needed

Don't dispatch `benchmarks.yml`/`integration-tests.yml` for a dashboard-only
change — the screenshots are the evidence. Move straight to `review-cycles` once
they're attached.

If the change also touches `dashboard/backend/` or `reduce_run`'s output shape,
that's a **code** change too — run `testing`'s unit tier (and the backend's own
tests) before review, in addition to the screenshots.
