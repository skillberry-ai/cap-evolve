# Post-merge review — four merged skill PRs (#368 agent-optimize · #369 gepa · #380 skillopt · #373 mcp-tool)

Reviewed against `main` at `af7cf9d6`.

> **Rebase addendum (`main` at `c8bc2292`).** Re-derived a second time after #387, #388,
> #391, #393 and #396 landed. **Three of my own conclusions changed, and one of my own
> tests caught me** — recorded here rather than silently corrected, because the whole
> finding of this review is that a hand-derived skill-vs-code table decays:
>
> - **gepa's Known gaps went from 5 bullets to 2.** #387 fixed the hollow eval-cache
>   reflection (`cache.py:91-99` now persists `output`/`trace`/`errored`, and
>   `gepa.py:162-175` replays them), and #396 fixed BOTH the missing `step` record and the
>   non-accumulating `JOURNAL.md` — `harness.record_iteration` (`harness.py:1037-1077`) is
>   now the one place any algorithm ends an iteration, and gepa calls it at four sites. So
>   the section I had cut from 5 to 4 bullets needed cutting again, to 2: the missing task
>   input (`gepa.py:230` vs `:263-267`) and the empty-train→val fallback (`:530`).
> - **Two `harness.py` citations rotted again.** #393 + #396 grew the file ~266 lines, so
>   `harness.py:2004-2006`/`:2013` became `:2270-2272`/`:2279`. Re-derived mechanically
>   (`/tmp/capreview-pma-rederive2.py`) rather than by hand: **23/23 skillopt + 3/3 gepa
>   citations now resolve.** All 19 `skillopt.py` citations held — only the cross-file ones
>   moved, which is the predictable failure mode and an argument for citing symbols over
>   lines.
> - **My own tripwire fired, for the right reason and the wrong cause.**
>   `test_skillopt_minibatch_focus_is_still_empty_by_construction` went red — not because
>   #371 was fixed, but because #391 reworded the summary from `of 0 tasks` to
>   `of 0 focused task(s) of N on val`. The gap is exactly as real. Two consequences: the
>   test now asserts the **property** (`0 solid / 0 flaky / 0 failing`, and no val feedback
>   leaking into a train-focused prompt) instead of a sentence, and skillopt's SKILL.md no
>   longer quotes the pre-#391 string. A tripwire that fires on rewording is a false alarm,
>   which is worse than none — my own mistake, caught by my own test.
> - **Preserved unchanged:** the gepa budget-ceiling correction, re-verified against current
>   `gepa.py` (`_try_merge` samples a FRESH minibatch at `:831` and evaluates the merge plus
>   BOTH parents at `:832`/`:834`/`:836`, then pays a second full val) — `5·mb +
>   2·|val|·n_trials` stands exactly. #396's AST guard in
>   `core/tests/test_iteration_record_parity.py` is untouched (`git diff` empty, 9 passed).
> - **Added from #396's semantics:** an INDECISIVE gepa child **charges `spent.iterations`**
>   while leaving the stall counter alone (`record_iteration(..., indecisive=True)`,
>   `harness.py:1072`). The spend meter counts it because the rollouts were really spent;
>   only the evidence meter does not. A reader budgeting a run needs that distinction and
>   the skill did not have it.
> - **#388's fix preserved through the conflict:** both merge conflicts were #388's removal
>   of the phantom `cap-evolve status` / `cap-evolve finalize` subcommands colliding with my
>   trims. #388's substance won; the phantom commands were not reintroduced (verified by the
>   14 subcommand-guard tests).
>
> Final counts: **836 passed, 12 skipped** (main's 829 + 7 new), all four `check.py` clean,
> `bash examples/toy_calc/run.sh` → `best_id cand_0001`, `test_reward 1.0`, `finalized true`,
> and the three failing-first assertions re-verified RED against `origin/main`
> (`/tmp/capreview-pma-failingfirst2.py`).
 None of the four was independently reviewed before merge.
`main` baseline confirmed green at **805 passed, 12 skipped**
(`PYTHONPATH="$PWD/core:$PWD/dashboard/backend" python -m pytest core/tests -q`).

Merge order matters for reading this: `#350` (1775cddd, snapshot ignore) landed **before** #369, and
`#386` (cfcad862, the shared `OptimizerContext` assembler) landed **after** all four. #386 is what
made three of #369's and eleven of #380's statements wrong again.

---

## Skill-vs-code re-derivation

### gepa — #369 claimed 14 divergences (10 fixed in text, 4 flagged). Re-derived: **3 live divergences**, and 2 of the 4 flagged gaps are no longer real.

Body claims (all verified against `core/cap_evolve/gepa.py`, `selection.py`, `cache.py`,
`skills/algorithms/gepa/scripts/run.py`):

| claim | code reality | file:line | still accurate? |
|---|---|---|---|
| parent = frequency-weighted sample over per-instance (co-)winners, seeded | `rng.choices(pool, weights=counts)` over candidates with ≥1 win | `selection.py:180-192` | yes |
| strict `pareto_frontier` is a *different*, narrower set used by merge + `frontier_size` | two distinct functions; merge calls `pareto_frontier`, selection calls `_instance_win_counts` | `selection.py:114`, `gepa.py:795`, `:721` | yes |
| local gate is `sum(child) > sum(parent)` on the **same** minibatch, `2·mb` rollouts, eval-cached | exactly that | `gepa.py:639-643` | yes |
| reflection reads **train** traces only | `_sample_minibatch(train_ids…)`, `ctx.inject(split="train")` | `gepa.py:559`, `:585` | yes |
| "failing" = hard threshold `reward < 1.0`; header reads `N/N pass` | `< 1.0`; header is `{len(passing)}/{len(per)}` | `gepa.py:228`, `:236-237` | yes |
| ~800-char truncation, at most 12 tasks | `[:800]` ×3, `actionable[:12]` | `gepa.py:251-259` | yes |
| merge: two strict-frontier dominators with a common ancestor both beat, component-wise | `_find_merge_pair` + `_build_merge`, `origin` per component | `gepa.py:795-804` | yes |
| `--max-merges` counts attempts that BUILT a candidate; a skip is free | `merges_done += 1` only when `merge_step is not None` | `gepa.py:706-708` | yes |
| protected-path tamper ⇒ INDECISIVE, no reward, stall untouched | `update_spent(iterations=1, accepted=None)`, `candidate_val: None` | `gepa.py:626-637` | yes |
| every hyperparameter default (`0/50/4/1/2/3`, `--workers 1`, `--store git`) | matches | `scripts/run.py:33-56` | yes |
| **`--max-metric-calls` overshoot bound is `2·mb + \|val\|·n-trials`, "one more minibatch on a merge iteration"** | a merge fires *inside* an accepting iteration and evaluates the merge **and both parents** on a **freshly sampled** minibatch, then pays a second full val ⇒ worst case `5·mb + 2·\|val\|·n-trials` | `gepa.py:698-704`, `:813-819`, `:833` | **NO — understates a budget ceiling by ~2.5×** |

`## Known gaps` (the interesting part):

| flagged gap | code reality | file:line | still accurate? |
|---|---|---|---|
| reflective dataset carries no task **input**, though `gepa.py`'s docstring claims it does | docstring says "contributes its input"; the writer emits only `Agent output` / `Trajectory` / `Feedback` | `gepa.py:222` vs `:253-259` | **yes** — verified in a real `REFLECTION.md` (see Evidence) |
| on an eval-cache hit only `{reward, feedback}` are stored, so `Agent output:` is empty | `EvalCache.put` persists two keys; a hit builds `raw={"cached": True}` | `cache.py:88-90`, `gepa.py:161-167` | yes |
| **candidate snapshots keep the loop's scratch because the snapshot call omits the ignore list; and the dotfiles are not excluded from the component list** | `run_dir.snapshot(..., ignore=_SNAPSHOT_IGNORE)` at BOTH call sites (#350), and `NON_CAPABILITY_FILES`/`DIRS` now cover `CLAUDE.md`/`AGENTS.md`/`GEMINI.md`/`.claude`/`guidance`/`trajectories`/`prior_iterations` (#386) | `gepa.py:682`, `:846`; `types.py:26-43` | **NO — both halves fixed. Deleted.** |
| iterations charged with no `step` event emitted | gepa logs 11 event kinds, none named `step`; `log_event("step")` exists only in `harness.py:1383`/`:1563` | `gepa.py` (grep) | yes |
| **optimizer context reaching GEPA has been narrower than hill-climb's (#109)** | `gepa_loop` takes the shared `OptimizerContext` and calls the same `inject()`/`instructions()` as its siblings | `gepa.py:478`, `:501`, `:585-595` | **NO — fixed by #386. Rewritten to the live half (JOURNAL non-accumulation).** |
| `JOURNAL.md` injected but never accumulates in gepa | `_reconcile_journal` is called from `harness.run_step` only, which gepa does not use | `harness.py:1578` | yes |
| empty `splits.train` ⇒ silent fallback to **val** ids | `list(...train) or list(...val)` | `gepa.py:522` | yes |

Plus one in the reference: `gepa/references/concepts.md:100-105` asserted the component exclusion list
"does *not* cover the optimizer-agent dotfiles". False since #386 — `types.py:35-39` was changed
*specifically* so an injected read-context dir cannot appear to gepa as an editable component. **Fixed.**

### skillopt — #380 claimed 10 divergences (5 fixed, 5 flagged). Re-derived: **all 5 flagged gaps still real**, but **12 live divergences of a different kind** — the citations that make them checkable.

| claim | code reality | file:line | still accurate? |
|---|---|---|---|
| mini-batch ids come from train but filter the parent's **val** rows ⇒ `0 … of 0 tasks` | `train_ids` read, sliced, handed to `ctx.instructions` which filters `current_val.per_task` by train ids; splits disjoint | `skillopt.py:237`,`:291`,`:300` → `harness.py:2004-2006`; `splits.py:117-119` | **yes** (gap real) |
| …"with no task ids" | the *focus summary* and *failure index* are empty, but `_passing_block` is built from the WHOLE val split since #370, so protect-these-ids IS populated | `harness.py:2013` | **imprecise — corrected** |
| epoch-boundary re-eval scores whole train twice, then discards all but ~20 | `evaluate_candidate(split="train")` ×2, no `ids=`, then filtered to `sample_ids` | `skillopt.py:467-472`, `:473-475` | yes (gap real) |
| vacuous comparison when an epoch accepted nothing | guard `prev_epoch_best_id != run_dir.best_id`; log claims a train sample size | `skillopt.py:464`, `:478-482` | yes (gap real) |
| `requested_edits` vs `applied_changes` read nowhere | 2 write sites, 0 read sites repo-wide | `skillopt.py:346`,`:353` | yes (gap real) |
| …"A run at `L=4` logged `applied_changes: 6`" | **worse than documented**, and #386 made it worse: the ignore list matches 7 `.md` *basenames* while `run_step` injects `guidance/`, `trajectories/`, `prior_iterations/*/diff.patch`, which `_SNAPSHOT_IGNORE` keeps out of the parent snapshot. Measured `applied_changes: 10` for **one** real edit, and `10` again on a step whose capability file was byte-identical to its parent | `skillopt.py:406-435`, `:420` | **understated — corrected with the measurement** |
| `"skill"` leaks into the live prompt | `"Comparing the skill at the START of this epoch…"` | `skillopt.py:147` | yes (gap real) |
| `improved` computed + logged, not exclusive, never in the prompt | `if after > before` is a separate non-`elif` branch; `_slow_update_instructions` never reads it | `skillopt.py:184-185`, `:139-166` | yes |
| slow update is never force-accepted | goes through `harness.run_step` like any step | `skillopt.py:493-499` | yes |
| `--max-iterations` accepted and ignored | declared with `help="IGNORED…"`, never passed to `skillopt_loop` | `scripts/run.py:42-43`, `:105-118` | yes |
| every documented flag exists | all 18 present | `scripts/run.py:35-78` | yes |
| **11 of 18 `file:line` citations** | drifted 7-9 lines when #386 restructured the module; e.g. `skillopt.py:230` (cited for the train-ids read) is now a docstring line | see table above | **NO — all refreshed** |
| **"both land with PR #370; until then read `harness.run_step` itself"** | #370 landed as `ae71aa87`; `hill-climb/references/run-step.md` exists | — | **NO — stale, removed** |

The stale citations are not cosmetic. A "verify me" claim whose line number lands on unrelated code
reads as fabricated, which is exactly the credibility this whole effort was buying back.

---

## #368 token budget (measured)

Measured with `tiktoken` `cl100k_base` (no tokenizer was in the venv; installed it).
Body = everything after the closing frontmatter `---`; the `description` is always-in-context
metadata and is budgeted separately, per `.review/skill-duplication-analysis.md`.

| | lines | body tokens | whole file |
|---|--:|--:|--:|
| pre-#368 (`24e58fe8^`) | 922 | — | 60,176 chars |
| as merged by #368 | 337 | **5,580** | 5,580 |
| after this review | 311 | **5,000** | 5,137 |

#368 reported ~5,444; the real number was **5,580** — 11.6% over the ≤5,000 bar, and the PR flagged
the overage instead of fixing it.

**Verdict: the overage was not earning its place, so I cut it.** −580 tokens, no rule deleted. What
moved, and why each was restatement rather than instruction:

- the fan-out invariants' *rationale* — `references/algorithm.md` § *Parallelism* states all of them
  in full; the body keeps every rule verb and points there (ownership contract: one owner states it).
- the "concurrency composes from three places" enumeration — same section of `algorithm.md`; the
  thread-safety criteria (no shared scratch dir / live container / module-global client) stayed,
  because that list is *not* in the reference.
- the per-task-fan-out helper roll-call's flags (`--supersedes`, `--floor`, `--canary-auto`,
  `--traces`, `dropped_additions`) — all present in `references/per-task-fanout.md`, which the
  pointer names as carrying "every helper's flags". Every helper name stayed (`check.py` requires it).
