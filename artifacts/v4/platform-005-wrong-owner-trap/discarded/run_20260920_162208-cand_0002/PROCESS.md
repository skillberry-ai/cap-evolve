# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration 2/3 · candidate `cand_0002` · parent = champion (seed, val 0.604) · capability `system-prompt`

> **This file was rewritten mid-iteration.** An earlier version of it described a different
> edit set, built on the claim that cand_0001's edit was **inert** (100% of it in a file this
> task never loads). That claim is **false** and I disproved it myself before finalizing — see
> *Correction* immediately below. Both the diagnosis and the shipped edit set changed as a
> result. The `JOURNAL.md` entry carries the same retraction as an append, per the rules.

## Correction: cand_0001's edit was NOT inert, and my first edit set was a re-proposal of it

`prior_iterations/cand_0001/diff.patch` (124 lines) carries **only** `--- a/aap2_agent.md` /
`+++ b/aap2_agent.md` headers, which reads as "the whole edit went into one unloaded file."
That file is **truncated**. Diffing the actual scored snapshots settles it:

    diff candidates/seed/<f>.md candidates/cand_0001/<f>.md   # changed lines
      orchestrator.md    23
      shared_context.md  10
      aap2_agent.md     199
      babylon_agent.md   78     <-- a LOADED file
      cost/icinga/ocpv/security  0

So cand_0001 edited 4 files, `babylon_agent.md` among them (+78 lines in the single most
load-bearing file for this task), and its own `PROCESS.md` was right while its `diff.patch`
was wrong. **Its val 0.518 vs 0.604 is a real measured regression, not noise around a no-op.**

That mattered enormously, because my first edit set for this iteration independently
re-derived cand_0001's content almost point-for-point: error-vs-`found: false`, progressive
term shortening, an AgnosticV/AgnosticD ownership table with "`rhpds` never owns AgnosticD",
"after two empty results against the same `owner/repo`, change the `owner/repo`", a
`## Reporting What You Found` section, a `| Value | Read from |` table with
`{owner}/{repo}:{path}`, and the identical `shared_context.md` owner fix. I reverted all three
files to seed (verified 0 diff), then rebuilt on a different axis. `INSTRUCTIONS.md` forbids
re-proposing a refuted edit, and this would have been one measured at 0.518.

**What cand_0001's rejection most likely bought us (the information its diff hid).** Its
`babylon_agent.md` rule 2 said: *"Say so and stop — do not fall back to sweeping repos with
keyword searches."* Both winning trials depended on exactly that move — t4 won via
`search_github_repo` sweeps of `agnosticd/agnosticd-v2` on calls 6-7. Two further suspects: an
AAP2-deferral escape hatch, and an abbreviation-expansion rule (`adv`→`advanced`,
`dev`→`developer`) that names this task's own item and role. **Nothing in cand_0002 suppresses
a recovery search, and nothing in it expands an abbreviation.**

## The load-path finding (unaffected by the correction above — still verified)

**This task never loads `orchestrator.md` or `aap2_agent.md`. It fast-path routes straight
into the `babylon` sub-agent.** `classify_fast()` (`parsec-live/src/agent/agents.py:256`) is a
deterministic regex over the question text: `_AAP2_PATTERNS` does not match, `_BABYLON_PATTERNS`
matches on the literal `catalog item`, so it returns `"babylon"` and the orchestrator LLM is
never invoked. Corroborated by `_run/logs/parsec-live.log` for this exact question text
(`Streaming sub-agent babylon started (fast-path)`), and by the fact that the tools all five
trials used (`lookup_catalog_item`, `fetch_github_file`, `search_github_repo`,
`search_agnosticv_prs`) are absent from `get_orchestrator_direct_tools()`.

**The prompt footprint for this task is exactly `shared_context.md` + `babylon_agent.md`.**
`babylon.max_rounds = 8` (`agents.py:118`). The graded answer is `"".join()` of every
`event: text` frame for the whole turn (`parsec_harbor_agent.py:164-191`) — tool results are
never graded, so a value must be restated in prose, and early-round prose counts permanently.

