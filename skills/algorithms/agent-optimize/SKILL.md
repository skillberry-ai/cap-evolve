---
name: agent-optimize
description: 'Free-form optimization algorithm for agent orchestration mode: the conversational agent owns the whole search — proposing capability edits itself, screening them cheaply, gating each on full val, and sealing test once. Use when orchestration_mode is agent and algorithm_skill is agent-optimize. For a deterministic loop use hill-climb, gepa or skillopt instead.'
component: algorithm
argument-hint: "agent-mode only — set orchestration_mode: agent + algorithm_skill: agent-optimize"
allowed-tools: Read, Write, Edit, Bash, Task
provides: [candidate]
needs: [scores, traces, candidate]
---

# agent-optimize — the free-form loop you own

The one algorithm with **no deterministic subprocess** and **no per-iteration optimizer**: you — the agent
that ran intake — are the optimizer, the scheduler and the stopping rule. `cap-evolve run` (with
`orchestration_mode: agent`) does check → baseline, prints a handoff, and returns. From there the search
is yours, bounded by core's invariants and the free-text **`stop_condition`**. Drive the *existing*
primitives so the run dir and dashboard stay populated as in a deterministic run (unattended:
`host.py`/`--agent-driver`). A forensic run (#665) followed this loop in PROSE, not BEHAVIOR — 1
candidate/round forever, full-val paid regardless of scope, two mergeable accepts never merged — so
every step below names the script that decides for you.

## Shell variables used below

```bash
R="<run_dir from the agent-mode handoff>"      # e.g. .capevolve/run_20250101_120000
P="<project dir>"                              # the dir holding capevolve.yaml + adapters/
S="${CAPEVOLVE_SKILLS_DIR:?set CAPEVOLVE_SKILLS_DIR to the skills/ dir}"
A="$S/algorithms/agent-optimize/scripts"       # this skill's helpers
mkdir -p "$R/work"                             # working copies live here (RunDir does NOT create it)
```

Every script imports `_bootstrap` itself and prints JSON on stdout.

## Phase 0 — understand before you optimize

Once, before any edit, and **ask the user any blocking question here** so the loop then runs unattended.
Read `PROJECT.md`, `capevolve.yaml`, the adapter, every file under `capability_path`,
`./guidance/<cap>/SKILL.md`, `optimizer/INSTRUCTIONS.md` if present; understand the task, `run_target`
output, `score()` reward, per-task feedback, val/test size, `num_trials`, `gate_mode`/`gate_k_se`,
`objectives`/`model_routing` if set (sections below), edit surface.

Then let `spend.py` parse the free-text **`stop_condition`** rather than restating it: it prints
`constraints.predicates`, every concrete check it extracts. **If `constraints.ambiguous` is non-empty,
ASK THE USER before the loop starts** — a vague clause is reported, never guessed at.

## Model routing — resolve the model for every judgment call

`capevolve.yaml` may set `model_routing` for seven roles (no block = each resolves to
`optimizer_model`, unchanged): `plan`/`root_cause` (steps 1-2), `propose`/`implement` (step 3),
`evaluation_analysis` (5-6), `merge` (before sealing), `synthesis` (final report). Call
`resolve_model(role, spec)` at each and report which model you got — one model silently doing
root-cause AND merge AND mechanical-edit judgment is the undifferentiated cost this breaks. Exact call:
`algorithm.md`, "Model routing".

## Agent-mode loop

**Every round's goal: the fewest evaluations that reach the target score.**

Baseline scored the seed on val and set `best_id = seed`. Each round:

**0. Check you can afford the round**, with `--n-siblings N` for the N candidates you intend to run,
*before* spending:

```bash
python "$A/spend.py" --run-dir "$R" --project "$P" --n-siblings 3
```

Act on the single `recommendation`: **`stop`** (a ceiling breached, `budget_exhausted()` true, or the
score goal met on FULL val) → **Stop & seal**; **`narrow_scope`** (≥80% of a ceiling consumed, goal
unmet) → ONE cheap candidate at tier 1; **`continue`** → run the round you planned. (Step 2 prices the
real N; this first call is a gut-check at a guess.)

`afford.affordable: false` (`afford.blockers` names the ceiling) means **do not fan out N** — check
BEFORE dispatching proposers. `afford.runner_spend_metered: false` means $0 is *unmetered*, not free —
bound the run with `max_metric_calls` and report **rollout counts, not dollars**.

**1. Read the signal.** Free — no new evaluation:

```bash
BEST="$(python "$A/spend.py" --run-dir "$R" | python -c 'import json,sys;print(json.load(sys.stdin)["best_id"])')"
python "$S/phases/diagnose/scripts/run.py" --run-dir "$R" --tag "$BEST" --split train > "$R/work/diag_t.json"
python "$S/phases/diagnose/scripts/run.py" --run-dir "$R" --tag "$BEST" --split val > "$R/work/diag_v.json"
```

Read `clusters` for what to fix and `kept_good` for what not to break. **With a disjoint train split,
diagnose it too and compare its cluster signatures to val's** — free, and it decides whether the round
can work at all: disjoint signatures mean no train-driven edit can move the val mean, and every
candidate is rejected for a reason that looks exactly like a null result. Say which, in the report.

**Read the per-task pass rate, not the per-task pass/fail.** At `num_trials: n` a task's reward is
`k/n`, and that fraction is what separates defects from noise:

| per-task rate | what it is | what to do |
| --- | --- | --- |
| `0/n` – `3/10` | a real, reproducible defect | this is where every edit should aim |
| `4/10` – `7/10` | genuinely unstable behaviour | fix by *removing* ambiguity, not adding rules |
| `8/10` – `9/10` | noise around a working path | **leave it alone**; "fixing" it is how churn starts |

**Audit the MEASUREMENT before you credit a failure**, in round 1 while free: does feedback name the
**defect** or only the tool; does a helper fail **silently**; did the rollout **run**, or is this
missing data wearing a 0.0? `edit-design-lessons.md`. **After two rejected rounds, read the TRACE
before writing a third** — never exercised ⇒ the **form** is wrong; exercised and still wrong ⇒ the
content is.

**2. Plan the round's branches — before creating any candidate dir.** The forensic run always forked
exactly 1 candidate, unstated. `plan_round.py` groups diagnose's clusters by shared implementation
surface into slots and estimates each slot's own branch count from its evidence — **varies by
root-cause structure, never a fixed constant**:

```bash
python "$A/plan_round.py" --run-dir "$R" --project "$P" --clusters "$R/work/diag_v.json" > "$R/work/plan.json"
python "$A/spend.py" --run-dir "$R" --project "$P" \
       --n-siblings "$(python -c 'import json;print(json.load(open("'"$R"'/work/plan.json"))["total_estimated_branches"])')"
```

Each `slots[]` carries `cluster_ids`/`affected_tasks`/`score_lost`/`hypothesis_stub` (yours to write the
real hypothesis against — no LLM call lives in `plan_round.py`) and `estimated_branches`;
`total_estimated_branches` is this round's N, read from the file, not asserted — accept, shrink
(unaffordable), or grow it, stating why when you override. A lone low-stakes slot legitimately
estimates 1 — running the planner and getting 1 is not the anti-pattern; skipping it is.
`algorithm.md`, "Branch planning".

**3. Create exactly the planned branches, then write each edit.** One `prepare_candidate.py` per
branch — never fewer than the plan's `total_estimated_branches`, never a bare `cp -r`:

```bash
TAG="cand_1"                                   # unique per branch — it IS the rollout tag
python "$A/prepare_candidate.py" -r "$R" -t "$TAG"
# edit the files under $R/work/$TAG your capability owns (Example only: see capability_path).
```

Every edit encodes a **general rule** — never a task id, gold value, or answer.

**Choose the edit FORM from the failure TYPE** — the form that fixes one failure type measurably
backfires on another:

| the failure you observed | the form that fixes it | the form that makes it worse |
| --- | --- | --- |
| rule stated, agent skips it under pressure | a prohibition + the symptom preceding it ("if about to X, already failed") | restating the rule — less compliant |
| complies, wrong call shape | a **positive recipe**: the correct call, its parts, in order | a don't-list — *more* unwanted output |
| a required element missing | a **structural REQUIRED slot** or code precondition | a prose reminder mid-document |
| behaviour should differ by situation | a conditional on an **observable predicate** | an unconditional rule plus exemptions |

Then: **no nuance clauses**; **exemption clauses do not scope**; **prefer an in-code guard to a prose
rule where the capability owns its tools**. Guard-closure trap: `edit-design-lessons.md`. **Verify
before you gate**: run the edit against the trace it targets and confirm it fires, then against 1-2
currently-passing tasks on the same surface and confirm it does NOT — unverifiable is a guess, drop it.
Within one branch, bundle only independent, low-risk structural fixes into its ONE working copy; a
probabilistic prose edit stays one edit, one branch. `algorithm.md`, "Bucketing edits within a slot".

**Every round evaluates a null control first** — a byte-for-byte copy of the current best, the noise
floor. **Read `$R/rejected.jsonl`; make each proposal STRUCTURALLY different** — never a narrower
version of a rejected rule.

**4. Micro-test first, when the cluster has one** — `microcase.py run-all`; `micro_test_fail` rejects
on the spot, no rollout paid.

**5. Build an EvaluationPlan, THEN screen at ITS stage — never default straight to full val.** 7/8
forensic-run candidates paid full val though each named ≤7 tasks, 6 screens came back `inconclusive`
on an ad hoc subset. `evaluation_plan.build_evaluation_plan(cluster, history=...)` +
`persist_evaluation_plan(run_dir, tag, plan)` write `<candidate_dir>/evaluation_plan.json`
(`affected_tasks`/`regression_sentinels`/`stage`; call: `algorithm.md`, "Evaluation plans"). Act on
`plan.stage` — 0 `STAGE_STATIC`: micro-test only; 1-2
`STAGE_TARGETED_SMALL`/`STAGE_EXPANDED_CLUSTER`: `screen.py --ids <affected_tasks+regression_sentinels>`;
3 `STAGE_REGRESSION`: a second `screen.py` call, no `--broken`; 4 `STAGE_BROAD_PARTIAL`:
`screen.py --tier 2`; 5 `STAGE_FULL`: straight to step 6 — escalate only on a wider footprint than
assumed:

```bash
python "$A/screen.py" --run-dir "$R" --project "$P" --candidate "$R/work/$TAG" \
       --ids "$(python -c 'import json;p=json.load(open("'"$R"'/candidates/'"$TAG"'/evaluation_plan.json"));print(",".join(p["affected_tasks"]+p["regression_sentinels"]))')" \
       --k-se 1.0 --rationale "evaluation_plan stage"
```

Only the candidate pays, for the subset. `decision` is `kill` or `promote` — **never accept** — kills
only on proven harm. **Check the arithmetic first:** `savings.breakeven_kill_rate` is the fraction it
must kill to pay for itself; baseline freezes this as `screening_structurally_uneconomical` (#631) —
if false, skips beyond `max_screen_skips` (default 1) are refused.

**6. Honest gate on FULL val.** Before this step, confirm every addressable diagnosed cluster for the
round is folded in or deferred, with why (`algorithm.md`, "Bucketing edits within a slot"). Evaluate
the whole split (tags by the candidate **dir name**), then decide off those rollouts:

```bash
python "$S/phases/evaluate/scripts/run.py" --run-dir "$R" --project "$P" \
       --candidate "$R/work/$TAG" --split val --n-trials <num_trials>
python "$A/gate_check.py" --run-dir "$R" --candidate "$TAG" --k-se <gate_k_se>
```

`"verdict"` is evidence, not a command — decide accept/reject yourself, citing the numbers in
`commit.py --note`. `"indecisive"` means too little of val ran, not a rejection. **`regressions` is
diagnosis, not a veto** (`--veto-regressions` restores the old no-regression veto). **Read `footprint`
before the delta; `unresolved` is no evidence.** `references/algorithm.md`, "Gate as evidence"/
"Measuring only what the edit reaches".

**If `capevolve.yaml` declares `objectives`** (e.g. reward+cost), use `--mode pareto` on these SAME
two scripts (`--objectives`/`--metrics-candidate`/`--metrics-current`/`--metrics-stderr-*`; never
`round.py`). It refuses (`ParetoObjectiveError`) rather than guesses on a missing stderr; the result
is a **frontier read**, not a disguised boolean. `algorithm.md`, "Pareto acceptance".

**7. Handover + DIAGNOSIS.json, THEN commit.** Add one `## Iteration <cid>` entry below
`work/$TAG/JOURNAL.md`'s marker (not `$R/JOURNAL.md`): what, why, what the numbers said. 
`work/$TAG/DIAGNOSIS.json` maps edits→clusters→tasks. `commit.py` refuses without either. Then
commit, so `best_id`, stall and the audit log stay real; `--decision reject` keeps the old best:

```bash
python "$A/commit.py" --run-dir "$R" --candidate-id "$TAG" --from-dir "$R/work/$TAG" \
       --decision accept --val <cand_mean> --note "<one line: the general rule you added>"
cap-evolve dashboard --export "$R"
```

**On a reject, pass `--reject-basis`** (`gate`/`screen_kill`/`ceiling`/`budget`/`infra` — never conflate
"promote" with "evaluated on full val"). 3+ rejects? Run `merge_rejects.py` first. `commit.py`
**refuses a `--candidate-id` that already carries a decision** (`--force` to repair deliberately).
Pass `--optimizer-usd/--optimizer-tokens/--optimizer-seconds` for your own proposal cost.

**Two decisions that are NOT rejects**: `--decision inconclusive` (`verdict_stable: false` — run
`grow.py` first); `--decision provisional` (Δ>0 under the bar — `grow.py` buys trials, capped at 2).
`references/algorithm.md`.

**8.** Real framework bug/gap? Log it in `work/$TAG/FRAMEWORK_IMPROVEMENTS.md`, not just chat.

## Parallel round — the default cascade

**The whole of steps 5–6 is one command**, once every planned branch exists. `round.py` screens every
tag, pairwise-merges disjoint survivors, builds the null control, evaluates each survivor in parallel
*processes* (own adapter `apply()`, never shared), gates serially, one table. Carry each candidate's
own `evaluation_plan.json` into `--plan`:

```bash
python "$A/round.py" --run-dir "$R" --project "$P" \
       --candidates cand_1,cand_2,cand_3 --plan "$R/work/plan.json" \
       --n-trials <num_trials> --k-se <gate_k_se> --concurrency 8 --max-parallel 2
```

`$R/work/plan.json`: one entry per tag, `{"cand_1": {"ids": "8,14,22", "rationale": "<evaluation_plan.rationale>", "cluster_ids": ["c3"], "edit_kind": "code"}}`.

Read `screen_stage`/`screen_killed`/`merge_stage` first (`algorithm.md`, "Gating N Bucket-A siblings").
`--no-merge` past `max_merge_skips` (default 1) is refused (#630). Gold-replay check? `--pregate-check`.
`round.py` still refuses fewer than `MIN_SIBLINGS` (3) tags unless you pass
`--single-candidate-justification` (step 2's `plan.json` IS that justification below 3) or an
`--afford-check-file`. **`--mode` stays single-metric** — a pareto-gated candidate is always gated by
hand through `gate_check.py`.

`--concurrency` (gate load) is low by default; `round.py` refuses one too hot to
resolve its verdict — never raise it to buy wall clock. Read
`noise_floor_from_control` FIRST: inside that band is no evidence, whatever the verdict.
It never commits; which part of a bundle to keep is your call.

Four fan-out invariants (reasoning: *Parallelism*, [`references/algorithm.md`](references/algorithm.md)):
diagnosis fans freely (≤2 at a time, read-only); proposal fans across distinct copies, a tag that is
unique per sibling (shared tags corrupt rollout filenames); the gate stays serial — re-gate every
remaining sibling against the new best after any accept; never fan out across test, pay before you
do. Concurrency also composes inside one eval (`screen.py --workers N`), thread-safe only.

### Per-task fan-out — the cheap gradient

Reach for this only when `k/n` bands show loss **concentrated in a few named tasks**: one task at
`n_trials` buys the same bit as a full-val round. Helpers, in order — `taskeval.py` (detached),
`mechanisms.py` (list BEFORE diagnosing), `integrate.py`, `funcmerge.py`, `merge_taskopt.py` — then gate
once via `round.py`. Flags: [`references/per-task-fanout.md`](references/per-task-fanout.md). A
multi-branch artifact is assembled with `integrate.py`, never by one merge — a clean `funcmerge` is not
evidence the branches compose. Clean merge is a syntactic property; composition is empirical.

## Measurement discipline

**Measure step 3's null control twice**: the gap between two byte-identical parents is the round's bar.
Rest — ceiling arithmetic, the binomial floor, the sign test —
[`references/measured-lessons.md`](references/measured-lessons.md). (1) Explore fast, gate slow, gate
ALONE. (2) Two independently-seeded blocks, agreeing in sign, before a small effect is a result —
`multirep.py` takes the error across whole runs; unaffordable ⇒ "not resolvable" is the honest output.

## Stop & seal, then MEASURE (once)

**Before you stop, merge disjoint-cluster `accepted` candidates — REQUIRED, a visible protocol violation
to skip, never a judgment call.** The forensic run's `merge_compliance_warning` fired twice naming
exactly this and sealed anyway both times:

```bash
python "$A/merge_search.py" --run-dir "$R" --project "$P" --base "$BEST" \
       --survivors <comma-separated accepted/surviving tags>
```

If `measure.py`'s automatic `check_merge_compliance` reports `merge_compliance_warning` for candidates
you have not run this for, **the round is not finished** — run it, or state explicitly in `JOURNAL.md`
why no merge applies (a real `funcmerge.py` collision, not a skipped choice). A sealed run with an
unaddressed warning is a protocol violation your final report must name. `algorithm.md` §"Merging
accepted candidates before you finalize".

Spend is not a CLI subcommand: **every 2–3 rounds** run `spend.py`, re-read from the run dir, never a
total in your head (`$6.00` becoming `$6.01` is how that total drifts). Stop when `recommendation` is
`stop`, then produce the run's one honest table — seed vs best on **val**, **train** when worth
reporting, and the **sealed test** split scored once:

```bash
python "$A/measure.py" --run-dir "$R" --project "$P" --train auto
python "$S/phases/report/scripts/run.py" --run-dir "$R"
```

`measure.py` seals test through the same `harness.finalize` the finalize phase calls (interchangeable
with `phases/finalize/scripts/run.py`; a second finalize raises `TestSealError`). Report its refusals
unsoftened: an **empty** split is `empty`, not 0.0; a **no-holdout** spec is a **FIT metric**; a
negative `screen_ledger.net_rollouts` says screening was pure overhead; `best_id == "seed"` is a **null
result with a diagnosed cause**. Wait for it to exit, or the seal is wasted. No finalize, no result.

## Honesty invariants that are yours by hand

Core enforces the split seal, the val-only gate and the tamper guard whether you cooperate or not
(`skills/phases/{evaluate,gate,finalize}` document them). Three are yours: **never hand a subset result
to `gate_check.py`** — its `coverage` reads 1.0 since its denominator *is* the subset; **a round with no
run-dir artifacts is a bug**; **sealing with an unaddressed `merge_compliance_warning` is a bug you
created** — host.py owns no algorithm decisions, so that one is on you alone.

**Report a broken framework file; don't hand-work around it.** `references/algorithm.md` §honesty.

## References

One level deep — each read standalone, none points at another.

- [`references/algorithm.md`](references/algorithm.md) — why free-form, honesty under full autonomy,
  screening break-even, the constraint surface, branch planning, evaluation plans, model routing,
  Pareto acceptance. **Load** before relying on a screen, growing a candidate, or skipping a rule.
- [`references/measured-lessons.md`](references/measured-lessons.md) — binomial floor, full val vs a
  hard subset, the sign test. **Load** before your first gate decision, or when a result surprises you.
- [`references/per-task-fanout.md`](references/per-task-fanout.md) — fan-out economics, briefing
  contract, canary selection. **Load** when the loss concentrates in a few named tasks.
- [`references/edit-design-lessons.md`](references/edit-design-lessons.md) — scorer audit, guard
  closure, measured backfires. **Load** before editing a surface the first time, or after two rejects.
- [`references/microcase.md`](references/microcase.md) — micro-test schema, `gen` contract. **Load**
  before proposing a candidate for a cluster with (or needing) a case.
- [`references/context-sources.md`](references/context-sources.md) — the Phase-0 sources compared.