- the `measure.py` refusals' and screening break-even's *reasoning* — both in `algorithm.md`.
- **a genuine triplication**: "measure the null / a candidate inside that band is not evidence" was
  stated three times in one body (step 2, the Parallel-round paragraph, Measurement-discipline rule 1).
  Now stated once operationally in step 2, with the "twice" requirement folded in.

Two counting bugs #368 introduced while condensing, both fixed: "state these **five** invariants"
above a four-item list (it merged old items 4+5 into one bullet), and "**Two** rules decide whether a
round's number means anything" above three.

`core/tests/test_agent_optimize_skill.py` — **passes unmodified** (5 passed; `git diff` on the file is
empty). It caught one of my compressions mid-review: I had rewritten "skipping the **re-gate**
double-counts one gain" as "or you double-count a gain", and the test pins the literal term `re-gate`.
Restored — and that is the test doing exactly its job, so it is worth naming here rather than quietly
fixing. The companion behavioral check
`skills/algorithms/agent-optimize/scripts/check.py` (1,167 lines; it executes every command SKILL.md
documents against a throwaway run dir) also passes unmodified: `ok: true, problems: []`, 60+ notes. It
caught a second one: I had shortened "the old **no-regression** veto" and it requires that token.

---

## #373 policy guard (verified empirically, not read off the PR body)

