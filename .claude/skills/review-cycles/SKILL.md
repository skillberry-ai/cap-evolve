---
name: review-cycles
description: Run 3 independent review rounds on a cap-evolve PR, using agent-tool reviewers on this machine (GLM via Claude Code, IBM Bob Shell, or the user's own Claude Code as fallback), fix the findings between rounds, and report both verdicts. Use for every PR review in this repo opened via the open-pr skill, and whenever asked to review a cap-evolve PR (yours or someone else's). Use instead of the generic code-review skill, which makes one review and doesn't know this repo's rules.
---

# Review cycles

Two reviewers review the PR in parallel, on this machine, with the user's own login
to the reviewer tool. Each posts its review on the PR. You fix the findings, push,
and run this skill again for the next round — **3 rounds total by default**.
Reviewer N in round 2+ resumes its own earlier-round session.

The reviewer tool is a backend in `scripts/offload-review/backends/<name>.sh`:

- `glm` (the default): GLM through Claude Code, pointed at an internal gateway.
- `bob`: IBM Bob Shell.
- `claude`: the user's own Claude Code, with its own login and model.

Use `--backend <name>` or `OFFLOAD_BACKEND` to pick the first one.

**Fallback.** When a reviewer's backend is not set up, or it fails before that
reviewer posts, the next backend in `OFFLOAD_FALLBACK` (default `bob claude`) runs
that reviewer. So the default order is glm, then bob, then claude.

- Each reviewer falls back on its own. One reviewer can post with glm and the other
  with bob.
- A reviewer never posts twice. The next backend runs only while no review of that
  reviewer, round and head is on the PR.
- The marker of each review names the backend that wrote it. The script's last line
  lists the backend of each reviewer. Report both to the user.
- **When a reviewer did not use the first backend, the script prints a `Note:`
  line.** The `Tried first:` lines say why, for example `glm (not set up:
  GLM_KEY_FILE is set in your shell profile but not in this session ...)`. Tell the
  user the reason before you accept the round. Do not report "not set up" as a fact
  about the machine: it is often a fact about this session.
- In round 2+, each reviewer starts with the backend that wrote its previous
  review, so it resumes that session.
- `--no-fallback` (or `OFFLOAD_FALLBACK=""`) turns it off. Use it to compare one
  backend with another, so the results do not mix.

Run this skill in the **main session**, not in a subagent. A subagent is not woken
by its own background task, so it cannot wait for the reviewers.

## When to use

- **Every PR review in this repo uses this skill**, including "review PR #<N>" for
  a PR someone else wrote.
- **Do not use the generic `code-review` skill for a PR review.** It makes one
  review, not two independent ones. It does not know this repo's rules (honesty
  invariants, host-agnostic skills, the test-alongside-code house rule). It also
  compares against the current `main`, not against the PR's base, so a branch that
  is behind `main` gets findings in files the PR does not change.
- `code-review` is still fine for a quick check of your own diff before you commit.
- **A PR by another person:** run the rounds, then report both verdicts to the
  user. Do not fix the findings (step 5) unless the user asks you to.

## Before you start

1. The PR is pushed and is not a draft. Everything is committed.
2. The backend tool works and the user is logged in.
   - For `glm`: `claude --version`, and `GLM_KEY_FILE` names the user's JSON key
     file (key, gateway URL, model id — not in this repo; never print, copy or log
     it). The backend reads the key at call time through `apiKeyHelper`, so it
     never enters the reviewer's environment. Check it is visible in this session:
     `echo "GLM_KEY_FILE ${GLM_KEY_FILE:+set}"`. A session started before the
     variable was added to the shell profile does not see it — fix it for this run
     with `GLM_KEY_FILE=<path> scripts/offload-review.sh <pr>`, or start a new
     session.
   - For `bob`: `bob --version`, and one interactive `bob` login.
   - For `claude`: `claude --version`, and the user is logged in.
     `OFFLOAD_CLAUDE_MODEL` picks the model; default is the user's own default.
   - A backend that is not set up is skipped, and the next one runs.
3. `gh auth status` works. The reviewers post with the user's `gh` login.
4. Decide the track with the `open-pr` skill first: a **code** PR gets a real
   `testing` run before review; a **dashboard** PR gets screenshots attached
   instead of a real run; a **docs-only** PR skips both and goes straight here.

**Time limit.** Each reviewer run has a wall-clock limit, `OFFLOAD_REVIEW_TIMEOUT`
seconds (default 1800, 30 minutes; `0` turns it off). A run past the limit is
stopped with all its processes, and that reviewer goes to the next backend, unless
its review is already on the PR. It is not a token limit — the reviewer keeps its
full output and thinking budget. A stopped run shows `timed out` in its
`Tried first:` line, and its `review.log` ends with `offload-review: stopped after
<N>s`.

**A failed run is never resumed.** When a run ends without posting, its saved
session is dropped. The next round starts that reviewer fresh.

## Steps

