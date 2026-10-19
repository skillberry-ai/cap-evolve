# PROCESS — cand_0004 (iteration 4/4, last of the run)

Parent: `cand_0002` (the champion). Files touched: `shared_context.md`,
`orchestrator.md`, `cost_agent.md`, `security_agent.md`, `aap2_agent.md`.
Untouched: `babylon_agent.md`, `icinga_agent.md`, `ocpv_agent.md`.

The brief said "no actionable failures in focus — seek a robustness/generalization
gain that does not regress the solid tasks." So this iteration did not chase a
task cluster. It went after **three properties of the benchmark harness** that
cost reward on any task that happens to trip them.

---

## 0. Why I changed lever: the inherited diagnosis was arithmetically wrong

The three prior iterations all concluded "the search is flat, prose is
exhausted, the measurement is the binding constraint" (`META_INSIGHTS.md`).
That rested on `internal_estimate.json`: champion 0.8037 vs seed 0.8212,
Δ = −0.0175, z = −0.76 — i.e. the accepted champion is *worse than the untouched
baseline*.

I rebuilt that comparison per-task from the raw rollouts (67 tasks; 10 seed
trials each vs the champion's 4 full-coverage arms) and got the opposite sign:

| comparison | Δ | se | z |
|---|---|---|---|
| paired per-task, all rollouts | **+0.0241** | 0.0184 | 1.31 |
| paired per-task, timeout-free rollouts only | **+0.0497** | 0.0178 | **2.80** |

The reason is a confound nobody had checked. The simulator's 240 s tool timeout
fires at a **~10× different rate between rounds**:

| arm | rollouts | tool calls | timeouts | rate |
|---|---|---|---|---|
| seed | 670 | 3674 | 16 | 0.44% |
| cand_0002 | 268 | 1353 | 63 | **4.66%** |
| cand_0003 | 12 | 67 | 3 | 4.48% |

The champion was measured in a round whose infrastructure was ~10× flakier than
the round the seed was measured in. That alone accounts for the negative
full-coverage delta. **`cand_0002` is not worse than seed; it is better, and this
run has been reasoning from a confounded number for two iterations.** This is the
most important item in this file — it also means the earlier conclusion "prose is
exhausted" was drawn from a measurement artifact, not from the prompt.

## 1. Ranked issues (all three are harness properties, verified in source)

Ranked by **domain spread**, per `INSIGHTS.md`'s confirmed heuristic that spread
beats points as a proxy for "would this help a task I cannot see". All three span
every domain, because all three live in the harness rather than in a task.

### Issue A — a tool that never answered is treated as a finding (highest value)
`sim_backend.py:243` wraps every simulated call in `asyncio.wait_for`; on timeout
it returns one fixed template for *any* tool: `"<tool> did not respond within
240s. The simulated service accepted the request and never answered; treat this
as the tool being unavailable rather than as a result."`

- 64 rollouts, **39 of 67 tasks**, **13 distinct tools**. Not seeded per task — it
  is genuine infrastructure flake, so it can hit any task, including hidden ones.
- When the agent re-called the tool it **got real data 43/45 times**.
- When it gave up instead: **−0.185 mean** vs the same task's timeout-free trials
  (n=24); within-tag-family **−0.268** (n=23).
- The parent had **no rule for this**, and carried a blanket `**NEVER call the
  same tool with the same parameters twice in a conversation.**` which *forbids
  the winning action*. Transcripts show the consequence: cost-073 made one call,
  it timed out, and the answer told the user "Retry the query — Cost Explorer
  occasionally times out" — advising the user to do the retry it could have done
  itself. Reward 0.2 on a task seed solves 10/10.

### Issue B — the prompts route agents into tools that can never work
`routing.py:62` defines a fixed `UNMODELLED` frozenset; every call returns
`"<tool> is not modelled by the simulation. The benchmark excludes it
deliberately; the question should be answerable from the identifiers you were
given."`

Measured over 962 rollouts: `query_provisions_db` **299 calls / 0 successes**;
`render_chart` **51 / 0**. No other tool is at 0%. Also in the set:
`db_describe_table`, `db_list_tables`, `db_table_sample`, `db_read_knowledge`,
`query_aws_pricing`, `generate_report`.

The parent actively directed agents into these — including a **`MANDATORY: Call
db_describe_table before querying ANY table`** and an aap2 workflow whose *step
1* was a `db_describe_table` call. 96 rollouts called a dead tool more than once.
The honest cost is modest (≈ one wasted round per call; ≈ −0.01 to −0.04 once
budget-exhaustion is partialled out) but it is pure waste against a cap as low as
8 rounds, and it yields answers naming a dead tool as the obstacle.

### Issue C — running out of rounds truncates the answer
Caps are low and the agent is never told the number: orchestrator 10
(`config.yaml:13`); sub-agents 8 (cost, babylon, ocpv), 15 (icinga), 20 (aap2,
security) (`agents.py` `AGENTS`). On exhaustion the harness appends
`_MAX_ROUNDS_TEXT` (`orchestrator.py:1105`, emitted `:1336`). 25 rollouts hit it,
mean reward **0.444**, none at 1.0; 5 had written nothing first.

## 2. Edits, by class

| # | File(s) | Class | Edit |
|---|---|---|---|
| E1 | `shared_context.md` | **right-domain-wrong-action** (replaces a harmful rule) | Replaced the blanket "NEVER call the same tool with the same parameters twice" with two branches: a call that **never answered** → re-issue once; a call that **answered** negatively (empty, not found, validation, named backend failure, 429/quota, not-modelled, internal/malformed) → never re-issue, pivot. Capped at one retry. Plus "don't hand the retry back to the user". |
| E2 | `shared_context.md`, `orchestrator.md`, `cost_agent.md`, `aap2_agent.md` | **missing knowledge** | "Being offered a tool does not mean it is served": the first not-modelled result is **final for that tool for the conversation** — don't re-call, don't substitute a sibling, don't name it as the reason a figure is missing, re-plan onto served sources. Removed the `MANDATORY db_describe_table` line; reordered the aap2 "job not found" workflow to hit the AAP2 API first; made charts/reports/pricing non-blocking. |
| E3 | `shared_context.md` | **overcautious/overconfident** (budget discipline) | "Running out of tool rounds costs most of the answer": write once you can answer and in any case by ~6 calls; if ever told rounds remain, write immediately; spend rounds only on what the answer needs. |
| E4 | `security_agent.md` | **missing knowledge** | CloudTrail attribution without a provisions DB: SELECT `userIdentity.username` (the column that carries it); `arn`/`type` are frequently null; if null, re-run selecting `username` before reporting unknown. |

All four name a *mechanism*, not an instance; no rule's trigger is a task literal (§4).

## 3. Verify-the-fix (would the text have changed the actual failing moment?)

- **E1 vs cost-073 `inc_p1_1`:** one call → timeout → answer told the user to
  retry. E1 branch 1 matches that string and orders the retry as the next call;
  the parent's blanket rule forbade it. **Changes the failing step.**
- **E1 vs icinga-214 `inc_p2_2`:** one `query_icinga` call, timeout, stopped —
  "the Icinga tool did not respond … so I cannot retrieve". Seed scores this
  10/10; this arm scored 0.314. **Changes it.**
- **E1 vs platform-162 `inc_p2_2`:** timed out, then burned its rounds and hit
  the cap. E1 and E3 both bite. **Changes it.**
- **E1 negative control — cost-408:** its *designed* behaviour is to report GCP
  unavailable. Its error is `"GCP BigQuery query failed: no matching cost data"`
  — a **response**, which E1 routes to branch 2 (no retry, report it). The string
  is listed in branch 2 verbatim. **Correctly does not fire.**
- **E2 vs aap2 "job not found":** parent step 1 was a `db_describe_table` call
  that cannot succeed; step 1 is now the AAP2 API. **Changes it.**
- **E4 vs cloud-057:** trials selecting `arn, type` got nulls and scored 0.8;
  trials selecting `userIdentity.username` got the user and scored 1.0. E4 names
  the right column. **Changes it.**
- **E3:** *not* verifiable this way — the stub is harness-appended, so no
  transcript shows the model deciding to stop. E3 is the weakest of the four and
  I flag it as such rather than claiming verification.

## 4. Non-overfitting audit (mechanical, per `INSIGHTS.md`)

Extracted every literal from the final diff: `10`, `20`, `429`, plus tool/column
names (`query_provisions_db`, `db_*`, `tower_job_log`, `deployer_job`,
`userIdentity.username`, `ref`, `cluster`, …). **No GUID, hostname, ticket,
count, or task-specific service name.** Every number is a generic cap or an HTTP
status. Each rule restates without a task-specific noun — the test the brief asks
for.

The three mechanisms were **read from the simulator source** (`routing.py`,
`sim_backend.py`, `agents.py`, `orchestrator.py`), not inferred from task
content. That is the strongest available argument for transfer: a hidden task
runs on the same simulator.

## 5. Process — subagents, and what each pass caught

Three blind passes. **Pass 3 again caught what passes 1–2 missed, and this time
it caught a regression I had introduced myself.**

- **Pass 1 (independent re-derivation).** Confirmed the 0%-success tools and the
  retry asymmetry, and **corrected two of my framings**: the timeout rate differs
  ~10× by round (§0), and the `query_provisions_db` penalty is ≈0 once
  budget-exhaustion is partialled out, not −0.13. Adopted both.
- **Pass 2 (adversarial, aimed at regressions).** Proved `_MAX_ROUNDS_TEXT` is
  **harness-appended, not model-written**, and that answers merely *ending* with a
  follow-up offer are **not** penalised (158 rollouts, mean 0.845). My first draft
  claimed the opposite and contradicted `orchestrator.md`'s `{{choices}}`
  requirement. Rewrote E3 from "never ask a question" into round budgeting. Also
  flagged branch 1 saying "rate-limited → retry" against existing "429 → pivot".
- **Pass 3 (attacks only pass 2's repairs).** Found **my own `security_agent.md`
  repair had introduced a regression**: "where the identity fields are null, say
  the event records no identity" contradicted a correct existing rule at
  `security_agent.md:47` and matches exactly the trials scoring 0.8 instead of 1.0
  on cloud-057. Rewrote as E4. It also proved my "check your tool list" framing
  was **backwards** — the dead tools *are* in every agent's tool list
  (`tool_definitions.py`, `get_cost_tools` et al.), so "if it is in your tool
  list" reads as *permission*. Rekeyed all of E2 onto "offered ≠ served; the first
  not-modelled result is final".
- I re-verified each pass's load-bearing claims myself (round caps, `UNMODELLED`
  membership, tool-list membership, the `completion=1.0` partial-credit point, the
  timeout-rate table). One pass-1 claim I did **not** adopt: that existing
  guidance already covered retries — it was reading my own edited file; `grep`
  against `candidates/cand_0002/` shows the parent has no such rule.

## 6. Good things to PRESERVE (do not undo)

- The parent's **conclusion checklist** at the top of `shared_context.md` and its
  carve-outs (masked/redacted ≠ absence; placeholder zeros must not be stated as
  figures) — `INSIGHTS.md` records these as regression-prone and hard-won.
- The parent's **line-citation** and **epoch** rules.
- `security_agent.md:42-48`'s field notes, especially "if a user-identity column
  comes back null, re-run selecting `userIdentity.username`" — E4 now points at it
  instead of contradicting it.
- Branch 2 of E1 **must keep** the named-backend-failure and not-modelled cases.
  Collapsing E1 into "retry on any error" would break cost-408 and re-introduce
  dead-tool retries.

## 7. What I skipped, and why

- **The fast-path routing/tool gap** (largest cluster, ~3.5 task-points). Four
  iterations have confirmed it unreachable from prose: `classify_fast()`
  (`agents.py:256`) dispatches before the orchestrator LLM, so `orchestrator.md`
  is never built for most tasks, and sub-agents cannot hand off. Escalated in
  `FRAMEWORK_IMPROVEMENTS.md`.
- **Relocating `shared_context.md` into the domain files** (the dilution A/B).
  `cand_0003` tested exactly this and was rejected with `broke={}`.
- **The trailing-follow-up-offer class.** ≈ −0.03 and noisy; pass 2 showed it is
  not penalised. Deliberately untouched.

## 8. Honest risk assessment

- E1 and E2 are the high-confidence edits: mechanism read from source, effect
  measured, failing moment verified, negative control verified.
- **E3 is the weakest** — harness-generated stub, no verifiable decision point,
  and its mechanism (the model managing a budget it is not told) is indirect.
- E1 costs one extra round on a timeout. 85% of rollouts use <10 calls, so there
  is headroom, but on an 8-round agent that already ran long it is a real trade;
  the one-retry cap is what bounds it.
- §0 means **this candidate is itself scored under whatever timeout rate this
  round happens to have.** If the gate rejects it with `broke={}`, read the
  timeout rate of the scoring arms before concluding the edit failed — that is
  the mistake this run has already made twice.
