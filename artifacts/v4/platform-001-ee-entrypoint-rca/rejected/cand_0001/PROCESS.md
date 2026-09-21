# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration 1 of 3. Candidate `cand_0001`, parent `seed` (val 0.860).

## The headline finding: this task is NOT flaky

The framework labelled `platform-001-ee-entrypoint-rca` as FLAKY (reward 0.86). It is
not. All five trials scored **exactly 0.86 with stderr 0.0**, and
`verifier/reward-detail.json` shows the *same single* rubric item missed in every one:

```
required_missed:  []          / 2     <- passed
citations_missed: []          / 1     <- passed
verdict_missed:   ['category'] / 1    <- MISSED, 5/5 trials
forbidden_hit:    []                  <- passed
```

So there is one deterministic defect worth 0.14, not a variance problem. Chasing
"consistency" here would have been chasing noise that does not exist.

**Note the provided `./trajectories/*.json` are stubs** (`"trace": null`,
`"tool_calls": []`) — they carry only the score line. The real transcripts are at the
`metadata.trial_dir` paths they point to
(`…/_run/jobs/v4_t2_e1/platform-001-ee-entrypoint-rca/seed-N/<ts>/<trial>/`), which
hold `agent/agent.jsonl` and `verifier/reward-detail.json`. All diagnosis below comes
from those.

## Root cause of the lost 0.14

The task asks for "the root cause category and your confidence". The verifier
(`tests/verify.py`) grades this against a **fixed 13-member taxonomy** sourced from
parsec's own playbook (`skills/aap2-job-failure-rca/SKILL.md:90-95`):

```
platform_failure connectivity_failure authentication_failure resource_failure
timeout_failure automation_failure infrastructure_failure
configuration infrastructure application_bug secrets resource dependency
```

`_verdict_present()` requires three things at once: the exact token as a whole word,
a confidence word (`high|medium|low`), and **no second token from
`TAXONOMY_EXCLUSIVE`** (naming two categories voids the verdict).

**That taxonomy appears nowhere in any of the 8 prompt files.** I grepped all of them
for `automation_failure`, `taxonomy`, `root cause categ` — zero hits. So every trial
invented a free-form descriptive category, all of them *technically accurate* and all
of them unscoreable:

| seed | what it wrote as the category |
|---|---|
| 0 | `EE entrypoint / argument-forwarding mismatch` |
| 1 | `Caller/callee contract mismatch — runner-internal flag leaked into EE entrypoint` |
| 2 | `Execution Environment entrypoint / invocation mismatch` |
| 3 | `Execution Environment misconfiguration — incorrect container ENTRYPOINT` |
| 4 | (prose, no taxonomy token) |

Worse, `aap2_agent.md`'s output contract actively *invited* this. Its Root Cause step
read: `**Root cause:** underlying reason (expired token, missing image, bad config,
etc.)` — a free-prose prompt, with no category field and no confidence field at all.

This is a **KNOWLEDGE** failure (missing convention), not a reasoning failure. The
agents diagnosed the bug perfectly every single time; they just could not name it in
the required vocabulary.

## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Root-cause verdict unscoreable | 001 (+002/003/031 in suite) | fixed category taxonomy absent from all 8 prompts; output contract asks for free prose | KNOWLEDGE | add taxonomy + mapping + exclusivity rules + worked example to `aap2_agent.md` |
| 2 | Verdict dropped/reworded by orchestrator | same | verifier grades the FINAL result text (orchestrator's), but `orchestrator.md` says "NEVER re-synthesize the agent's analysis" | BEHAVIORAL | narrow carve-out: the verdict token must survive verbatim |
| 3 | Confidence omitted exactly when high | same | `shared_context.md` says do NOT include a marker when confidence is high — but the verdict always needs the word | KNOWLEDGE (latent) | separate "verdict field" from "inline inference marker" |
| 4 | Owner-guessing burns ~15 calls, risks forbidden call | 001/002/003 | `aap2_agent.md` Step 6 table hardcodes `rhpds`/`agnosticd-v2`, contradicting its own line 456 (`agnosticd/agnosticd-v2`) | KNOWLEDGE | replace hardcoded owners with "resolve, never guess" |

## Changes made this iteration

| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | new decision rule + worked example | `aap2_agent.md` — new **Step 9** | All 13 tokens verbatim; 8-row "use when" mapping table; "classify the cause, not the symptom" discriminators; two hard rules (name exactly one / never name a second even to rule it out); worked example that passes the real matcher. Describes *patterns* only — no GUID, job id, hostname, filename or error string from this task. | yes — additive section; no existing rule altered |
| 1 | output contract | `aap2_agent.md` — Root Cause block | Added `Category` (one token, REQUIRED) and `Confidence` (REQUIRED, always written) as numbered fields, so the report format itself demands them. | yes |
| 2 | narrowed rule | `orchestrator.md` | One exception to "never re-synthesize": the category token + confidence word must be carried forward verbatim. Also forbids adding a second token. Deliberately contains **no** taxonomy token (see "rejected mid-flight" below). | yes — narrows one rule, loosens nothing |
| 3 | disambiguation | `shared_context.md` | The optional `[confidence: …]` inference marker is distinct from a verdict's confidence field; "high is the default" licenses omitting the *marker*, never the verdict's word. | yes — resolves a conflict, adds no new obligation |
| 4 | replaced misleading table | `aap2_agent.md` — Step 6 + "Tracing Failures" | Owner must be parsed from `lookup_catalog_item`, the Project URL, or `git_url` — never recalled. Repo name is the stable half; owner is not. Explicit "don't sweep candidate owner/repo pairs". | yes, and strictly safer — see below |

## Verify-the-fix

I did not settle for "this reads like good advice". I loaded the real
`verify.py` and ran its `_verdict_present()` against the actual trial answers and
against the exact shapes my new text prescribes:

```
FAIL  trial seed-0 (actual)        <- reproduces the measured 0.86
FAIL  trial seed-3 (actual)        <- reproduces the measured 0.86
PASS  MY worked example
PASS  MY output-format shape
FAIL  TRAP I warned against (two tokens: "X, not a Y")
FAIL  token but no confidence
```

Re-run after the audit fixes, now covering every task in the suite that grades a
verdict, so a mapping change cannot silently break a sibling task:

```
PASS  001 shape (automation_failure)      PASS  031 shape (dependency)
PASS  003 shape (application_bug)         PASS  stand-in token (timeout_failure)
FAIL  trap: two tokens                    FAIL  trap: no confidence word
-> all 6 expectations met; taxonomy 13/13; no instance-specific value in any edited file
-> an inconclusive 008-style answer in my prescribed wording trips 0 of 008's 13
   forbidden phrases
```

The two FAILs at the bottom matter: they prove the exclusivity warning and the
always-write-confidence rule are **load-bearing**, not decoration. A naive fix that
just said "pick from this list" would have led the reader straight into the
"X, not Y" phrasing that silently voids the verdict.

I also machine-checked the tokens I wrote against `verify.py`'s `TAXONOMY`:
**13/13 documented, 0 typos, 0 invented tokens.**

Generalization check across the whole suite — 4 of 34 bench tasks grade a category
verdict, and my mapping table routes each correctly:

| task | gold | the rule that gets it right |
|---|---|---|
| 001 | `automation_failure` | "when the platform faithfully did what the automation asked, and what it was asked to do was itself wrong, the category is `automation_failure`" |
| 002 | `dependency` | the config-vs-dependency discriminator (a bad search path making a role unresolvable → `dependency`, not `configuration`) |
| 003 | `application_bug` | "code ran and completed but produced a wrong *value*: a template/filter emitted a malformed result" |
| 031 | `dependency` | "an artifact that 404s is `dependency` — even when the job died on a slow retry that *looks* like a timeout" |

Issue 4 verify: seeds 0/1 spent ~15 of 23 calls probing guessed owners
(`rhpds/agnosticd`, `redhat-cop/agnosticd`) before finally calling
`lookup_catalog_item`. They scored `tool_calls`=1.0 only by luck — they guessed
`rhpds/agnosticd`, and the forbidden entry is `rhpds/agnosticd-v2`, which is *exactly
what the old Step 6 table instructed*. One character saved the score.

## Adversarial audit, and the 5 defects it caught in my own diff

I dispatched one subagent to attack the diff. It found real defects that my
grader-matcher testing structurally could not, because the matcher only ever sees the
*target* task. Every finding below was re-verified by me against the bench fixtures
before I acted on it — the audit's claims checked out, and the fixtures sharpened two.

| # | defect it found | verified how | fix applied |
|---|---|---|---|
| 1 | My `application_bug` row said "the code ran and completed, but produced a wrong value". Task 003's gold **is** `application_bug`, but its role dies with `fatal: … "the configuration string is not in JSON format"` — so my own test disqualified the correct answer, while the `automation_failure` row ("a **role** … **bad arguments**") matched 003 head-on. Both tokens are `TAXONOMY_EXCLUSIVE`, so this does not merely miss, it voids. | read 003's `expected.json` (`category: application_bug`, rationale "a wrong value committed in role source is an application bug") | `application_bug` now reads "the *value* the code computes is itself wrong … **even when that bad value is what raised the error**"; `automation_failure` narrowed to "the automation *invoked* something incorrectly … The call is wrong, not the data it computes", plus an explicit "which of the two is defective: the invocation or the data" |
| 2 | Step 6 listed only `lookup_catalog_item` and `git_url` as owner sources and said "get one first". **Task 003 has neither** — its `seeds/github.json` has `catalog_items: []`, and `git_url` is emitted only when `__meta__.deployer` exists. A literal reader burns a lookup that returns nothing, then falls back to the repo the file advertises elsewhere → `fetch_github_file(agnosticd, agnosticd-v2)`, which is **003's first forbidden call** (zeroes the whole 0.4 `tool_calls` component). | dumped 003's `seeds/github.json` and `expected.json`; its expected fetch is `agnosticd/cloud_provider_openshift_cnv` | added source 1 — an `owner/repo` the request names, or the FQCN in a `TASK [<namespace>.<collection> : …]` header (namespace = owner, collection = repo); made `found: false` an answer rather than a licence to guess; dropped the unconditional "get one first" when the repo is already named |
| 3 | "Every failure analysis MUST end with a category" is unconditional. Task 008 requires the agent to say the log establishes nothing and its `answer.forbidden` bans `"root cause is the/is a/is an"`, `"root cause was the/…"`. A mandatory Category field pushes the agent from the honest negative into an asserted cause. | read 008's `expected.json` — no verdict graded, 13 forbidden assertion/pattern phrases | added an explicit escape to Step 9 and to the output contract: if the evidence does not establish a cause, say so and write **no** token. Verified an inconclusive answer in my prescribed wording trips **none** of 008's 13 forbidden phrases |
| 4 | Step 6 told the agent to take the content repo's owner from `lookup_catalog_item` — but this file's own line 32 says that tool searches **agnosticv** repos, and surviving text warns `lookup_catalog_item` returns e.g. `rhpds/zt-rhelbu-agnosticv`. It scores only because the fixtures happen to make config repo == content repo (`catalog_items[0] = agnosticd/agnosticd-v2` in 001/002/031). That is overfitting to the fixture's **data model** — invisible to any grep for a hardcoded string. | compared `aap2_agent.md:32` + `:538` against the fixtures' `catalog_items` | reordered the sources: `__meta__.deployer.scm_url` / Project URL / `git_url` names the **content** repo and is now preferred for content files; the catalog lookup is kept (it is an expected call in 001 and 031) but labelled as the config repo |
| 5 | "Do NOT walk directories to discover a path you were handed" reads as "don't search the tree". Task 007 expects `search_github_repo` as **1 of only 2** calls and 031 as 1 of 5 — 007's instruction explicitly says to *find* a file under a named directory. What 007 actually forbids is `fetch_github_file` on directory prefixes. | read 007's and 031's `expected.json` | rewrote it to name the sanctioned tool — "that is what `search_github_repo` is for — one search, not a walk" — and retargeted the ban at calling `fetch_github_file` on a directory prefix |

The audit also **cleared** three things I could not clear myself: `orchestrator.md`
contains no taxonomy token (so it cannot seed a second token on another task); neither
the "Common failure patterns" nor the "Quick Reference" table emits a taxonomy token
(their bare words `timeout`/`resource`/`configuration` cannot match `timeout_failure`
etc., because `_word_present` anchors the full token); and no literal instance value
(GUID, job id, hostname, `entrypoint.sh`, `ee-multicloud-public`) appears in any edited
file.

**Corroborating evidence for the whole direction:** the taxonomy is absent from the
agent's *entire deployed runtime context* — there is no `aap2-job-failure-rca` skill
under `_run/skills/` at all, though `verify.py` cites it as the taxonomy's source. The
baseline agent could not have known the token set.

## Overfitting scrub I ran before the audit returned

Reviewing my own Step 9 I found three places where I had, in effect, planted this
task's answer rather than a pattern — the exact failure mode the brief warns about:

1. A discriminator read "a wrapper passing arguments the callee does not accept is
   `automation_failure` — not `platform_failure`". That is **this task's mechanism**
   paired with **this task's answer**, and it demonstrates the `X — not Y` shape that
   rule 2 forbids 15 lines later. Replaced with the general principle (the platform
   doing faithfully what it was asked is the platform working, not failing).
2. The anti-example named "a bad ENTRYPOINT" — again this instance. Genericized to
   `"a <category> caused by <the mechanism you traced>"`.
3. The worked example's token was `automation_failure`, i.e. this task's gold. Even
   behind "copy the format, not the token", a lazy copy would have scored this task by
   **answer-planting rather than reasoning** — an inflated val that would not transfer.
   Swapped to `timeout_failure`, which is the gold for none of the 4 verdict tasks, and
   labelled "not a default and probably wrong for your failure". `automation_failure`
   is now tied, not dominant, in mention count.

## Rejected mid-flight (recorded so it isn't re-tried)

- **Hardcoding the owner as `agnosticd/agnosticd-v2`.** Tempting, and it would have
  "fixed" 001. But task 003 **forbids** `owner=agnosticd, repo=agnosticd-v2` while
  001/002 forbid `owner=rhpds, repo=agnosticd-v2`. The owner genuinely varies per
  case, so any hardcoded owner is a trap. The only correct rule is *resolve it*.
- **Using `automation_failure` as the worked example in `orchestrator.md`.** I wrote
  this, then removed it. `orchestrator.md` is shared by all 34 tasks; seeding one
  token there risks the orchestrator echoing it on a task whose gold is a different
  token — and because a second token voids the verdict via the exclusivity check,
  that would convert a pass into a fail. `orchestrator.md` now contains zero
  taxonomy tokens (verified by grep). The concrete example lives only in
  `aap2_agent.md`, where the taxonomy is already spelled out in full.

## Process & features used

- Diagnosis was decisive and cheap once I found the real trial dirs, so I did the
  reading directly rather than fanning out diagnostic subagents per trajectory —
  there was exactly **one** failing rubric item across all 5 trials, so N parallel
  diagnosers would have returned the same single finding N times. I recorded this
  trade-off in META_INSIGHTS.md rather than fanning out for form's sake.
- I did dispatch **one adversarial audit subagent** where fresh eyes genuinely add
  value: hunting overfitting, cross-task regressions, and contradictions with
  surviving text. Its brief is the 5 questions in META_INSIGHTS.md.
- Verification was done by *executing the grader*, not by reading it.
- Prior iterations: none — `RUNMAP.md` and `LEDGER.md` are empty (iteration 1),
  `rejected.jsonl`/`history.jsonl` absent. Nothing to build on or avoid.

## Good things to PRESERVE (do not let a future iteration undo these)

- **The exclusivity rule** ("never name a second category, not even to rule it out").
  It is counter-intuitive and a future iteration may read it as needless hedging-ban.
  It is mechanically required: `_verdict_present()` returns False if any other
  `TAXONOMY_EXCLUSIVE` member appears as a whole word. Verified above.
- **`orchestrator.md` containing no taxonomy token.** Adding one is an attractive
  "clarification" that silently risks the exclusivity check on other tasks.
- **"Resolve the owner, never recall it."** Do not re-introduce a fixed owner→repo
  table; the forbidden lists of 001/002 and 003 point in opposite directions.
- **Confidence as an always-written verdict field**, distinct from the optional
  inline marker.
- **The "if the evidence does not establish a cause, write no category" escape.** It
  looks like it weakens the main rule; it is what keeps the mandatory Category field
  from converting task 008's honest "the log does not say" into an invented cause.
- **The neutral stand-in token in the worked example.** It is deliberately a token
  that is gold for none of the graded tasks. Changing it to the "more realistic"
  `automation_failure` would let a lazy copy score this task without reasoning.
- **`application_bug` covering a bad value that *raises*.** The intuitive wording
  ("the code ran and completed") silently hands task 003 to `automation_failure`.

## Residual risks I could not close

- **`aap2_agent.md:204`** (pre-existing baseline YAML) shows
  `scm_url: https://github.com/agnosticd/agnosticd-v2` in a `__meta__` example. That
  pair is task 003's *forbidden* call. I left it: it is illustrating real record
  structure, it is the value my Step 6 rule tells the agent to **parse** rather than
  recall, and editing baseline text I have no evidence is harmful would be scope creep.
  If a future RESULT shows `broke={tool_calls}` on 003, this line is the first suspect.
- **The `orchestrator.md` edit remains the least verifiable of the five.** I can run
  the grader's matcher offline; I cannot run the orchestrator's summarising behaviour.
- **Step 6 is the weakest risk/reward edit** and is cleanly separable. The baseline
  already scored `tool_calls`=1.0 on 001, so the hazard it removes was not actually
  biting on the target task. If a RESULT shows a `tool_calls` regression anywhere,
  revert Step 6 alone and keep the rest.

## Deliberately skipped

- **Tool-call efficiency as a scored target** — `tool_calls` is already 1.0. I touched
  the owner-guessing path only because it is a latent *forbidden-call* risk and a
  contradiction in the file, not to chase a metric that is maxed.
- **`completion`** — already 1.0.
- **The other 5 domain agents** (`babylon`, `cost`, `icinga`, `ocpv`, `security`) and
  routing — this task's footprint is `services=["platform","github"]` →
  `investigate_aap2_job`, and routing was correct in all 5 trials. Editing unread
  files adds risk with no upside.

## Escalation (no tool/code layer in this phase — recording honestly)

Nothing here requires a new tool; the failure was a genuine prompt-knowledge gap and
prose is the correct fix. But two observations for whoever owns the code layer:

1. The taxonomy is duplicated in three places (`verify.py`,
   `src/bench/contract.py`, and the runtime `aap2-job-failure-rca/SKILL.md`). The
   agent's system prompts are a fourth copy now. If the runtime skill were actually
   reaching the agent's context, this gap would not exist — worth checking whether
   `skills/aap2-job-failure-rca/SKILL.md` is loaded at runtime at all, because its
   step 7 already states the rule correctly.
2. `_verdict_present`'s exclusivity check is invisible to the agent. An agent writing
   a thorough differential diagnosis ("ruled out: platform_failure, because…") is
   penalised for good reasoning. That is a defensible grader choice, but it means the
   rule *must* be stated in the prompt, as I have now done.