Reproduced against the shipped `cap_evolve.tool_surface` with mcp-tool's real
`DEFAULT_POLICY = {"allow": ["description","params","examples","add","remove"]}`
(`/tmp/capreview-postmerge-algos-mcpproof.py`):

```
=== (1) params edit carrying properties/type/required
report: {"changed": ["params:kb_search"], "refused": []}
parameters now: {"type": "array", "properties": {"limit": {...}}, "required": ["injected"]}

=== (2) add edit carrying a code key
report: {"changed": ["add:srv"], "refused": []}
added keys: ['code', 'description', 'name', 'parameters'] | code key present: True

=== (3) validate() on the schema-rewritten artifact
validate: {"ok": true, "tools": ["kb_search", "srv"], "problems": []}
validate() source references load_policy: False

=== (4) policy path
code: ['f = Path(capability_dir) / "policy.json"']
only inputs/policy.json present -> allow = ['add','description','examples','params','remove']  (ignored)
capability_dir/policy.json present -> allow = ['schema']                                        (read)
```

All four of #373's claims hold on current `main`:

1. `apply()` filters the edit's **`kind` label** only (`tool_surface.py:65-67`). A `params` value is
   `dict.update()`-merged into `parameters` (`:82`), so `type`/`required`/`properties` rewrite the wire
   schema and come back `refused: []`.
