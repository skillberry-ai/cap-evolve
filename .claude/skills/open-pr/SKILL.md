---
name: open-pr
description: Entry point for an AI agent doing development work in cap-evolve - branch off main, commit as the right identity, pick the right testing/review track for the change (code, dashboard, or docs-only), and open the PR with the house checklist filled in. Use whenever asked to implement a change, fix a bug, or open a PR in this repo.
---

# Open a PR

The single entry point other skills assume you went through: `testing`,
`review-cycles`, `dashboard-change`, `docs-change`. Read this first for any
development task in cap-evolve, then branch into the skill(s) your change's track
needs.

## 1. Branch

Work in a worktree, not the checkout the user is sitting in (see
`superpowers:using-git-worktrees` if available, else `git worktree add`), branched
from a fresh `origin/main`:

```
git fetch origin main
git worktree add -b <type>/<short-slug> ../wt-<slug> origin/main
```

Pick `<type>` the way this repo's history does: `feat`, `fix`, `refactor`,
`chore`, `docs`, `test`.

## 2. Identity

Commit and open the PR as the user's own configured git identity — never as an AI
tool's identity, and never add a tool co-author trailer, unless the user's own
instructions (a `CLAUDE.md`, a memory, or something said this session) say
otherwise for this session. Check `git config user.name`/`user.email` match what
the user expects before your first commit.

## 3. Classify the change — pick the track

| Track | What it is | What happens before review |
|---|---|---|
| **Code** | `core/cap_evolve`, `skills/*/*/scripts`, `dashboard/backend/capevolve_dashboard`, CI, adapters, anything with logic | Run the `testing` skill: unit tier always, end-to-end real run(s) when the change plausibly affects a real run |
| **Dashboard** | `dashboard/frontend/src/**` (components, routes, styles) | Run `dashboard-change`: build, screenshot before/after, attach to the PR — no real end-to-end optimization run needed |
| **Docs-only** | `*.md`, `docs/**`, `site/**` prose, `SKILL.md` body text, comments-only diffs | Run `docs-change`: link check only, no real run |

A PR can touch more than one track (e.g. a feature with code + docs) — run every
track's prep, then one shared `review-cycles` pass over the whole diff.

If you are unsure which track a change is, read the diff's file list: anything
under `dashboard/frontend/src/` with no `core/`/`skills/`/`dashboard/backend/`
changes is dashboard-only; anything that is 100% `.md`/doc-comment is docs-only;
everything else is code.

## 4. Commit

Follow `CONTRIBUTING.md`'s house rules (honesty lives only in `core/cap_evolve`,
skills stay host-agnostic, zero runtime deps in `core`, a test for any
`core`/`skills`/`dashboard` code change). Use `git commit -s` if the repo's commits
are signed off (check `git log -5` for `Signed-off-by` trailers).

## 5. Open the PR

```
gh pr create --title "<type>: <summary>" --body "$(cat <<'EOF'
## What & why
...

## Checklist
- [ ] python -m pytest core/tests -q passes
- [ ] python skills/_registry/build_manifest.py skills is clean
- [ ] Any new/changed skill's scripts/check.py is green
- [ ] Honesty invariants untouched (gate on val, test sealed) — or explained
- [ ] Docs updated (README/skill SKILL.md) if behavior changed
EOF
)"
```

This is `.github/PULL_REQUEST_TEMPLATE.md` verbatim — fill in the checkboxes with
what you actually ran, don't just check them.

## 6. Test and review

Go run the track(s) from step 3, then `review-cycles` for 3 rounds. Do not open
the PR for review before the relevant test evidence (a real run's link/score, or
screenshots, or the link-check result) is either already in the PR description or
about to be posted as the first comment — reviewers judge against that evidence.

## 7. Finish

After the last review round reports both verdicts, hand back to the user. Do not
merge on your own unless explicitly asked to.