1. **Decide on live tests.** Reviewers read code only by default. A **dashboard**
   PR should already have screenshots attached by `dashboard-change` before this
   runs — reviewers judge those, not a live run. For a **code** PR, the `testing`
   skill should already have produced real run results (or explained why none were
   possible) before the first round; link them in the PR so reviewers can read the
   evidence instead of re-running anything. Only ask the user (AskUserQuestion) if
   a reviewer genuinely needs to execute something itself (e.g. local pytest) that
   isn't already captured.
2. **Start the round** with Bash, `run_in_background: true`. Make no other tool
   calls until it ends:
   ```
   scripts/offload-review.sh <pr>
   ```
3. **Read the result.** Each reviewer has 3 files in its worktree,
   `.claude/worktrees/review-pr<N>-<backend>-r<1|2|3>/`:
   - `.review.md`: the review. The reviewer writes it and posts it on the PR.
   - `review.log`: the tool's full output. The script writes it, not the reviewer.
     Read it only when something failed.
   - `.review-prompt.md`: the prompt the script gave the reviewer.

   | Exit | Meaning | What you do |
   |---|---|---|
   | 0 | Both reviews are posted. | Read both `.review.md` files. |
   | 1 | No backend posted a review for a reviewer, or the input is wrong. | Read the message. It names each backend tried and its `review.log`. Report it to the user. Stop. |
   | 2 | The round budget (3) is used. | Go to "More rounds". |
   | 3 | This head already has both reviews of its round. | You did not push since that round. Push the fixes first. If the user asks for a round on the same head, see "Same head". |

   A warning "files changed in <checkout> during the review" means a reviewer may
   have written outside its worktree. Check that checkout with `git status` before
   you go on.
4. **If both verdicts are `approve`**, check the diff for a behavior change (a
   default, a time limit, what gets cached, offloaded or shown). Tell the user the
   PR is ready to merge, naming any behavior change found. Stop.
5. **Fix the findings** in your own worktree. Check each finding first: fix the
   real ones; for one you reject, reply on the PR and say why. Commit, then push.
6. **Run step 2 again** for the next round. Each reviewer checks its own earlier
   findings. After 3 rounds, go to step 7.
7. Report both verdicts to the user. Do not start another round on your own.

## Same head

Run a round on a head that already has both reviews only when the user asks for
it — for example, the author answered a finding with a reply and proof, with no
code change.

```
scripts/offload-review.sh <pr> --same-head
```

Each reviewer resumes its own session and is told the head did not move. The round
counts toward the 3-round budget.

## More rounds

The default budget is **3 rounds**. Only the user can grant more.

1. When a reviewer still blocks after round 3, ask the user with AskUserQuestion.
   Give the facts: each open finding, your reply to it, and why one more round can
   close it.
2. Offer: one more round, or stop and let a person decide.
3. If the user grants N more rounds:
   ```
   OFFLOAD_MAX_ROUNDS=<old total + N> scripts/offload-review.sh <pr>
   ```
4. If the user says stop, the PR waits for a person. Do not ask again for that PR
   unless the user brings it up.

Do not ask for more rounds just because there are findings — fix them in the
rounds you have.

## Clean up after the PR merges

Run this when the PR is merged or closed, not before.

```
scripts/offload-review.sh <pr> --cleanup
```

It removes every reviewer worktree and the backend's sessions for them. It refuses
while the PR is still open; to clean up one you gave up on, ask the user first,
then run it with `OFFLOAD_FORCE=1`.

## Rules

- Do not edit the reviewer worktrees. They belong to the reviewers.
- Round 1 is independent: the reviewers do not read the PR conversation. From
  round 2 on, each reviewer reads all of it, so it sees your replies and the other
  reviewer's findings.
- Reply on the PR to every finding before the next round: fixed (with the commit),
  or rejected (with the reason and proof). The reviewers read these replies.
- Write PR replies in ASD-STE100 style, with `--body-file` from a quoted heredoc.

## Add a backend

Create `scripts/offload-review/backends/<name>.sh` with three functions, and the
optional ones below. Each one runs inside the reviewer's worktree:

- `backend_label`: one line for the identity table, with the tool and version.
- `backend_has_session`: exit 0 when this worktree has an earlier session to
  resume.
- `backend_run <prompt-file> <resume:0|1>`: run one review with every tool
  approved. The tool must post the review itself, as `review-prompt.md` says.
- `backend_cleanup` (optional): delete this worktree's sessions. `--cleanup` calls
  it.
- `backend_forget_session` (optional): drop the session to resume, after a run
  that posted nothing. Without it, the script calls `backend_cleanup` instead.

The tool must keep sessions per folder, or `backend_has_session` and
`backend_run` must store their own session id in the worktree, e.g.
`.review-session`.

---

Ported from [rossoctl/context-guru](https://github.com/rossoctl/context-guru)'s
`offload-review` skill (Apache-2.0), adapted for cap-evolve: 3 rounds by default
instead of 2, this repo's house rules in the review prompts, and the
context-guru-specific comment-exemption policy dropped.
