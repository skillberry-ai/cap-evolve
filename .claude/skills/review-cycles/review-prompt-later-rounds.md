# Round {{ROUND}}: find and review everything that is new

This is not your first round on this PR. Your job in this round is to review
**everything that changed since your last review**: every new commit and every new
comment. Read all of it, in full. A review that skips a commit or a comment is a
**failed review**, even when its verdict is right. If you cannot read something,
say so in the review and use `Verdict: blocking`.

## 1. Find your last review

Your last review is the newest PR review whose first line starts with
`<!-- offload-review reviewer={{REVIEWER}} `. Read its `sha=` and its
`submitted_at`:

```
gh api --paginate repos/{{REPO}}/pulls/{{PR}}/reviews \
  --jq '.[] | select(.body | startswith("<!-- offload-review reviewer={{REVIEWER}} ")) | {submitted_at, first: (.body | split("\n")[0])}'
```

Call them LAST_SHA and LAST_TIME. Do not trust your memory of this session for
them. The session can be old, or new.

## 2. Read every new commit

```
git log --stat LAST_SHA..HEAD
git diff LAST_SHA..HEAD
```

Read the whole diff. Read each changed file around the changes, not only the diff
lines.

## 3. Read the whole conversation

Save each list to a file in your folder, then read each file **in full**. Do not
use `head`, `tail`, or any other command that cuts the output. GitHub keeps these
three lists apart, and the author's replies to findings are mostly in the second
and third.

```
gh api --paginate repos/{{REPO}}/pulls/{{PR}}/reviews \
  --jq '.[] | "== review by \(.user.login) at \(.submitted_at):", .body' > .review-in-reviews.txt
gh api --paginate repos/{{REPO}}/issues/{{PR}}/comments \
  --jq '.[] | "== comment by \(.user.login) at \(.created_at):", .body' > .review-in-comments.txt
gh api --paginate repos/{{REPO}}/pulls/{{PR}}/comments \
  --jq '.[] | "== inline by \(.user.login) at \(.created_at) on \(.path):\(.line // .original_line):", .body' > .review-in-inline.txt
```

Do not use `gh pr view --comments`. It fails on this repo.

Read everything, and look hardest at the items newer than LAST_TIME. A comment from
a person (not a reviewer marker) is a request from the team. Check each one, even
when it is not about one of your findings.

## 4. Then review

- For each earlier finding (yours and the other reviewer's), say: fixed, not fixed,
  or rejected by the author. If the author rejected it with a reason, check the
  reason. Accept it when it is right. Keep the finding only if you can show the
  reason is wrong.
- Do not repeat a finding the other reviewer already raised. Write "agree with
  reviewer N, finding M" only after you checked it yourself, and add only new
  proof.
- Review every new commit as carefully as a first review. Raise a new finding on
  old code only when it is serious.
- Re-check the house rules from round 1 (honesty in `core/cap_evolve` only,
  host-agnostic skills, zero runtime deps in `core`, a test alongside any
  `core`/`skills`/`dashboard` code change) against the new commits too.

## 5. Show your work

Start "What I checked" with these lines, with real values:

```
- Last review: round R, LAST_SHA, LAST_TIME
- New commits read: N (list each short sha and title)
- Read in full: X reviews, Y comments, Z inline comments (from the three files)
- New items since my last review: list each one and what I did about it
```

If N is 0, show the `git log` command and its empty output.
