# PROCESS — cand_0004

## Headline finding: every prior iteration edited a file this task never loads

The decisive discovery this iteration is not about the agent's reasoning. It is that
`aap2_agent.md` — the **only** file iterations 1, 2 and 3 touched — is **never read by this
task**. The task routes to the **babylon** agent, which loads `shared_context.md` +
`babylon_agent.md`.

Verified four independent ways, not inferred:

1. **The fast-path classifier.** I extracted the compiled regexes from
   `_run/parsec-live/src/agent/agents.py` and ran them against the task's own
   `instruction.md`. `_BABYLON_PATTERNS` matches on the literal substring **`catalog item`**
   (the instruction says "read the catalog configuration for the affected item" … "how many
   catalog items are failing"). `_AAP2_PATTERNS` does **not** match. `classify_fast`
   (agents.py:256) returns `"babylon"` when babylon matches and aap2 does not — so the
   orchestrator is skipped entirely and babylon is selected deterministically.
2. **The runtime logs.** All 5 champion trials log
   `Fast-path routing to babylon agent` / `Agent prompt loaded for babylon (28164 chars,
   shared=yes)`, timestamped inside this task's own trial window.
3. **The prompt loader.** `system_prompt.py` maps `babylon` → `babylon_agent.md` and
   prepends `shared_context.md`. `aap2_agent.md` is loaded only for `agent_type == "aap2"`.
4. **Byte-identical prompts across both arms.** The champion and cand_0003 lanes both log
   28164 chars for babylon, even though cand_0003 grew `aap2_agent.md` by ~11.6 KB. The
   effective prompt delta between champion and cand_0003 was **zero bytes**.

Consequences, stated plainly:

- **cand_0003's −0.210 was not caused by its edit.** Its edit could not reach the agent. The
  3/5-vs-1/5 cutoff split is sampling variation on a step both arms fail at the same
  underlying rate (P(≥3 of 5) ≈ 0.16 at a ~30% true cutoff rate). Its rejection reason
  (`SE=0 → STRICT fallback, n=1`) is consistent with noise.
- **cand_0001's +0.095 and cand_0002's +0.017 are also not attributable to their edits**, for
  the same reason. The run's apparent 0.783 → 0.878 → 0.895 climb is, as far as the loading
  path can support, unattributable drift. This iteration is effectively the **first** edit to
  reach this task.
- The prior iterations' budget arithmetic was against the wrong agent: they reasoned about
  `max_rounds=20` (aap2) and "~10 tool calls". Babylon's real budget is
  **`max_rounds=8` model rounds** (agents.py:118), with tool calls parallel within a round.

## Ranked issues (from the real timelines of all 10 trials, champion + rejected)

All 10 trials share an identical opening: 3 job-log reads + `find_jobs` (3 failed jobs) +
`lookup_catalog_item` → `found: true` with a fetchable `path` and a `files` list. Every
scored fact lives in the one file at `path`. What happens after that decides the reward.

**1. Constructed-sibling-path fetch, ahead of the returned `path` (10/10 trials).**
The agent's first GitHub call after the lookup is a path it *built* from `directory` +
a name in `files`, not the `path` the tool returned. That 404s in 6 of 10 trials. Misread as
"wrong repo/ref", it starts the hunt — one trial then re-fetched with `ref="main"` explicitly,
and two widened to other owners (`rhpds/agnosticv`, `redhat-cop/agnosticd`).
*Class: missing knowledge (tool-contract).*

**2. `search_github_repo` used as a grep — 0-for-23 across all trials.**
`tools/github_files.py:313` substring-matches the git **tree's paths**; it never opens a
file. Every single query in every trial was a *content* string (variable name, hostname,
secret name, path fragment read out of a fetched file) and every one returned
`total_matches: 0`. The agent reads the zero as "not here, look elsewhere" and keeps hunting.
Nothing in `babylon_agent.md` said the tool is path-only — and the tool's **own description**
(`tool_definitions.py:829`) asserts "if it returns zero matches, the item does NOT exist",
which is false for a content query and actively drives the misreading.
*Class: missing knowledge (tool-contract). This is what generates the dead calls.*

**3. No budget awareness, and no warning before the cutoff (4/10 trials score 0.475).**
All four low trials end on the harness `max_rounds` stub (`agents.py:1109`) — they emit **no
report at all**, with every scored fact already in context 4–7 calls earlier.
`completion=1.0`, `tool_calls=1.0`, `answer=0.25`: 100% of the loss is the undelivered
answer. The streaming path never calls `_maybe_inject_budget_warning`, so there is no hint.
*Class: right domain, stopped too late.*

**4. Chasing artifacts the config declares unreadable.** The stage config states the secret
is ansible-vault encrypted and "cannot be inspected from here". Trials still spend rounds
fetching/searching for it. *Class: right domain, wrong action.*

**5. Sibling-item re-lookups that cannot succeed.** Two trials spend their last two rounds on
`lookup_catalog_item` for the other two affected items, taken from job titles; both return
`found: false`. The shared cause was already established from one config.
*Class: right domain, wrong action.*

**6. Rubric content not carried anywhere in babylon's prompt.** The rubric requires naming
the breadth as a number, naming the dependency *as shared*, saying the registry *answered*
(forbidding outage phrasing), and naming the credential as *stale/rotated* — and forbids
substituting SSH/bastion credentials. The passing trials get these right by luck of
reasoning; `babylon_agent.md` carried none of it.
*Class: missing knowledge.*

## Edits made (all in `babylon_agent.md` — the file this task actually loads)

Nothing went into `shared_context.md`: it is prepended to all six domain agents, and these
rules are specific to the GitHub/agnosticv config-tracing tools that only babylon and aap2
hold. Nothing went into `orchestrator.md`: the orchestrator is **skipped** for this task
(fast path), so an edit there would be inert — and the routing is correct anyway.

1. **`Catalog Item Lookup Rules` — fetch the returned `path` first, verbatim** (issue 1).
   Distinguishes `path` (verified fetchable) from `files` (a bare listing, not a fetchability
   promise), and states that a 404 on a path *you constructed* is not evidence about the
   repo, owner or ref.
2. **New section: `search_github_repo` matches FILE PATHS ONLY** (issue 2). Explicit
   never-search list (variable/parameter name, hostname/URL, secret name, error string, YAML
   key, role name, any value read inside a fetched file), what `total_matches: 0` does and
   does not mean, and a **placeholder-only** worked example showing the three wrong calls and
   the right move. It also carves this tool out of `shared_context.md`'s "0 results → broaden
   and retry" advice, which otherwise points the wrong way here.
3. **Same contract added to the tool inventory and `Tool Response Formats`** (issue 2), so it
   is present where the agent looks up tool behaviour, not only in a prose section.
4. **New section: a declared-unreadable artifact is a finding, not a to-do** (issue 4).
   Report the name + the include path, say it is not inspectable and why, do not try to open
   it. Extended to role/playbook source referenced by a failing task.
5. **New section: reading an authentication failure — refused is not unreachable** (issues 6).
   An error proving the remote end *answered* (rejected credential / `unauthorized` / `401` /
   `403`) means reachable-and-serving, fault on our side; only timeout/DNS/refused supports an
   availability claim. Plus: name the *specific* authentication that failed (an image-pull
   credential, an API token and a shell/bastion credential are different things), and the
   stale-stored-copy mechanism (correct-looking config + live rejection ⇒ rotated/expired
   elsewhere).
6. **New section: several items failing identically ⇒ find what they SHARE** (issues 5, 6).
   State the breadth as a number in prose; establish the shared cause from **one** item's
   config (sibling re-lookups add no fact and cost rounds); name the shared thing *as* shared.
7. **New section: round budget — write the report while you still can** (issue 3). The real
   numbers (≈8 rounds, parallel within a round, no warning), the stake (budget exhaustion
   delivers *nothing*), and a possession test — *"can I already answer every question the
   user actually asked?"* → if yes, stop and write. Plus the five specific things that do
   **not** earn another call.

## Verify-the-fix — replayed against the champion's failing trial (seed-2), call by call

| # | What it did | Under this edit |
|---|---|---|
| 1–5 | job logs, `find_jobs`, `lookup_catalog_item` | unchanged (fact-gathering) |
| 6 | `fetch .../common.yaml` (constructed from `files`) | **blocked** by edit 1 → fetches the returned `path` instead ⇒ **every scored fact in hand at call 6** |
| 7 | `search(ocp4_workload_common)` | **blocked** by edit 2 (role/variable name) |
| 8 | `fetch .../prod.yaml` | already done at call 6 |
| 9 | `search(registry.redhat.io)` | **blocked** by edit 2 (hostname) |
| 10 | `search(ocp4_token)` | **blocked** by edit 2 (secret name) |
| 11 | `fetch` the directory | **blocked** by edit 1 + edit 7 |
| 12–13 | `lookup` two sibling items | **blocked** by edit 6 (establish from one config) |

The possession test in edit 7 completes at call 6 — the config names the credential, names
its include path, says it is encrypted, and says it was rotated externally; `find_jobs`
gave the count; the job log gave the rejected-credential error. So the report is written
around round 4–5 instead of never. `answer` 0.25 → 1.0.

Same replay holds for the three cand_0003 cutoffs: each reaches the stage config at call
7–11 and then spends its remaining rounds exclusively on calls this edit blocks.

## Regression safety

- **`search_github_repo` has never returned a match on this task**: 23 calls across all 10
  trials, 23 × `total_matches: 0`. Forbidding content-searches therefore cannot remove a fact
  from any report — no passing report contains anything sourced from that tool.
- **All four passing trials end with 2–3 consecutive dead searches immediately before their
  report.** The edit deletes exactly those, leaving the report intact and buying 2–3 rounds
  of headroom.
- **The `path`-first rule costs nothing.** In the 4 trials where the constructed sibling
  *did* resolve, it contributed no scored fact — all five rubric facts come from the file at
  `path`. The rule reorders rather than removes, and permits a second config fetch when a
  question the user asked is still unanswered.
- **Edits 4–6 are additive content**, latent in the trials that already report correctly, so
  they cannot regress a passing trial. They also align with both rubric `forbidden` groups
  (outage phrasing; SSH/bastion substitution) which the passing reports already avoid.
- The possession test can only make a trial report **sooner** than it already did, and only
  once it can answer everything asked.

## Non-overfitting check

`git diff | grep` over the added lines finds **zero** occurrences of any task-specific
literal — no item name, credential name, registry hostname, repo name, controller name,
job id, or count. Every rule is stated over placeholders and roles (`<secret_var>`,
"a stage config", "N unrelated items"). Each restates without a task-specific noun:
*fetch the verified path before a constructed one*; *a path-matching tool cannot find file
contents*; *an error proving the service answered is not an outage*; *identical failures
across unrelated items point at what they share*; *write the report before the round budget
ends*. The count rule says "give the digit the enumerating result returned", never a value.

## Escalations (real findings, out of scope for a system-prompt-only phase)

1. **`search_github_repo`'s own tool description is wrong and harmful.**
   `tool_definitions.py:829` tells the model "if it returns zero matches, the item does NOT
   exist — do NOT fall back to other methods." For a content query against a path-only
   matcher that is false, and it is the proximate cause of issue 2. Edit 2 exists to
   counteract the tool's own text; fixing the description is the durable fix.
2. **`lookup_catalog_item`'s `files` list is not a fetchability promise.** It lists directory
   contents, but entries constructed from it 404 at the returned ref while `path` succeeds.
   This starts the dead-end hunt in 10/10 trials. Durable fix: return only fetchable paths,
   or mark which are.
3. **The budget warning is dead code on this path.** `_maybe_inject_budget_warning` fires at
   `remaining == 2` computed off `max_rounds`, and the streaming path never calls it — there
   are 0 occurrences of "rounds remaining" in any trial. Babylon gets 8 rounds with no
   warning. Injecting a real warning at round 6 would likely resolve this flakiness with no
   prompt change at all.
4. **Budget-exhaustion output is scored as an answer.** On cutoff the harness emits a stub
   ("I've used all my planned tool calls…" + a `{{choices}}` block) which is graded, yielding
   `completion=1.0, tool_calls=1.0, answer=0.25`. A trial that delivered nothing scores 0.475.
   Flushing a best-effort report on exhaustion, or scoring exhaustion distinctly, would both
   be more honest and remove most of this task's variance.
5. **The capability's edit surface does not match its load surface.** The optimizer is
   handed 8 editable files with no machine-readable statement of which ones the task under
   optimization actually loads. Three iterations and ~$20 were spent editing a file this
   task never reads. See `FRAMEWORK_IMPROVEMENTS.md`.

## Process / features used

Two parallel read-only subagents (one per trajectory group: champion and rejected). The
rejected-arm agent surfaced the routing discovery; I then re-derived it independently from
the classifier source, the prompt loader, and the trial-window runtime logs before acting on
it, rather than trusting the report. I did **not** use edit-subagents or worktrees: once the
root cause turned out to be a single file that had never been edited, fanning out editors
would have added merge risk for no coverage. I reconstructed the per-call timelines
(tool, arguments, useful-vs-dead, where the report was emitted) for all 10 trials directly
from `agent/agent.jsonl` — that table is what made every claim above checkable.

## What to preserve

The `path`-first rule and the path-only tool contract (edits 1–3) are the load-bearing ones:
they remove the calls that cause the cutoff. Edit 7's possession test is the backstop. Keep
all of them in **`babylon_agent.md`** — moving any of it to `aap2_agent.md` makes it
invisible to this task, which is the mistake this iteration exists to correct.

## What I skipped

- No `orchestrator.md` edit: the fast path skips the orchestrator entirely here, so it would
  be inert; routing is also correct in 10/10 trials.
- No `shared_context.md` edit: these rules are not domain-general, and it is prepended to all
  six agents.
- I did not revert cand_0001/0002's `aap2_agent.md` content. It is unreachable from this task
  and therefore cannot affect the gate; reverting it would add diff noise and might harm other
  tasks in a wider run. Flagged here so a future iteration knows it is unvalidated by this
  run's numbers.