## Ranked issue list (clusters by # failing trials, biggest first)

| rank | cluster | trials | shared root cause | tag | change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **Whole round budget burned inside the wrong repository** | t2 (0.29), t3 (0.29), t0 (0.44 partial) | Agent sweeps `rhpds/agnosticv` keyword after keyword for a path that structurally cannot live there. t2 spent 10/10 calls and t3 8/8 inside agnosticv, never touching `agnosticd/agnosticd-v2`. | KNOWLEDGE | sharpen existing rule + one sourced fact |
| 2 | **Turn ends on a statement of intent, so nothing is reported** | t0, t2, t3 | All three end on the harness punt boilerplate (`agents.py:1108`) with zero values written. t3's last words were the *correct* next step, stated instead of taken. | BEHAVIORAL | port a proven rule block |
| 3 | **A failed tool call read as a fact about the world** | t0, t1, t2, t3 | `lookup_catalog_item` errored in 4/5 trials (3 distinct error strings). Seed rule said `found: false` ⇒ "the item **does not exist**. Do NOT fall back to other methods" — nothing distinguished an *error* from a negative answer. | BEHAVIORAL | rewrite the rule |
| 4 | **Fully qualified lookup term misses; agent never shortens it** | t0, t1, t2, t3 (t4 = counter-example) | t4 is the only trial where the lookup succeeded, on the third try with a loose fragment after the `{account}.{item}.{stage}` name missed twice. Unprescribed. | KNOWLEDGE | fold into the rewritten rule |
| 5 | **Prompt asserts a false GitHub owner** | none (latent) | `shared_context.md:162` and `aap2_agent.md:238` positively claimed `rhpds/agnosticd-v2`, which does not exist. `forbidden_violations` is **empty in all 5 trials**, so this is a real defect that was **not** the live failure and earns no score credit. | KNOWLEDGE | factual correction |

## Changes made this iteration — 6 edits, 3 files, +32 lines

The governing constraint: cand_0001 added **+260 lines across 4 files (+78 into
`babylon_agent.md`)** and measured 0.518. cand_0002 adds **+32 lines total, +27 into
`babylon_agent.md`**, and every one of them is either a *port of text already proven in this
repo*, a *deletion*, a *narrowing*, or a *factual correction*. Net new invented prose: ~12 lines.

| # | cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- | --- |
| 1 | 2, 1 | **port a rule the source already proves** | `babylon_agent.md:8-21` — new `### Critical Rules`, 3 rules, immediately after the intro | `aap2_agent.md:7-27` already carries exactly this block — "NEVER narrate your process", "ALWAYS produce a structured final report", "**Budget your rounds** … Do NOT speculatively browse directories … More fetching without analysis is worse than a report with some gaps". `babylon_agent.md` has **none** of it, though it runs under the same finite `max_rounds` and the same streaming grader. This is `SKILL.md` lever 4 — *add a rule the source requires but the prompt omits* — and it traces to a real source: a sibling agent prompt in this same capability. Rule 2 adds the one mechanism aap2's version leaves implicit: the investigator never sees tool results, so state each value **in the turn the tool returns it**. | Yes — t1 and t4 already satisfy all three. |
| 2 | 3, 4 | rewrite a rule | `babylon_agent.md:92-97` — lookup rule 2 | Replaces "`found: false` ⇒ the item does not exist; do NOT fall back" with: an `{"error": ...}` means the lookup **did not run** and says nothing about existence; retry shorter (`{account}.{item}.{stage}` → `{item}` → most distinctive fragment); only `found: false` **with** a `similar_items` list is an answer about the item. Generalizes to every tool: never read a call that failed as evidence about the world. Also folds in t4's winning escalation. | Yes — no winner depended on treating an error as absence, and the shortening ladder *is* t4's behavior. |
| 3 | 1 | **deletion** | `babylon_agent.md` — removed "If it returns `found: false` with no similar items, the item **does not exist**. Do NOT fall back to other methods." | This is the dead end 3 of 5 trials obeyed. Its live constraint (don't flail after a negative lookup) survives in Critical Rule 3 and lookup rule 5, both of which are *more* specific about what not to do. | Yes — removing a false premise cannot cost a winner. |
| 4 | 1 | add one sourced fact | `babylon_agent.md:101-107` — lookup rule 5 | "The lookup resolves **which repository holds a file** — not whether the file exists." If the request names the path, fetch it directly. Then the ownership one-liner: catalog YAML (`common.yaml`, `{stage}.yaml`, `__meta__`) → `rhpds/agnosticv`; Ansible content under `ansible/` (playbooks, `configs/`, `roles_ocp_workloads/<role>/`) → `agnosticd/agnosticd-v2` (v2) or `redhat-cop/agnosticd` (v1); **`rhpds` owns no AgnosticD repo, so an `ansible/` path is never found in an agnosticv repo however the search term is spelled.** A repo-layout fact, not an instance — any question about role defaults on this platform hits it. | Yes — it endorses where t1 and t4 both ended up, and sanctions t1's winning blind fetch with the owner inferred as `agnosticd`. |
| 5 | 1 | **narrowing (a cut, not an addition)** | `shared_context.md:108` + new bullet at `118-121` | The seed's *Catalog Item Search Strategy* says "**Exact match returns 0 rows → broaden immediately**", unscoped. The failing trials obeyed it literally and broadened the **keyword** forever while never changing the **repo**. Two changes: (a) scope the section's opening to "searching the provisions DB or the catalog index", which is what its examples are about; (b) one bullet stating that the broaden-and-retry loop does **not** apply to GitHub repo searches — a repo search is scoped to one `owner/repo`, so two empties mean the repository is wrong and rewording a third time cannot find the file: **change the `owner/repo`.** Domain-general (aap2 reads the same repos), hence shared context. | Yes — neither winner ever hit 2 empties against one repo, and the bullet explicitly *keeps* searching as the recovery move (it redirects it, unlike cand_0001's "stop"). |
| 6 | 5 | factual correction | `shared_context.md:167`, `aap2_agent.md:238` | `rhpds/agnosticd-v2` → `agnosticd/agnosticd-v2` in the Sources example URL and in the version→owner table. `aap2_agent.md` is not loaded for this task; fixed anyway because it is a defect, and flagged as earning **no** score credit here. | Cannot regress: no correct behavior can depend on a false premise. |

Untouched at seed state: `orchestrator.md`, `cost_agent.md`, `icinga_agent.md`,
`ocpv_agent.md`, `security_agent.md`.

## Verify-the-fix (the exact divergence point in each failing trial)

- **t2 (0.29 → the strongest case).** Divergence at call 4, after the lookup errored. It ran
  `search_github_repo(rhpds/agnosticv, …)` three times, then three bare-directory
  `fetch_github_file` probes (`path: "agd-v2"`, `"."`, `"sandboxes-gpte"`), and **never
  queried `agnosticd/agnosticd-v2` at all**. Three edits intercept this independently:
  Critical Rule 3 bans directory browsing outright and specifically says *when you were
  already given the path, just fetch it* (all three probes die there); lookup rule 5 makes
  searching an agnosticv repo for an `ansible/` path structurally pointless; the
  `shared_context.md` bullet stops the keyword sweep at call 6 and redirects it to the other
  `owner/repo`. Any one converts this trial.
- **t3 (0.29).** Eight calls, all inside `rhpds/agnosticv`, one per round, so zero rounds
  remained to answer. Same three interceptions. Additionally its final streamed text was
  *"This is the agnosticv catalog-side config, not the workload role defaults. I need to find
  the AgnosticD repo…"* — a correct diagnosis **spent as narration on its last round**.
  Critical Rules 1 and 2 target that exact sentence: rule 1 forbids the "I need to…" form,
  rule 2 requires the last text block to be the report, and lookup rule 5 hands it the
  agnosticv-vs-agnosticd distinction ~6 rounds earlier than it derived it.
- **t0 (0.44) — partial, and I am not claiming more.** It scored `tool_calls=1.0` and reached
  the golden fetch, but on its **last** round after five consecutive
  `search_github_repo(rhpds/agnosticv, …)` calls. The `shared_context.md` bullet cuts that
  sweep at call 6 and lookup rule 5 gets it there directly, freeing ~3 rounds — so a report
  *would* have been written. **But the fetch returned simulator-invented content**
  (`operator_channel: stable`, `quay_admin_user: quayadmin`, no version key) with the wrong
  envelope shape, not the seeded golden body. t0 never held the graded literals, so with
  rounds to spare it would have reported what it actually read and gained the citation item
  (≈0.2 → 0.4 on `answer`), not 1.0. **That residue is environment fidelity and is
  unreachable by any prompt edit.**
- **Regression check on t1 and t4 (both 1.0).** t1's winning move was a blind
  `fetch_github_file` of the instruction's path with the owner *inferred* as `agnosticd`
  because the lookup had failed — now explicitly sanctioned by lookup rule 5 rather than left
  to luck. t4's winning move was the shortened lookup term, now lookup rule 2's ladder, plus
  `search_github_repo` sweeps of `agnosticd/agnosticd-v2` on calls 6-7 — which no edit here
  discourages (the deliberate contrast with cand_0001). Neither trial's output format is
  constrained by anything I added; I deliberately did **not** add a report template, because
  the winners already produce a good one and cand_0001's restructure of one is a live suspect.

**Honest expectation.** The mechanism is redundant for t2/t3 and partial for t0, so the central
case is a real move above 0.604. Not a guarantee: the simulator is non-deterministic across
trials (identical queries return `[]` in some trials and matches in others, across three
response schemas), so the gate sees a distribution, not a point. And the gate is STRICT here
(`rejected.jsonl`: `paired Δ̄=-0.0860 <= 0 (SE=0 → STRICT fallback, warned; n=1)`), so this must
clear 0.604 outright.

## ESCALATION — a code-layer defect prose cannot reach

`_maybe_inject_budget_warning` (`agents.py:338`) is the mechanism that tells a sub-agent
"2 rounds remaining, write your report now". It is invoked at **exactly one** call site,
`agents.py:776`, inside the **non-streaming** `run_sub_agent`. The **streaming** loop the fast
path uses (`for _round in range(agent_cfg.max_rounds):`, `agents.py:901`) never calls it. So
every fast-path sub-agent — which is every trial of this task — runs to budget exhaustion with
no warning and then emits the unconditional punt boilerplate (`agents.py:1108`).

This is the highest-leverage fix for cluster 2 and it is **not a prose fix**: prose can ask the
agent to budget its own rounds (Critical Rule 3, which should help), but only the harness knows
how many rounds remain. Adding the existing `_maybe_inject_budget_warning` call to the streaming
loop is a one-line change in a file this phase forbids me to touch. Recorded here rather than
faked with more prose, per `INSTRUCTIONS.md`.

## Process & features used

- **Subagents.** Two read-only agents in parallel: (A) a routing/loading audit — which of the
  8 files is actually in context for this task; (B) per-trial transcript forensics — final
  graded text verbatim, ordered tool calls with arguments and results, budget-exhaustion check,
  and which concrete values existed anywhere in each run. (B) was decisive and **corrected me
  twice**: it established that t0 never held the golden values (so t0 is not a "read it and
  dropped it" case), and it found the streaming/non-streaming split in
  `_maybe_inject_budget_warning` that became the escalation above. Both agents' negative claims
  I re-verified at the source before acting, per cand_0001's lesson.
- **Two hypotheses I formed and then disconfirmed myself.** (i) That `orchestrator.md`'s "NEVER
  re-synthesize the agent's analysis" rule was swallowing the values — disconfirmed two ways
  (the winners' values appear with no orchestrator summary; the file is never loaded). (ii) That
  cand_0001's edit was inert — disconfirmed by diffing the candidate snapshots, which cost me a
  whole edit set but saved the iteration from re-proposing a refuted candidate.
- **Prior iterations read.** `RUNMAP.md`, `prior_iterations/cand_0001/{PROCESS.md,diff.patch}`,
  **and the raw snapshots `candidates/{seed,cand_0001}/`** (the step that mattered — the
  snapshotted diff is truncated), `LEDGER.md` (`broke={}`, `fixed={}`), `JOURNAL.md` including
  its two self-corrections, `INSIGHTS.md`, `META_INSIGHTS.md`, and `rejected.jsonl`.
- **Structural difference from the refuted candidate**, as `INSTRUCTIONS.md` requires — and
  this time measured against what cand_0001 *actually* contained, not against its truncated
  diff:
  1. **Direction.** cand_0001 told the agent to **stop** after a failed lookup ("do not fall
     back to sweeping repos with keyword searches"). cand_0002 tells it to **redirect** —
     change the `owner/repo` and keep searching. Both winners won by searching; suppressing
     that is the most likely source of the 0.518.
  2. **Volume.** +260 lines / 4 files → **+32 lines / 3 files**, on a prompt already 267 lines
     long read by `claude-sonnet-4-6`. cand_0001's ideas and mine overlap; the *dose* does not.
  3. **Provenance.** cand_0002's largest block is a **port of `aap2_agent.md:7-27`**, text
     already in this capability, placed at the top of the file. cand_0001 wrote its own version
     and buried it 277 lines deep.
  4. **Subtraction.** cand_0002 includes a deletion and a **scope narrowing of an existing
     over-broad rule** (`shared_context.md`'s "broaden immediately"), an axis cand_0001 never
     touched. Every one of its 10 changed `shared_context.md` lines was additive.
  5. **No output template.** cand_0001 added a report section and a value table. cand_0002 adds
     neither — the winners already emit a good report, and rewriting a template passing trials
     follow is the classic regression surface.
  6. **No abbreviation expansion.** cand_0001's `adv`→`advanced` / `dev`→`developer` rule names
     this task's own item and role, which is also the overfitting `INSTRUCTIONS.md` bans.

## Good things to PRESERVE (do not let a future iteration undo these)

- **Read `candidates/<id>/` directly, never `prior_iterations/<id>/diff.patch`.** The
  snapshotted diff for cand_0001 is truncated to one file and reads as complete. Diagnosing a
  rejection from it produces a confidently wrong story — it produced two for me.
- **The prompt footprint for this task is `shared_context.md` + `babylon_agent.md` only.**
  Editing `orchestrator.md` or the four unloaded domain files cannot move this task's score.
- **Never reintroduce `rhpds/agnosticd-v2` as a positive claim in any of the 8 files.** Both
  occurrences are corrected; grep before finalizing. (A sentence saying `rhpds` owns no
  AgnosticD repo is fine and is deliberately present.)
- **Never suppress the repo-search recovery move.** t4 wins with `search_github_repo` sweeps.
  Redirect it; do not forbid it. This is the one thing cand_0001's rejection most likely bought.
- **The error-vs-`found: false` distinction**, and the absence of "Do NOT fall back to other
  methods" — that rule is the dead end three of five trials obeyed.
- **The `{owner}/{repo}:{path}`-on-one-line citation shape** (grader's matcher requires repo and
  path on the same line within ~40 chars). Not added as a template this iteration, but do not
  add anything that breaks it.

## Deliberately skipped (cluster + why)

- **`orchestrator.md` routing** and the four other domain files. Not in this task's context.
- **Anything targeting the forbidden wrong-owner *call*.** `forbidden_violations` is empty in
  all 5 trials — that trap was never tripped on the wire.
- **Naming the ruled-out repository in the answer as a refutation.** The forbidden answer item
  has **no `attributed_to`** qualifier, so *any* occurrence of the string costs the point — even
  inside a correct "it is not there" sentence.
- **A report template / value table.** cand_0001 had one; it is a live regression suspect and
  the winners already produce the right shape. Omitted on purpose, not overlooked.
- **t0's wrong file body.** Environment fidelity (the simulator served a non-golden body for a
  correct fetch). Unreachable by prompt text; flagged so a future iteration does not read t0's
  residual gap as an agent defect.