2. `add` appends the value verbatim (`:72`), so a `code` key lands unrefused.
3. `validate()` never calls `load_policy` and returns `ok: true` on the rewritten artifact (`:102-130`).
4. The loader reads `<capability_dir>/policy.json`; `inputs/policy.json` is ignored (`:36`).

**The skill states this plainly rather than implying enforcement.** `mcp-tool/SKILL.md:41-56` is
headed "**The policy checks the edit's LABEL, not its effect**", names both bypasses individually,
and closes with "Nothing downstream re-checks the boundary, so the discipline is yours." That is the
honest form. Its edit-boundary table still says schema/code are "no", which is correct as *policy*,
and the paragraph immediately below says what is and is not *enforced* — no contradiction.

**Policy path — does any of my four skills still name the wrong one? No.**
`mcp-tool/SKILL.md:58-61` names `inputs/policy.json` only to rule it out. gepa, skillopt and
agent-optimize never mention a policy file.

But four surfaces outside my four skills still claim the wrong path (#352):

- `core/cap_evolve/tool_surface.py:15` (module docstring) and `:35` (`load_policy`'s own docstring) —
  **the most authoritative surfaces in the repo, and the ones the skill cites.** Both said the loader
  reads `inputs/policy.json`. **Fixed in this PR** (in core, not a skill, so not an ownership breach).
- `skills/capabilities/tools/references/{examples.md:366, pitfalls.md:127, concepts.md:114}` — owned
  by the `tools` skill. **Not touched** per the ownership contract; recorded here and in the PR body
  under "what `tools` should drop".

---

## Instruction loss

`git show` on each of the four merge commits, diffing removed lines against the current body plus
every reference, then a mechanical audit of bolded spans and backticked identifiers
(`/tmp/capreview-postmerge-algos-ruleaudit.py`).

**#368 — one real loss, and it was a dangling promise.** `SKILL.md` names "the sign test for effects
below the floor" as living in `references/measured-lessons.md`. The old rule 9 — *pre-register
directional predictions and use a sign test; 9/10 positive gave p = 0.0107 where no individual z
reached 2; write each prediction down before its arm runs or the test is worthless* — is in **no**
file in the package. A reader following the pointer finds nothing. **Restored** into
`measured-lessons.md` § *The binomial floor*, with a regression test.

The other eight of the old nine measurement rules, and all nine old honesty invariants, are
accounted for: rules 1/2/3/4/6/7/8 in `measured-lessons.md` (verified by their measured numbers:
`0.0778`, `0.0615`, `1.27`, `0.0146`, `0.0115`, `0.0262`, `Sum \`1 - rate\``), rule 6 also in
`per-task-fanout.md`. Honesty invariants 1/3/5/6/7/8/9 survive in the body; 2 was **deliberately
inverted** to match the code (`regressions` is diagnosis, not a veto; `--veto-regressions` restores
the old behavior) and 4 was correctly deleted as a restatement the `gate`/`finalize` phases own.

My own cut briefly dropped one identifier: `cap-evolve-diagnoser`, the concrete subagent to dispatch
for parallel diagnosis. It exists (`plugins/cap-evolve/agents/cap-evolve-diagnoser.md`) and
agent-optimize's SKILL.md is the **only** skill that names it — so dropping it would have been a real
loss. **Restored.**

**#369 — no rule lost.** Removals were the 6-row routing table (owner: the `using-cap-evolve` router
and the frontmatter description), the agent-mode restatement (owner: `orchestrate`), the
re-specified reflective-dataset format (owner: `diagnose`), and a step-by-step loop restatement now
owned by `hill-climb`. `--no-regression` is delegated with "as hill-climb" and hill-climb documents
it (`hill-climb/SKILL.md:100`). One routing row is gone without a new home — *"tiny task set (frontier
collapses to 1-2 points) → hill-climb"*; the description carries the two main routing rules, so this
is advice-level, noted not fixed.

**#380 — one half-loss, out of my ownership.** The deleted *"Pitfall: small val sets"* carried
*"with a small val set, raise `--n-trials` … or use a **graded** reward so the paired significance
test has signal."* The `--n-trials` half survives in the body ("spend your tuning budget on
`--n-trials` and the gate"); the graded-reward half is in no skill. It belongs to `phases/gate`
(owner of the significance bar), which does not carry it. Recorded for that owner, not edited.

**#373 — no rule lost.** The annotations table, the human-in-the-loop rule, and the
execution-vs-protocol error distinction all landed in `references/concepts.md` §4 (verified:
`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`, `human-in-the-loop`, `isError`,
`poisoning`, `list_changed` all present). The reader-capability-tier advice was correctly deleted
(owner: `skill-package`).

**Ownership-contract compliance.** All four point at `hill-climb` for the shared iteration mechanics;
none restates the honesty invariants, the agent-mode loop, the failure taxonomy, or the
reflective-dataset format. Two shortfalls found: gepa pointed at `hill-climb/SKILL.md` rather than
its `references/run-step.md` (**fixed**), and skillopt's pointer was gated behind "both land with
PR #370" which has landed (**fixed**).

---

## Problems found

1. **gepa `## Known gaps` reported two fixed defects as current** — the dirty-snapshot + unexcluded-
   dotfiles gap (fully fixed by #350 + #386) and the optimizer-context-parity gap (fixed by #386).
   A skill that over-reports gaps trains its reader to distrust the section. **Fixed.**
2. **gepa's `--max-metric-calls` overshoot bound understates a merge iteration by ~2.5×** — a real
   budget-safety number. **Fixed.**
3. **gepa `references/concepts.md` asserted the exact opposite of what #386 changed** — that the
   component list does not exclude the injected read-context. **Fixed.**
4. **11 of 18 `file:line` citations in skillopt's `## Known gaps` point at unrelated lines** after
   #386's restructuring. **Fixed**, plus a standing instruction to re-derive the section if a citation
   stops matching.
5. **skillopt understated the `applied_changes` defect** — it is not merely uninformative, it has no
   zero: 10 for one real edit, 10 for none. **Fixed with the measurement.**
6. **#368 shipped 5,580 body tokens against a ≤5,000 bar** (and mis-reported it as ~5,444).
   **Fixed: 5,000.**
7. **#368 lost the sign-test rule while keeping the pointer that promises it.** **Fixed.**
8. **`core/cap_evolve/tool_surface.py`'s module and `load_policy` docstrings still named
   `inputs/policy.json`** — issue #352's defect surviving in the code that *defines* the answer.
   **Fixed, failing-first.**
9. Not fixed, recorded for their owners: 3 wrong policy paths in `skills/capabilities/tools/
   references/`; the graded-reward guidance that `phases/gate` should adopt.

---

## Evidence

- Baseline `805 passed, 12 skipped` → after this change **`812 passed, 12 skipped`** (805 + 7 new),
  always pinned: `PYTHONPATH="$PWD/core:$PWD/dashboard/backend" python -m pytest core/tests -q`.
- All four `scripts/check.py`: `ok: true, problems: []` (before and after).
- `#373` guard: `/tmp/capreview-postmerge-algos-mcpproof.py`, output quoted above.
- Token measurement: `tiktoken` `cl100k_base`, body-only, quoted above.
- Failing-first: `/tmp/capreview-postmerge-algos-failingfirst.py` shows all three new assertions fail
  against `HEAD`'s text.
- **Zero-API runs, `examples/toy_calc`, mock optimizer, via `cap_evolve.cli run`** (flow reused from
  `ci/e2e_all_algorithms.sh`):

  | | gepa | skillopt |
  |---|---|---|
  | best_id | `gepa_0001` | `so_e01s01` |
  | accepts | 1 | 1 |
  | best val | 1.0 | 1.0 |
  | **sealed test** | **1.0** (baseline 0.0, Δ +1.0) | **1.0** (baseline 0.0, Δ +1.0) |
  | iterations | 3 | 3 |

  Both reached a gate-accepted candidate and a sealed test score. **Honest caveat:** both fired
  `gate_warning` — "combined/paired SE is 0 (likely n_trials=1 or identical trials) … falling back to
  STRICT (accept any delta>0)". Expected on a deterministic `n_trials=1` example and stated honestly
  in the accept reason, but these are **STRICT-fallback accepts, not significance-gate accepts**.
  They prove the plumbing and the seal, not the gate's discrimination.

- gepa `REFLECTION.md` from that run, verbatim — the missing-input gap, live:

  ```
  ### task a3
  - Agent output: I think 2 * 5 is roughly some number.
  - Trajectory: prompt_had_calc=False
  - Feedback: expected '10' but agent produced '…'; the prompt likely lacks an explicit
    instruction to compute and output only the number
  ```

  There is no `- Input:` line. Note the refinement: the *output* is populated (so "the reflection is
  empty" would be wrong — the skill does not say that), but the task input is structurally absent and
  is recoverable here only because this adapter's output happens to echo the expression.

- Accepted candidate snapshots contain exactly `INSTRUCTIONS.md`, `PROCESS.md`, `prompt.txt` — no
  `REFLECTION.md`, `FOCUS.md`, `guidance/`, `trajectories/`, dotfiles. `_SNAPSHOT_IGNORE` works,
  which is precisely what makes the `applied_changes` asymmetry in problem 5 possible.
- skillopt `skillopt_step` events, verbatim:
  ```
  epoch 1 step 1  edit_budget=4  requested_edits=4  applied_changes=10  accept=true
  epoch 2 step 1  edit_budget=4  requested_edits=4  applied_changes=10  accept=false
  ```
  Step 1's 10 = 7 `guidance/*` + 2 `trajectories/*` injected + 1 real edit (`prompt.txt`).
  Step 2's `prompt.txt` was byte-identical to its parent.

---

## Overall verdict

**#373 (mcp-tool) is the one that did its job.** Every claim it makes about the guard is true today,
verified empirically rather than read off the PR body, and it states plainly that the guard does not
guard. Its policy-path correction is right, and nothing was lost — the removed depth is all in
`references/concepts.md`. No changes needed to the skill.

**#369 (gepa) and #380 (skillopt) were honest when written and have decayed since.** Both were
written *before* #386 restructured the modules they cite, and neither had a mechanism that would
notice. gepa now over-reports two fixed defects as current; skillopt's citations mostly point at
unrelated lines. The substance of skillopt's five gaps is entirely intact and one of them turned out
worse than documented. This is the failure mode the effort was fixing, reappearing not through
carelessness but because a hand-derived skill-vs-code table has no guard — which is why the fix here
includes tests, not just corrected prose.

**#368 (agent-optimize) knowingly shipped over the bar and it was not earning it.** 5,580 measured
against ≤5,000, cut to 5,000 with no rule deleted — the material that moved was restatement of its
own references or of `algorithm.md`, plus one rule stated three times in a single body. It also lost
the sign-test rule while keeping the pointer promising it, and left two miscounted lists ("five
invariants" over four; "two rules" over three) behind as evidence of a hurried condensation.

The systemic lesson, and the reason this PR adds `core/tests/test_skill_code_claims.py` rather than
only editing prose: **a skill that documents a code defect needs a test that fails when the defect is
fixed.** Otherwise the doc silently becomes a lie the moment someone does the right thing — which is
exactly what #386 did to #369, twice.

---

## PRs/issues I opened

- **PR #394** (`postmerge-algos-fixes`): everything marked **Fixed** above, plus
  `core/tests/test_skill_code_claims.py` (7 tests, 3 failing-first).
  <https://github.com/skillberry-ai/cap-evolve/pull/394>
- **Issue #395** — `skillopt.applied_changes` has no zero: it counts the injected read-context, so it
  cannot detect an optimizer that made no edit. Real but a code fix outside this PR's scope; the fix
  is to drop the duplicate seven-basename ignore list in favour of `types.NON_CAPABILITY_FILES` /
  `NON_CAPABILITY_DIRS`, which #386 extended for exactly this class of problem. Sibling of #371.
  <https://github.com/skillberry-ai/cap-evolve/issues/395>
- Recorded in PR #394's body rather than filed, being other owners' skills: the 3 wrong policy paths
  in `skills/capabilities/tools/references/` (last surfaces of #352, now that the core docstrings are
  fixed), and the graded-reward guidance `phases/gate` should adopt from #380's deleted small-val
  pitfall.
